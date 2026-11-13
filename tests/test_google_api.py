"""Google web-service contracts use strokes and plain text, without credentials."""

import json
import math

import httpx
import pytest

from lang_handler import google_api
from lang_handler.errors import ServiceError
from lang_handler.google_api import (
    GOOGLE_HANDWRITING_URL,
    GOOGLE_TRANSLATION_MAX_CHARS,
    GOOGLE_TRANSLATION_URL,
    GoogleService,
)
from lang_handler.ink import InkSnapshot
from lang_handler.results import TranslationResult


def ink():
    return InkSnapshot(300, 200, (((10, 20, 0), (40.125, 70, 25)), ((80, 50, 100),)))


def service_with(handler):
    return GoogleService(client=httpx.Client(transport=httpx.MockTransport(handler), trust_env=False))


def translated(text="Hello."):
    return {"sentences": [{"trans": text, "orig": "こんにちは。"},
                          {"src_translit": "Kon'nichiwa.", "translit": "Hello."}]}


def test_handwriting_sends_ordered_ink_and_preserves_more_than_six_candidates(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    requests = []
    candidates = ["わ", "ね", "ぬ", "あ", "れ", "お", "か", "な", "め", "ん"]

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=["SUCCESS", [["", candidates + ["わ", " "], [], {}]]])

    service = service_with(handler)
    assert service.recognize_handwriting(ink(), "Japanese") == candidates
    body = json.loads(requests[0].content)
    assert body["device"] == "Lang In/Out"
    assert body["requests"] == [{
        "writing_guide": {"writing_area_width": 300, "writing_area_height": 200},
        "ink": [[[10, 40.125], [20, 70], [0, 25]], [[80], [50], [100]]], "language": "ja",
    }]
    assert requests[0].url.params["ime"] == "handwriting"
    assert "authorization" not in requests[0].headers
    service.close()


@pytest.mark.parametrize("escaped,expected", [(True, "A & B"), (False, "A &amp; B")])
def test_candidate_html_entities_are_decoded_only_when_flagged(escaped, expected):
    service = service_with(lambda _: httpx.Response(
        200, json=["SUCCESS", [["", ["A &amp; B"], [], {"is_html_escaped": escaped}]]]
    ))
    assert service.recognize_handwriting(ink(), "ja") == [expected]
    service.close()


@pytest.mark.parametrize("value,language", [
    (b"PNG", "ja"), (InkSnapshot(0, 200, (((1, 1, 0),),)), "ja"),
    (InkSnapshot(300, 200, ()), "ja"), (InkSnapshot(300, 200, ((),)), "ja"),
    (InkSnapshot(300, 200, (((math.nan, 2, 0),),)), "ja"),
    (InkSnapshot(300, 200, (((301, 2, 0),),)), "ja"),
    (InkSnapshot(300, 200, (((1, 2, 20), (3, 4, 10)),)), "ja"),
    (InkSnapshot(300, 200, (((1, 2),),)), "ja"),
    (ink(), ""), (ink(), "auto"), (ink(), "not-a-language-name"),
])
def test_invalid_strokes_or_missing_language_are_rejected_before_upload(value, language):
    service = service_with(lambda _: pytest.fail("invalid input must not be uploaded"))
    with pytest.raises(ServiceError):
        service.recognize_handwriting(value, language)
    service.close()


def test_translation_preserves_source_and_reads_available_pronunciations():
    requests = []
    service = service_with(lambda request: requests.append(request) or httpx.Response(
        200, json={"sentences": [
            {"trans": "Мне нравится ", "orig": "コーヒーが"},
            {"trans": "кофе.", "orig": "好きです。"},
            {"src_translit": "Kōhī ga sukidesu.", "translit": "Mne nravitsya kofe."},
        ], "spell": {}}
    ))
    assert service.translate("コーヒーが好きです。", "Russian") == TranslationResult(
        "Мне нравится кофе.", "Kōhī ga sukidesu.", "Mne nravitsya kofe."
    )
    assert requests[0].url.params["q"] == "コーヒーが好きです。"
    assert requests[0].url.params["tl"] == "ru"
    assert requests[0].url.params["sl"] == "auto"
    assert requests[0].url.params.get_list("dt") == ["t", "rm", "ss"]
    service.close()


