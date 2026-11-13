"""Real controller saves both languages before one replacement translation runs."""

import threading
from dataclasses import replace

import pytest
from PySide6.QtTest import QSignalSpy

from lang_handler.results import TranslationResult

pytest_plugins = ("test_controller",)


@pytest.mark.parametrize("automatic", [False, True])
def test_swap_replaces_queued_translation_ignores_old_completion_and_has_no_trailing_request(
    controller, qtbot, monkeypatch, automatic,
):
    c = controller
    c.save_settings(replace(c.settings, translation_provider="google",
                            translation_source_language="ja", translation_auto_send=automatic,
                            translation_debounce_ms=200))
    started, release = threading.Event(), threading.Event()
    calls = []

    class Service:
        def __init__(self, **kwargs):
            pass

        def translate(self, text, target, *, source_language=""):
            calls.append((text, target, source_language))
            if len(calls) == 1:
                started.set()
                assert release.wait(4)
                return TranslationResult("obsolete translation", source_language="ja")
            return TranslationResult("逆翻訳", source_language="en")

        def close(self):
            pass

    monkeypatch.setattr("lang_handler.text_translation.GoogleService", Service)
    page = c.window.pages["translate"]
    page.set_source_text("first", automatic=False)
    page.set_result(TranslationResult("Hello", source_language="ja"))
    page.send()
    try:
        qtbot.waitUntil(started.is_set)
        page.source.text.setPlainText("queued")
        page.send()
        assert c.workflows.translation.pending.text == "queued"
        page.swap_button.click()
        assert page.source.text.toPlainText() == "Hello"
        assert page.result.text.toPlainText() == "queued"
        assert c.workflows.translation.pending.text == "Hello"
        assert c.settings.translation_source_language == "en"
        assert c.settings.target_language == "Japanese"
        saved = c.store.load_settings()
        assert saved.translation_source_language == "en" and saved.target_language == "Japanese"
        release.set()
        qtbot.waitUntil(lambda: c.workflows.translation_job is None)
        qtbot.wait(250)
        assert calls == [("first", "English", "ja"), ("Hello", "Japanese", "en")]
        assert page.source.text.toPlainText() == "Hello"
        assert page.result.text.toPlainText() == "逆翻訳"
    finally:
        release.set()


@pytest.mark.parametrize("automatic", [False, True])
@pytest.mark.parametrize("source_language", ["", "ja"])
def test_swap_save_failure_restores_languages_preserves_text_and_does_not_translate(
    controller, qtbot, monkeypatch, automatic, source_language,
):
    c = controller
    c.save_settings(replace(c.settings, translation_provider="google",
                            translation_source_language=source_language, translation_auto_send=automatic,
                            translation_debounce_ms=200))
    page = c.window.pages["translate"]
    page.source.text.setPlainText("こんにちは")
    page.set_result(TranslationResult("Hello", source_language="ja"))
    manual, auto = QSignalSpy(page.requested), QSignalSpy(page.automatic_requested)
    errors = []
    monkeypatch.setattr(c, "fail", errors.append)

    def fail_save(settings):
        raise OSError("synthetic save failure")

    monkeypatch.setattr(c.store, "save_settings", fail_save)
    page.swap_button.click()
    assert page.source_language.currentData() == source_language
    assert page.target.currentText() == "English"
    assert page.source.text.toPlainText() == "こんにちは"
    assert page.result.text.toPlainText() == "Hello"
    assert c.settings.translation_source_language == source_language
    assert c.settings.target_language == "English"
    assert len(errors) == 1 and "save failure" in errors[0]
    assert page.swap_button.isEnabled()  # Failed saves keep detected language available for retry.
    qtbot.wait(250)
    assert manual.count() == auto.count() == 0
    assert c.workflows.translation_job is None
