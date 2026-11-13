"""Validate contextual caption contracts without sending audio or network requests."""

import json
from types import SimpleNamespace

import pytest

from lang_handler.api import OpenAIService
from lang_handler.caption_context import trim_context
from lang_handler.errors import ServiceError
from lang_handler.results import CaptionRevision, TranslationResult


def client_with(payload):
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(output_text=payload if isinstance(payload, str) else json.dumps(payload))

    client = SimpleNamespace(responses=SimpleNamespace(create=create), close=lambda: None)
    return OpenAIService("unit-test-key", client=client), calls


def item(segment_id, translation="bridge"):
    return {"segment_id": segment_id, "translation": translation,
            "source_pronunciation": "hashi", "translation_pronunciation": "/brɪdʒ/"}


def test_contextual_api_returns_revisions_in_source_order_and_keeps_source_authoritative():
    service, calls = client_with({"items": [item(-2), item(-1, "cross the bridge")]})
    rows = service.revise_captions([(-1, "はし"), (-2, "を渡る")], "gpt-6-luna", "English", "Keep names.", "high")
    assert rows == [
        CaptionRevision(-1, "はし", TranslationResult("cross the bridge", "hashi", "/brɪdʒ/")),
        CaptionRevision(-2, "を渡る", TranslationResult("bridge", "hashi", "/brɪdʒ/")),
    ]
    request = calls[0]
    assert request["store"] is False
    assert request["reasoning"] == {"effort": "high"}
    assert "revise" in request["instructions"]
    assert "Keep names." not in request["instructions"]
    assert json.loads(request["input"])["custom_instructions"] == "Keep names."
    assert json.loads(request["input"])["segments"] == [
        {"segment_id": -1, "text": "はし"}, {"segment_id": -2, "text": "を渡る"}
    ]
    assert request["text"]["format"]["strict"]
    assert request["text"]["format"]["schema"]["properties"]["items"]["maxItems"] == 2


@pytest.mark.parametrize("payload", [
    "not json", [], {}, {"items": []}, {"items": [item(1)]},
    {"items": [item(1), item(1)]}, {"items": [item(1), item(99)]},
    {"items": [item(True), item(2)]}, {"items": [item(1), item(2, "")]},
    {"items": [item(1), {**item(2), "source_text": "invented"}]},
    {"items": [item(1), {**item(2), "source_pronunciation": 123}]},
])
def test_invalid_or_incomplete_revision_set_is_rejected_atomically(payload):
    service, _ = client_with(payload)
    with pytest.raises(ServiceError, match="invalid caption revisions"):
        service.revise_captions([(1, "first"), (2, "second")], "gpt-6-luna", "English")


@pytest.mark.parametrize("segments", [[], [(1, "")], [(True, "text")], [(1, "one"), (1, "two")], [(i, "text") for i in range(7)]])
def test_invalid_source_context_makes_no_api_call(segments):
    service, calls = client_with({"items": []})
    with pytest.raises(ServiceError):
        service.revise_captions(segments, "gpt-6-luna", "English")
    assert not calls


def test_context_is_bounded_by_recent_segments_and_characters_without_truncating_a_recording():
    segments = [(i, str(i)) for i in range(20)]
    assert trim_context(segments) == segments[-6:]
    assert trim_context([(1, "a" * 3500), (2, "b" * 3500)]) == [(2, "b" * 3500)]
    assert trim_context([(1, "a"), (2, "b" * 9000)]) == [(2, "b" * 9000)]
    assert segments == [(i, str(i)) for i in range(20)]


def test_nonreasoning_model_omits_reasoning_option():
    service, calls = client_with({"items": [item(1)]})
    service.revise_captions([(1, "はし")], "gpt-4.1", "English")
    assert "reasoning" not in calls[0]


def test_words_can_move_between_adjacent_fragments_without_duplicating_the_passage():
    empty = {**item(1, ""), "translation_pronunciation": ""}
    service, _ = client_with({"items": [empty, item(2, "I crossed the bridge.")]})
    result = service.revise_captions([(1, "はしを"), (2, "渡りました。")], "gpt-6-luna", "English")
    assert result[0].result.translation == ""
    assert result[0].result.source_pronunciation == "hashi"
    assert result[1].result.translation == "I crossed the bridge."


def test_entirely_empty_translation_passage_is_rejected():
    empty = lambda n: {**item(n, ""), "translation_pronunciation": ""}
    service, _ = client_with({"items": [empty(1), empty(2)]})
    with pytest.raises(ServiceError, match="invalid caption revisions"):
        service.revise_captions([(1, "はしを"), (2, "渡りました。")], "gpt-6-luna", "English")
