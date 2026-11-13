"""Source language is explicit provider input and part of the translation identity."""

import json
import threading
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest

from lang_handler.api import OpenAIService
from lang_handler.errors import ServiceError
from lang_handler.google_api import GoogleService
from lang_handler.results import TranslationResult
from lang_handler.settings import Settings
from lang_handler.text_translation import request_signature
from lang_handler.translation_context import translation_configuration
from lang_handler.translation_languages import resolved_source_language

pytest_plugins = ("test_controller",)


def openai_result(source):
    client = Mock()
    client.responses.create.return_value = SimpleNamespace(output_text=json.dumps({
        "translation": "Hello", "source_pronunciation": "Konnichiwa",
        "translation_pronunciation": "hello", "source_correction": "",
        "source_language": source,
    }))
    return OpenAIService("test-key", client=client), client


def test_source_setting_round_trips_without_altering_caption_configuration():
    initial = Settings()
    assert initial.translation_source_language == ""
    explicit = replace(initial, translation_source_language="ru")
    assert Settings.from_dict(explicit.to_dict()).translation_source_language == "ru"
    assert explicit.output_language == initial.output_language
    assert translation_configuration(explicit) == translation_configuration(initial)
    for provider in ("google", "openai"):
        settings = replace(initial, translation_provider=provider)
        assert request_signature("same", settings, "key") != request_signature(
            "same", replace(settings, translation_source_language="ja"), "key"
        )


@pytest.mark.parametrize("reported,expected", [
    ("JA", "ja"), ("zh-CN", "zh"), ("zh-TW", "zh"), ("pt-BR", "pt"),
    ("iw", "he"), ("in", "id"), ("jw", "jv"), ("und", ""),
    ("mul", ""), ("zxx", ""), ("", ""), (None, ""), ({}, ""), ("Japanese", ""),
])
def test_detected_codes_are_normalized_without_guessing(reported, expected):
    assert resolved_source_language(reported) == expected


def test_openai_detects_original_language_and_requests_code_in_structured_output():
    service, client = openai_result("JA")
    result = service.translate("こんにちは", "gpt-6-luna", "English")
    assert result.source_language == "ja"
    request = client.responses.create.call_args.kwargs
    assert "Auto-detect" in request["instructions"]
    assert "ORIGINAL source" in request["instructions"]
    assert "source_language" in request["text"]["format"]["schema"]["required"]


def test_openai_explicit_source_is_authoritative_and_kept_separate_from_custom_prompt():
    service, client = openai_result("en")
    result = service.translate("こんにちは", "gpt-6-luna", "English", "Keep names.",
                               source_language="ja")
    assert result.source_language == "ja"
    request = client.responses.create.call_args.kwargs
    assert "Selected source language: ja" in request["instructions"]
    assert "do not replace the selected source language" in request["instructions"]
    assert "Keep names." not in request["instructions"]
    assert json.loads(request["input"])["custom_instructions"] == "Keep names."


def test_invalid_source_is_rejected_before_openai_request():
    service, client = openai_result("ja")
    with pytest.raises(ServiceError, match="source language"):
        service.translate("hello", "gpt-6-luna", "English", source_language="not a language")
    client.responses.create.assert_not_called()


@pytest.mark.parametrize("selected,reported,query,resolved", [
    ("", "ja", "auto", "ja"), ("", "zh-TW", "auto", "zh"),
    ("ja", "en", "ja", "ja"), ("zh", "zh-CN", "zh-CN", "zh"),
    ("", None, "auto", ""), ("", {}, "auto", ""),
])
def test_google_explicit_or_detected_source_round_trips(selected, reported, query, resolved):
    requests = []
    service = GoogleService(client=httpx.Client(transport=httpx.MockTransport(
        lambda request: requests.append(request) or httpx.Response(
            200, json={"sentences": [{"trans": "Hello", "orig": "こんにちは"}], "src": reported}
        )
    )))
    try:
        result = service.translate("こんにちは", "English", source_language=selected)
        assert requests[0].url.params["sl"] == query
        assert requests[0].url.params["tl"] == "en"
        assert result.source_language == resolved
    finally:
        service.close()


