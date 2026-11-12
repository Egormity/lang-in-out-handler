"""UI contract checks without audio devices, API calls, or stored secrets."""

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QLineEdit

from lang_handler.settings import Settings
from lang_handler.ui.main_window import MainWindow
from lang_handler.ui.overlay import CaptionOverlay


def test_capture_commits_instructions_before_start(qtbot):
    window = MainWindow(Settings(), True)
    qtbot.addWidget(window)
    order = []
    window.settings_saved.connect(
        lambda prefs: order.append(("settings", prefs.output_instructions))
    )
    window.capture_requested.connect(lambda mode, chunks: order.append((mode, chunks)))
    page = window.pages["output"]
    page.instructions.setPlainText("Names: Sakura and Aoi")
    page.start_button.click()
    assert order == [("settings", "Names: Sakura and Aoi"), ("output", True)]


def test_split_results_do_not_duplicate_transcript(qtbot):
    window = MainWindow(Settings(), True)
    qtbot.addWidget(window)
    window.append_result("output", "こんにちは")
    window.append_result("output", "", "Hello")
    page = window.pages["output"]
    assert page.results.text.toPlainText() == "こんにちは"
    assert page.translations.text.toPlainText() == "Hello"
    window.set_recording("output", True)
    assert not page.start_button.isEnabled()
    assert page.stop_button.isEnabled()


def test_overlay_visibility_does_not_disable_translation(qtbot):
    overlay = CaptionOverlay(Settings())
    qtbot.addWidget(overlay)
    overlay.show()
    overlay.translation_toggle.setChecked(False)
    assert not overlay.settings.translation_visible
    assert overlay.settings.translation_enabled
    assert overlay.translation.isHidden()
    overlay.transcript_toggle.setChecked(False)
    assert overlay.empty.isVisible()
    overlay.append_caption("日本語", "Japanese")
    overlay.translation_toggle.setChecked(True)
    assert overlay.translation.text.toPlainText() == "Japanese"
    assert overlay.translation.isVisible()
    assert overlay.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    stopped = QSignalSpy(overlay.stop_requested)
    overlay.close()
    assert not overlay.isVisible()
    assert stopped.count() == 0


def test_preferences_key_mask_and_model_refresh(qtbot):
    window = MainWindow(Settings(), False)
    qtbot.addWidget(window)
    preferences = window.pages["preferences"]
    assert preferences.api_key.echoMode() == QLineEdit.EchoMode.Password
    preferences.models["input_model"].setCurrentText("custom-transcribe-model")
    window.set_models(["gpt-transcribe", "gpt-live-transcribe", "gpt-6-luna", "gpt-4o-mini-tts"])
    assert preferences.models["input_model"].currentText() == "custom-transcribe-model"
    assert preferences.models["input_model"].findText("gpt-live-transcribe") < 0
    assert preferences.models["translation_model"].findText("gpt-6-luna") >= 0


def test_saved_preferences_keep_unsaved_mode_instructions(qtbot):
    window = MainWindow(Settings(), True)
    qtbot.addWidget(window)
    window.pages["translate"].instructions.setPlainText("Use polite Russian.")
    window._save_preferences(replace(window.settings, target_language="Russian"))
    assert window.settings.target_language == "Russian"
    assert window.settings.translation_instructions == "Use polite Russian."


def test_history_selection_and_navigation(qtbot):
    window = MainWindow(Settings(), True)
    qtbot.addWidget(window)
    window.set_history(
        [
            {
                "id": 1,
                "mode": "output",
                "created_at": "2026-11-13",
                "source_text": "こんにちは",
                "translated_text": "Hello",
                "model": "test",
            }
        ]
    )
    window.show_page("history")
    page = window.pages["history"]
    page.table.selectRow(0)
    assert "Hello" in page.detail.text.toPlainText()
    assert window.stack.currentWidget() is page


def test_audio_level_exposes_silence_and_signal(qtbot):
    window = MainWindow(Settings(), True)
    qtbot.addWidget(window)
    window.set_level("input", 0.1)
    assert window.pages["input"].level.value() == 40
    assert "-20 dB" in window.pages["input"].level.text()
    window.set_level("output", 0)
    assert window.pages["output"].level.text() == "No audio detected"
    window.set_level("input", float("nan"))
    assert window.pages["input"].level.value() == 0
    window.set_level("input", 2)
    assert window.pages["input"].level.value() == 60
    window.set_recording("input", False)
    assert window.pages["input"].level.value() == 0


