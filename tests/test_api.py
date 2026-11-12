import base64
import io
import json
import wave

import httpx
import pytest
from openai import OpenAI

from lang_handler.api import OpenAIService
from lang_handler.errors import ServiceError
from lang_handler.network import proxy_url
from lang_handler.tts_api import realtime_speech


def service_with(handler):
    client = OpenAI(
        api_key="sk-test-only",
        base_url="https://api.openai.com/v1",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handler), trust_env=False),
    )
    return OpenAIService("sk-test-only", client=client)


def test_transcription_modern_languages_and_prompt():
    captured = []

    def handler(request):
        captured.append(request)
        return httpx.Response(200, json={"text": "こんにちは。", "languages": [{"code": "ja"}]})

    service = service_with(handler)
    assert (
        service.transcribe(b"audio", "gpt-transcribe", "ja,en", "A Japanese lesson.")
        == "こんにちは。"
    )
    body = captured[0].content
    assert captured[0].url.path == "/v1/audio/transcriptions"
    assert b'name="languages[]"' in body
    assert b'name="language"' not in body
    assert b"A Japanese lesson." in body
    assert b"gpt-transcribe" in body
    service.close()


def test_legacy_transcription_sends_single_language():
    requests = []
    service = service_with(
        lambda request: requests.append(request) or httpx.Response(200, json={"text": "hello"})
    )
    service.transcribe(b"audio", "gpt-4o-transcribe", "en")
    assert b'name="language"' in requests[0].content
    assert b"languages[]" not in requests[0].content
    service.close()


def test_translation_is_stateless_and_keeps_input_separate():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "id": "resp_test",
                "object": "response",
                "created_at": 1,
                "model": "gpt-6-luna",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "id": "msg_test",
                        "content": [{"type": "output_text", "text": "Hello.", "annotations": []}],
                    }
                ],
            },
        )

    service = service_with(handler)
    assert service.translate("こんにちは。", "gpt-6-luna", "English", "Keep names.") == "Hello."
    body = json.loads(requests[0].content)
    assert body["input"] == "こんにちは。"
    assert body["store"] is False
    assert body["reasoning"] == {"effort": "low"}
    assert "English" in body["instructions"]
    assert "Keep names." in body["instructions"]
    service.close()


def test_auth_error_does_not_reveal_key():
    service = service_with(
        lambda _: httpx.Response(
            401,
            json={
                "error": {"message": "Incorrect key: sk-test-only", "code": "invalid_api_key"},
            },
        )
    )
    with pytest.raises(ServiceError, match="rejected this API key") as caught:
        service.list_models()
    assert "sk-test-only" not in str(caught.value)
    service.close()


def test_quota_error_explains_credit_problem():
    service = service_with(
        lambda _: httpx.Response(
            429,
            json={
                "error": {"message": "insufficient", "code": "insufficient_quota"},
            },
        )
    )
    with pytest.raises(ServiceError, match="credits"):
        service.translate("hello", "gpt-6-luna", "Japanese")
    service.close()


def test_realtime_only_transcriber_is_rejected_before_upload():
    service = service_with(lambda _: pytest.fail("must not call API"))
    with pytest.raises(ServiceError, match="live-only"):
        service.transcribe(b"audio", "gpt-live-transcribe")
    service.close()


def test_unsupported_legacy_tts_instructions_are_not_silently_ignored():
    service = service_with(lambda _: pytest.fail("must not call API"))
    with pytest.raises(ServiceError, match="cannot follow instructions"):
        service.synthesize("hello", "tts-1", instructions="Speak slowly")
    service.close()


def test_proxy_normalization_does_not_change_environment(monkeypatch):
    for name in ("HTTPS_PROXY", "https_proxy", "all_proxy"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ALL_PROXY", "socks://127.0.0.1:7897")
    assert proxy_url() == "socks5://127.0.0.1:7897"
    import os

    assert os.environ["ALL_PROXY"] == "socks://127.0.0.1:7897"


class FakeSocket:
    def __init__(self, events):
        self.events = iter(events)
        self.sent = []
        self.closed = False

    def send(self, value):
        self.sent.append(json.loads(value))

    def recv(self):
        return json.dumps(next(self.events))

    def settimeout(self, value):
        pass

    def close(self):
        self.closed = True


def test_realtime_tts_waits_for_configuration_and_collects_audio(monkeypatch):
    pcm = b"\x00\x00\x01\x00" * 100
    socket = FakeSocket(
        [
            {"type": "session.created"},
            {"type": "session.updated"},
            {"type": "response.output_audio.delta", "delta": base64.b64encode(pcm).decode()},
            {"type": "response.done", "response": {"status": "completed"}},
        ]
    )
    monkeypatch.setattr("websocket.create_connection", lambda *args, **kwargs: socket)
    result = realtime_speech(
        "sk-test-only", "こんにちは。", "gpt-realtime-2.1-mini", "coral", "Speak gently."
    )
    with wave.open(io.BytesIO(result)) as audio:
        assert audio.getframerate() == 24000
        assert audio.getnchannels() == 1
        assert audio.readframes(audio.getnframes()) == pcm
    assert [event["type"] for event in socket.sent] == [
        "session.update",
        "conversation.item.create",
        "response.create",
    ]
    assert socket.sent[1]["item"]["content"][0]["text"] == "こんにちは。"
    assert socket.closed


def test_realtime_failure_does_not_return_partial_audio(monkeypatch):
    socket = FakeSocket(
        [
            {"type": "session.updated"},
            {"type": "response.output_audio.delta", "delta": "AAAAAA=="},
            {"type": "response.done", "response": {"status": "incomplete"}},
        ]
    )
    monkeypatch.setattr("websocket.create_connection", lambda *args, **kwargs: socket)
    with pytest.raises(ServiceError, match="did not complete"):
        realtime_speech("sk-test-only", "hello", "gpt-realtime-2.1-mini", "coral", "")
    assert socket.closed