@pytest.mark.parametrize("provider", ["google", "openai"])
def test_selected_source_reaches_provider_and_resolved_language_reaches_page(
    controller, qtbot, monkeypatch, provider,
):
    c = controller
    c.save_settings(replace(c.settings, translation_provider=provider,
                            translation_source_language="ja"))
    calls, displayed = [], []

    class Service:
        def __init__(self, *args, **kwargs):
            pass

        def translate(self, text, *args, source_language=""):
            calls.append(source_language)
            return TranslationResult("Hello", source_language=source_language)

        def close(self):
            pass

    monkeypatch.setattr("lang_handler.text_translation.GoogleService", Service)
    monkeypatch.setattr("lang_handler.text_translation.OpenAIService", Service)
    original = c.window.set_translation
    monkeypatch.setattr(c.window, "set_translation",
                        lambda result, *args: displayed.append(result) or original(result, *args))
    c.window.set_source_text("translate", "こんにちは")
    c.workflows.translate("こんにちは")
    qtbot.waitUntil(lambda: c.workflows.translation_job is None)
    assert calls == ["ja"]
    assert displayed == [TranslationResult("Hello", source_language="ja")]
    assert c.window.pages["translate"].result.text.toPlainText() == "Hello"


@pytest.mark.parametrize("old_error", [False, True])
def test_changing_only_source_drops_stale_result_and_runs_newest_request(
    controller, qtbot, monkeypatch, old_error,
):
    c = controller
    c.save_settings(replace(c.settings, translation_provider="google",
                            translation_source_language="ja"))
    started, release = threading.Event(), threading.Event()
    calls, displayed, errors = [], [], []

    class Service:
        def __init__(self, **kwargs):
            pass

        def translate(self, text, target, *, source_language=""):
            calls.append(source_language)
            if len(calls) == 1:
                started.set()
                assert release.wait(4)
                if old_error:
                    raise ServiceError("obsolete translation failed")
            return TranslationResult(source_language, source_language=source_language)

        def close(self):
            pass

    monkeypatch.setattr("lang_handler.text_translation.GoogleService", Service)
    original = c.window.set_translation
    monkeypatch.setattr(c.window, "set_translation",
                        lambda result, *args: displayed.append(result) or original(result, *args))
    monkeypatch.setattr(c, "fail", errors.append)
    c.window.set_source_text("translate", "same ambiguous text")
    c.workflows.translate("same ambiguous text")
    try:
        qtbot.waitUntil(started.is_set)
        c.save_settings(replace(c.settings, translation_source_language="ru"))
        c.workflows.translate("same ambiguous text")
        release.set()
        qtbot.waitUntil(lambda: c.workflows.translation_job is None)
        assert calls == ["ja", "ru"]
        assert [result.source_language for result in displayed] == ["ru"]
        assert c.window.pages["translate"].result.text.toPlainText() == "ru"
        assert not errors
    finally:
        release.set()


def test_auto_result_cache_is_not_reused_for_different_source_language(
    controller, qtbot, monkeypatch,
):
    c = controller
    c.save_settings(replace(c.settings, translation_provider="google",
                            translation_source_language="ja", translation_auto_send=True))
    calls = []

    class Service:
        def __init__(self, **kwargs):
            pass

        def translate(self, text, target, *, source_language=""):
            calls.append(source_language)
            return TranslationResult(source_language, source_language=source_language)

        def close(self):
            pass

    monkeypatch.setattr("lang_handler.text_translation.GoogleService", Service)
    c.window.set_source_text("translate", "same ambiguous text")
    for language in ("ja", "ru"):
        c.save_settings(replace(c.settings, translation_source_language=language))
        c.workflows.translate("same ambiguous text", automatic=True)
        qtbot.waitUntil(lambda: c.workflows.translation_job is None)
    assert calls == ["ja", "ru"]
    assert c.window.pages["translate"].result.text.toPlainText() == "ru"