def test_device_names_are_saved_and_friendly_labels_displayed(qtbot):
    window = MainWindow(Settings(microphone_source="usb.mic"), True)
    qtbot.addWidget(window)
    devices = [
        {"name": "usb.mic", "description": "USB Microphone", "is_monitor": False},
        {"name": "speakers.monitor", "description": "Desk speakers", "is_monitor": True},
    ]
    window.set_sources(devices)
    preferences = window.pages["preferences"]
    assert preferences.microphone_source.currentText() == "USB Microphone"
    assert preferences.microphone_source.findText("Desk speakers") < 0
    preferences.output_source.setCurrentText("Desk speakers")
    selected = preferences.collect()
    assert selected.microphone_source == "usb.mic"
    assert selected.output_source == "speakers.monitor"
    window.update_settings(selected)
    window.set_sources(devices)
    assert preferences.output_source.currentText() == "Desk speakers"
    preferences.microphone_source.setCurrentIndex(0)
    assert preferences.collect().microphone_source == ""
    preferences.output_source.setEditText("custom.monitor")
    assert preferences.collect().output_source == "custom.monitor"


def test_settings_update_does_not_emit_feedback_and_key_clears(qtbot):
    window = MainWindow(Settings(), True)
    qtbot.addWidget(window)
    settings = QSignalSpy(window.settings_saved)
    window.settings_saved.connect(window.update_settings)
    window.sync_mode_settings()
    assert settings.count() == 1
    preferences = window.pages["preferences"]
    saved_keys = QSignalSpy(window.key_saved)
    preferences.api_key.setText("unit-test-placeholder")
    preferences._save_key()
    assert preferences.api_key.text() == ""
    assert saved_keys.count() == 1
    window.set_key_status("No API key saved.")
    assert window.connection_badge.text() == "API key needed"
    window.set_key_status("API key removed.")
    assert window.connection_badge.text() == "API key needed"
    window.set_key_status("Saved in system keyring")
    assert window.connection_badge.text() == "Key saved"


def test_overlay_clear_preserves_session_controls(qtbot):
    overlay = CaptionOverlay(Settings())
    qtbot.addWidget(overlay)
    overlay.append_caption("日本語", "Japanese")
    stopped = QSignalSpy(overlay.stop_requested)
    overlay.clear_button.click()
    assert overlay.transcript.text.toPlainText() == ""
    assert overlay.translation.text.toPlainText() == ""
    assert stopped.count() == 0
    assert overlay.settings.translation_enabled
    assert overlay.transcript_toggle.focusPolicy() == Qt.FocusPolicy.TabFocus


def test_remove_key_and_tts_model_choices(qtbot):
    window = MainWindow(Settings(), True)
    qtbot.addWidget(window)
    preferences = window.pages["preferences"]
    keys = QSignalSpy(window.key_saved)
    preferences.api_key.setText("unsaved-placeholder")
    preferences.remove_key_button.click()
    assert keys.at(0) == [""]
    assert preferences.api_key.text() == ""
    window.set_key_status("API key removed.")
    assert not preferences.remove_key_button.isEnabled()
    window.set_models(
        [
            "gpt-realtime-2.1-mini",
            "gpt-realtime-translate",
            "gpt-realtime-whisper",
            "gpt-live-transcribe",
            "gpt-4o-mini-tts",
        ]
    )
    choices = preferences.models["tts_model"]
    assert choices.findText("gpt-realtime-2.1-mini") >= 0
    assert choices.findText("gpt-realtime-translate") < 0
    assert choices.findText("gpt-realtime-whisper") < 0
    assert window.pages["translate"].instructions.tabChangesFocus()


def test_speech_replay_is_forwarded_to_controller(qtbot):
    window = MainWindow(Settings(), True)
    qtbot.addWidget(window)
    replay = QSignalSpy(window.speech_replay_requested)
    generated = QSignalSpy(window.speech_requested)
    page = window.pages["tts"]
    assert not page.play.isEnabled()
    window.set_speech("/tmp/unit-test-speech.wav")
    page.play.click()
    assert replay.count() == 1
    assert replay.at(0) == ["/tmp/unit-test-speech.wav"]
    assert generated.count() == 0
