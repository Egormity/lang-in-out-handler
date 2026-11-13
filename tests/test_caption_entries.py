"""Continuous caption panes retain speech actions and minimal floating controls."""

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QCheckBox, QComboBox, QSpinBox

from lang_handler.settings import Settings
from lang_handler.ui.history import HistoryPage
from lang_handler.ui.overlay import CaptionOverlay


def test_caption_visibility_and_pin_only_change_through_preferences(qtbot):
    settings = Settings()
    overlay = CaptionOverlay(settings)
    qtbot.addWidget(overlay)
    overlay.show()
    assert not overlay.findChildren(QCheckBox)
    assert all(combo.objectName() == "audioSpeed" for combo in overlay.findChildren(QComboBox))
    assert not overlay.findChildren(QSpinBox)
    assert overlay.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    overlay.update_settings(replace(settings, transcript_visible=False, translation_visible=False))
    assert overlay.transcript.isHidden()
    assert overlay.translation.isHidden()
    assert overlay.empty.isVisible()
    overlay.append_caption("日本語", "Japanese")
    overlay.update_settings(settings)
    assert overlay.translation.isVisible()
    assert overlay.translation.toPlainText() == "Japanese"


def test_caption_speech_stop_is_separate_from_capture_and_clear(qtbot):
    overlay = CaptionOverlay(Settings())
    qtbot.addWidget(overlay)
    speech = QSignalSpy(overlay.speech_requested)
    stop_audio = QSignalSpy(overlay.speech_stop_requested)
    stop_capture = QSignalSpy(overlay.stop_requested)
    overlay.append_caption("日本語", "Japanese")
    overlay.translation.speak.click()
    assert speech.at(0) == ["Japanese"]
    overlay.set_speech_active(True)
    assert not overlay.stop_audio_button.isHidden()
    overlay.stop_audio_button.click()
    assert stop_audio.count() == 1
    assert stop_capture.count() == 0
    overlay.clear_button.click()
    assert overlay.transcript.toPlainText() == ""
    assert overlay.translation.toPlainText() == ""
    assert stop_capture.count() == 0
    overlay.stop_button.click()
    assert stop_capture.count() == 1


def test_history_speaks_original_and_translation_separately(qtbot):
    history = HistoryPage()
    qtbot.addWidget(history)
    speech = QSignalSpy(history.speech_requested)
    history.set_entries([
        {"id": 1, "mode": "output", "source_text": "こんにちは", "translated_text": "Hello"},
        {"id": 2, "mode": "input", "source_text": "Good morning", "translated_text": ""},
    ])
    history.detail.speak.click()
    history.translation.speak.click()
    assert speech.at(0) == ["こんにちは"]
    assert speech.at(1) == ["Hello"]
    history.table.selectRow(1)
    assert history.translation.isHidden()
    assert history.translation.text.toPlainText() == ""
