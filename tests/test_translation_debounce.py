"""Debounced edits send the newest text once, with explicit manual/off behavior."""

from dataclasses import replace

from PySide6.QtTest import QSignalSpy

from lang_handler.results import TranslationResult
from lang_handler.settings import Settings
from lang_handler.ui.text_pages import TranslatePage


def page(qtbot, **options):
    widget = TranslatePage(Settings(translation_debounce_ms=200, **options))
    qtbot.addWidget(widget)
    return widget


def test_typing_restarts_delay_and_sends_only_latest_text(qtbot):
    widget = page(qtbot)
    sent = QSignalSpy(widget.automatic_requested)
    widget.source.text.setPlainText("first")
    qtbot.wait(120)
    widget.source.text.setPlainText("latest")
    qtbot.wait(120)
    assert sent.count() == 0
    qtbot.waitUntil(lambda: sent.count() == 1)
    assert sent.at(0) == ["latest"]
    widget.set_result(TranslationResult("translated"), "latest", "English")
    qtbot.wait(250)
    assert sent.count() == 1


def test_manual_send_and_controller_request_cancel_automatic_duplicate(qtbot):
    widget = page(qtbot)
    automatic, manual = QSignalSpy(widget.automatic_requested), QSignalSpy(widget.requested)
    widget.source.text.setPlainText("hello")
    widget.run.click()
    assert manual.count() == 1
    qtbot.wait(250)
    assert automatic.count() == 0
    widget.source.text.setPlainText("clipboard shortcut")
    widget.request_started("clipboard shortcut")
    qtbot.wait(250)
    assert automatic.count() == 0


def test_disabling_and_empty_source_cancel_scheduled_translation(qtbot):
    widget = page(qtbot)
    sent = QSignalSpy(widget.automatic_requested)
    widget.source.text.setPlainText("hello")
    widget.apply_settings(replace(widget.settings, translation_auto_send=False))
    qtbot.wait(250)
    assert sent.count() == 0
    manual = QSignalSpy(widget.requested)
    widget.run.click()
    assert manual.count() == 1
    assert manual.at(0) == ["hello"]
    widget.apply_settings(replace(widget.settings, translation_auto_send=True))
    widget.source.text.setPlainText("  ")
    qtbot.wait(250)
    assert sent.count() == 0
    widget.source.text.setPlainText("next")
    widget.shutdown()
    qtbot.wait(250)
    assert sent.count() == 0


def test_target_and_provider_changes_debounce_without_unrelated_setting_requests(qtbot):
    widget = page(qtbot)
    sent = QSignalSpy(widget.automatic_requested)
    widget.source.text.setPlainText("hello")
    widget.target.setCurrentText("Japanese")
    qtbot.waitUntil(lambda: sent.count() == 1)
    assert widget.settings.target_language == "Japanese"
    widget.apply_settings(replace(widget.settings, font_size=30))
    qtbot.wait(250)
    assert sent.count() == 1
    widget.apply_settings(replace(widget.settings, translation_provider="openai"))
    qtbot.waitUntil(lambda: sent.count() == 2)


def test_read_aloud_source_never_auto_translates_until_edited(qtbot):
    widget = page(qtbot)
    sent = QSignalSpy(widget.automatic_requested)
    widget.set_source_text("Read this only", automatic=False)
    widget.apply_settings(replace(widget.settings, target_language="Japanese"))
    qtbot.wait(250)
    assert sent.count() == 0
    widget.source.text.insertPlainText(" edited")
    qtbot.waitUntil(lambda: sent.count() == 1)
