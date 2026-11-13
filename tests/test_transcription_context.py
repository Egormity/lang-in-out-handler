import httpx
import pytest
from openai import OpenAI

from lang_handler.api import OpenAIService
from lang_handler.errors import ServiceError
from lang_handler.prompts import single_prompt
from lang_handler.transcription_context import recognized_text, transcription_prompt


def test_no_context_keeps_existing_prompt():
    assert transcription_prompt("Keep names.") == single_prompt("input_instructions", "Keep names.")


def test_context_is_bounded_and_kept_separate_from_custom_instructions():
    prompt = transcription_prompt("Keep names.", "OLD_PREFIX" + "日" * 1500)
    assert "OLD_PREFIX" not in prompt
    assert prompt.count("日") == 1500
    assert prompt.startswith(single_prompt("input_instructions", "Keep names."))
    assert "Do not repeat the previous transcript" in prompt
    assert "unless those words are spoken again" in prompt


@pytest.mark.parametrize("value", ["Hello.", "こんにちは。", "то", "3", "と。"])
def test_recognized_words_across_scripts_are_preserved(value):
    assert recognized_text(value) == value


@pytest.mark.parametrize("value", ["", "♪♫", "…—。", "🙂"])
def test_punctuation_and_music_notes_alone_are_empty(value):
    assert recognized_text(value) == ""


@pytest.mark.parametrize("value", [None, [], 1])
def test_invalid_response_is_an_error(value):
    with pytest.raises(ServiceError, match="invalid audio transcription"):
        recognized_text(value)


def test_api_transcription_supplies_prior_context_and_original_instructions():
    requests = []
    client = OpenAI(
        api_key="sk-test-only", max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(
            lambda request: requests.append(request) or httpx.Response(200, json={"text": "現在。"})
        )),
    )
    service = OpenAIService("sk-test-only", client=client)
    try:
        assert service.transcribe(
            b"audio", "gpt-transcribe", "ja", "Keep names.", context="以前。"
        ) == "現在。"
        body = requests[0].content.decode()
        assert "以前。" in body
        assert "Keep names." in body
        assert "Do not repeat" in body
    finally:
        service.close()