def test_translation_does_not_invent_pronunciation_or_source_correction():
    service = service_with(lambda _: httpx.Response(
        200, json={"sentences": [{"trans": "Hello", "orig": "こにちは"}],
                   "spell": {"unknown_field": "unverified correction"}}
    ))
    assert service.translate("こにちは", "English") == TranslationResult("Hello")
    service.close()


def test_translation_empty_and_size_limits_make_no_request():
    service = service_with(lambda _: pytest.fail("must not upload invalid input"))
    assert service.translate(" \n", "English") == TranslationResult("")
    with pytest.raises(ServiceError, match="5,000"):
        service.translate("あ" * (GOOGLE_TRANSLATION_MAX_CHARS + 1), "English")
    with pytest.raises(ServiceError, match="Choose a translation language"):
        service.translate("Hello", "auto")
    service.close()


@pytest.mark.parametrize("payload", [None, [], {"sentences": []},
    {"sentences": [None]}, {"sentences": [{"trans": 42}]},
    {"sentences": [{"src_translit": "hello"}]},
])
def test_translation_malformed_responses_fail_explicitly(payload):
    service = service_with(lambda _: httpx.Response(200, json=payload))
    with pytest.raises(ServiceError):
        service.translate("Hello", "ja")
    service.close()


@pytest.mark.parametrize("status,message", [(401, "denied"), (403, "denied"),
    (429, "limiting"), (503, "unavailable"), (302, "redirected"), (400, "rejected")])
def test_google_failure_has_no_retry_fallback_or_private_error_text(status, message):
    requests = []
    service = service_with(lambda request: requests.append(request) or httpx.Response(
        status, text="private source sk-secret-token proxy://name:password@host"
    ))
    with pytest.raises(ServiceError, match=message) as caught:
        service.translate("Hello", "Japanese")
    assert len(requests) == 1
    assert "private" not in str(caught.value) and "password" not in str(caught.value)
    service.close()


def test_cookies_and_auth_are_never_sent_between_requests():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=translated(), headers={"set-cookie": "tracking=secret; Path=/"})

    service = service_with(handler)
    service.translate("こんにちは。", "en")
    service.translate("こんにちは。", "en")
    assert all("cookie" not in request.headers and "authorization" not in request.headers for request in requests)
    service.close()


def test_each_endpoint_uses_its_own_proxy_resolution_and_bounded_timeouts(monkeypatch):
    resolved, created = [], []
    original_client = httpx.Client

    def resolve(explicit, *, target):
        resolved.append((explicit, target))
        return "http://127.0.0.1:8080"

    def factory(**options):
        created.append(options)
        return original_client(transport=httpx.MockTransport(lambda request: httpx.Response(
            200, json=translated() if request.url.host == "translate.googleapis.com"
            else ["SUCCESS", [["", ["わ"], [], {}]]]
        )), trust_env=False)

    monkeypatch.setattr(google_api, "proxy_url", resolve)
    monkeypatch.setattr(google_api.httpx, "Client", factory)
    service = GoogleService(proxy="http://127.0.0.1:8080")
    service.translate("Hello", "Japanese")
    service.recognize_handwriting(ink(), "ja")
    assert [target for _, target in resolved] == [GOOGLE_TRANSLATION_URL, GOOGLE_HANDWRITING_URL]
    assert all(not row["trust_env"] and not row["follow_redirects"] for row in created)
    assert all(row["timeout"].read == 25 and row["timeout"].connect == 10 for row in created)
    service.close()
    with pytest.raises(ServiceError, match="closed"):
        service.translate("Hello", "Japanese")


def test_context_batch_has_one_translation_anchor_without_guessing_alignment():
    requests = []
    service = service_with(lambda request: requests.append(request) or httpx.Response(
        200, json=translated("It is sunny today.")
    ))
    revisions = service.revise_translation([(10, "今日は"), (11, "晴れです。")], "English", "Old text")
    assert requests[0].url.params["q"] == "今日は晴れです。"
    assert [item.segment_id for item in revisions] == [10, 11]
    assert [item.source_text for item in revisions] == ["今日は", "晴れです。"]
    assert revisions[0].result.translation == "It is sunny today."
    assert revisions[1].result == TranslationResult("")
    service.close()
