"""Structured translations keep pronunciation text distinct and honor reasoning."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from lang_handler.api import OpenAIService
from lang_handler.errors import ServiceError
from lang_handler.reasoning import reasoning_options, supports_reasoning
from lang_handler.results import TranslationResult


def service_result(output):
    client = Mock()
    client.responses.create.return_value = SimpleNamespace(output_text=output)
    return OpenAIService("test-only", client=client), client


@pytest.mark.parametrize("effort", ["low", "medium", "high"])
def test_requested_reasoning_and_pronunciations_round_trip(effort):
    service, client = service_result(json.dumps({
        "translation": " Coffee. ",
        "source_pronunciation": " Kōhī. ",
        "translation_pronunciation": " /ˈkɒfi/ ",
    }))
    result = service.translate("コーヒー。", "gpt-6-luna", "English", reasoning=effort)
    assert result == TranslationResult("Coffee.", "Kōhī.", "/ˈkɒfi/")
    assert client.responses.create.call_args.kwargs["reasoning"] == {"effort": effort}


@pytest.mark.parametrize("payload", [
    "plain text",
    "[]",
    "null",
    '{"translation": "Hello"}',
    '{"translation": "Hello", "source_pronunciation": null, "translation_pronunciation": "hello"}',
    '{"translation": " ", "source_pronunciation": "a", "translation_pronunciation": "b"}',
    '{"translation": 10, "source_pronunciation": "a", "translation_pronunciation": "b"}',
    '{"translation": "hi", "source_pronunciation": "a", "translation_pronunciation": "b", "extra": "c"}',
])
def test_malformed_result_is_not_rendered_as_a_translation(payload):
    service, _ = service_result(payload)
    with pytest.raises(ServiceError, match="invalid translation result"):
        service.translate("こんにちは", "gpt-6-luna", "English")


def test_nonlinguistic_text_can_return_empty_pronunciation():
    service, _ = service_result(
        '{"translation": "!", "source_pronunciation": "", "translation_pronunciation": ""}'
    )
    assert service.translate("!", "gpt-6-luna", "English") == TranslationResult("!")


def test_empty_text_and_missing_target_do_not_spend_api_credit():
    service, client = service_result("unused")
    assert service.translate("  ", "gpt-6-luna", "English") == TranslationResult("")
    with pytest.raises(ServiceError, match="target language"):
        service.translate("hello", "gpt-6-luna", " ")
    client.responses.create.assert_not_called()


@pytest.mark.parametrize("model", ["gpt-4.1", "gpt-4o", "gpt-5-chat-latest", "custom-model"])
def test_nonreasoning_models_never_receive_effort(model):
    service, client = service_result(
        '{"translation": "Hi", "source_pronunciation": "Hai", "translation_pronunciation": "/haɪ/"}'
    )
    service.translate("はい", model, "English", reasoning="high")
    assert "reasoning" not in client.responses.create.call_args.kwargs
    assert not supports_reasoning(model)


def test_invalid_effort_fails_before_network():
    service, client = service_result("unused")
    with pytest.raises(ServiceError, match="Low, Medium, or High"):
        service.translate("hello", "gpt-6-luna", "Japanese", reasoning="made-up")
    client.responses.create.assert_not_called()


def test_original_gpt5_pro_only_accepts_high_effort():
    with pytest.raises(ServiceError, match="only supports High"):
        reasoning_options("gpt-5-pro", "medium")
    assert reasoning_options("gpt-5-pro-2025-10-06", "high") == {"reasoning": {"effort": "high"}}
    assert reasoning_options("gpt-5.5-pro", "medium") == {"reasoning": {"effort": "medium"}}
