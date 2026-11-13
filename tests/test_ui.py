"""UI contract checks without audio devices, API calls, or stored secrets."""

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QLineEdit, QProgressBar

from lang_handler.settings import Settings
from lang_handler.ui.main_window import MainWindow
from lang_handler.ui.overlay import CaptionOverlay


def test_capture_uses_saved_preference_instructions(qtbot):
    window = MainWindow(Settings(), True)
    qtbot.addWidget(window)
    window.settings_saved.connect(window.settings_save_succeeded)
    order = []
    window.settings_saved.connect(
        lambda prefs: order.append(("settings", prefs.output_instructions))
    )
    window.capture_requested.connect(lambda mode, chunks: order.append((mode, chunks)))
    page = window.pages["output"]
    preferences = page.tool_settings
    preferences.instructions["output_instructions"].setPlainText("Names: Sakura and Aoi")
    preferences.save_button.click()
    order.clear()
    page.start_button.click()
    assert order == [("output", True)]
    assert window.settings.output_instructions == "Names: Sakura and Aoi"


def test_split_results_do_not_duplicate_transcript(qtbot):
    window = MainWindow(Settings(), True)
    qtbot.addWidget(window)
    window.append_result("output", "こんにちは")
    window.append_result("output", "", "Hello")
    page = window.pages["output"]
    assert page.results.toPlainText() == "こんにちは"
    assert page.translations.toPlainText() == "Hello"
    window.set_recording("output", True)
    assert page.start_button.isHidden()
    assert not page.start_button.isEnabled()
    assert not page.stop_button.isHidden()
    assert page.stop_button.isEnabled()
    window.set_recording("output", False)
    assert not page.start_button.isHidden()
    assert page.stop_button.isHidden()


def test_overlay_visibility_is_controlled_from_preferences(qtbot):
    overlay = CaptionOverlay(Settings())
    qtbot.addWidget(overlay)
    overlay.show()
    overlay.update_settings(Settings(translation_visible=False, translation_enabled=False))
    assert overlay.translation.isHidden()
    overlay.update_settings(Settings(transcript_visible=False, translation_visible=False))
    assert overlay.empty.isVisible()
    overlay.append_caption("日本語", "Japanese")
    overlay.update_settings(Settings())
    assert overlay.translation.toPlainText() == "Japanese"
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
    window.update_settings(Settings(input_model="custom-transcribe-model"))
    window.set_models(["gpt-transcribe", "gpt-live-transcribe", "gpt-6-luna", "gpt-4o-mini-tts"])
    input_panel = window.pages["input"].tool_settings
    translation_panel = window.pages["translate"].tool_settings
    assert input_panel.models["input_model"].currentText() == "custom-transcribe-model"
    assert input_panel.models["input_model"].findText("gpt-live-transcribe") < 0
    assert translation_panel.models["translation_model"].findText("gpt-6-luna") >= 0


def test_preferences_save_applies_instructions_to_all_modes(qtbot):
    window = MainWindow(Settings(), True)
    qtbot.addWidget(window)
    window.settings_saved.connect(window.settings_save_succeeded)
    preferences = window.pages["translate"].tool_settings
    preferences.instructions["translation_instructions"].setPlainText("Use polite Russian.")
    preferences.target_language.setCurrentText("Russian")
    preferences.save_button.click()
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
    assert "Hello" in page.translation.text.toPlainText()
    assert window.stack.currentWidget() is page


def test_audio_activity_is_compact_and_only_visible_while_recording(qtbot):
    window = MainWindow(Settings(), True)
    qtbot.addWidget(window)
    page = window.pages["input"]
    assert page.level.isHidden()
    assert not page.findChildren(QProgressBar)
    window.set_level("input", 0.1)
    assert page.level.isHidden()
    window.set_recording("input", True)
    assert not page.level.isHidden()
    assert page.level.text() == "Listening…"
    window.set_level("input", 0.1)
    assert page.level.text() == "● Audio detected"
    window.set_level("input", float("nan"))
    assert page.level.text() == "Listening…"
    window.set_recording("input", False)
    assert page.level.isHidden()


def test_device_names_are_saved_and_friendly_labels_displayed(qtbot):
    window = MainWindow(Settings(microphone_source="usb.mic"), True)
    qtbot.addWidget(window)
    devices = [
        {"name": "usb.mic", "description": "USB Microphone", "is_monitor": False},
        {"name": "speakers.monitor", "description": "Desk speakers", "is_monitor": True},
    ]
    window.set_sources(devices)
    input_panel = window.pages["input"].tool_settings
    output_panel = window.pages["output"].tool_settings
    assert input_panel.microphone_source.currentText() == "USB Microphone"
    assert input_panel.microphone_source.findText("Desk speakers") < 0
    output_panel.output_source.setCurrentText("Desk speakers")
    assert input_panel.collect()["microphone_source"] == "usb.mic"
    assert output_panel.collect()["output_source"] == "speakers.monitor"
    output_panel.save_button.click()
    window.set_sources(devices)
    assert output_panel.output_source.currentText() == "Desk speakers"
    input_panel.microphone_source.setCurrentIndex(0)
    assert input_panel.collect()["microphone_source"] == ""
    assert not output_panel.output_source.isEditable()
    output_panel.output_source.setEditText("custom.monitor")
    assert output_panel.collect()["output_source"] == "speakers.monitor"


def test_settings_update_does_not_emit_feedback_and_key_clears(qtbot):
    window = MainWindow(Settings(), True)
    qtbot.addWidget(window)
    settings = QSignalSpy(window.settings_saved)
    window.settings_saved.connect(window.update_settings)
    assert window.sync_mode_settings() == window.settings
    assert settings.count() == 0
    window.pages["input"].source_language.setCurrentText("Japanese")
    assert settings.count() == 1
    assert window.settings.input_language == "ja"
    assert window.pages["input"].tool_settings.input_language.currentText() == "Japanese"
    preferences = window.pages["preferences"]
    saved_keys = QSignalSpy(window.key_saved)
    preferences.api_key.setText("unit-test-placeholder")
    preferences._save_key()
    assert preferences.api_key.text() == "unit-test-placeholder"
    window.key_saved_successfully()
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
    assert overlay.transcript.toPlainText() == ""
    assert overlay.translation.toPlainText() == ""
    assert stopped.count() == 0
    assert overlay.settings.translation_enabled
    assert not hasattr(overlay, "transcript_toggle")


def test_remove_key_and_tts_model_choices(qtbot):
    window = MainWindow(Settings(), True)
    qtbot.addWidget(window)
    preferences = window.pages["preferences"]
    keys = QSignalSpy(window.key_saved)
    preferences.api_key.setText("unsaved-placeholder")
    preferences.remove_key_button.click()
    assert keys.at(0) == [""]
    window.key_saved_successfully()
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
    assert window.pages["translate"].tool_settings.instructions["translation_instructions"].tabChangesFocus()


def test_speech_replay_is_forwarded_to_controller(qtbot):
    window = MainWindow(Settings(), True)
    qtbot.addWidget(window)
    replay = QSignalSpy(window.speech_replay_requested)
    generated = QSignalSpy(window.speech_requested)
    page = window.speech_controls
    assert not page.play.isEnabled()
    window.set_speech("/tmp/unit-test-speech.wav")
    page.play.click()
    assert replay.count() == 1
    assert replay.at(0) == ["/tmp/unit-test-speech.wav"]
    assert generated.count() == 0


def test_key_test_and_model_refresh_receive_fresh_candidate(qtbot):
    window = MainWindow(Settings(), True)
    qtbot.addWidget(window)
    preferences = window.pages["preferences"]
    tested = []
    refreshed = []
    window.key_test_requested.connect(tested.append)
    window.models_requested.connect(refreshed.append)
    preferences.api_key.setText("  replacement-placeholder  ")
    assert preferences.test_key_button.text() == "Save and test"
    preferences.test_key_button.click()
    preferences.refresh_models_button.click()
    assert tested == ["replacement-placeholder"]
    assert refreshed == ["replacement-placeholder"]
    assert preferences.api_key.text().strip() == "replacement-placeholder"
    window.key_saved_successfully()
    assert preferences.api_key.text() == ""
    assert preferences.test_key_button.text() == "Test connection"
    preferences.test_key_button.click()
    preferences.refresh_models_button.click()
    assert tested[-1] == ""
    assert refreshed[-1] == ""


def test_key_save_failure_keeps_masked_candidate_for_retry(qtbot):
    window = MainWindow(Settings(), True)
    qtbot.addWidget(window)
    preferences = window.pages["preferences"]
    attempts = []

    def failed_save(candidate):
        attempts.append(candidate)
        window.set_status("Could not save the API key. Check local credential storage.", True)

    window.key_saved.connect(failed_save)
    preferences.api_key.setText("replacement-placeholder")
    preferences._save_key()
    assert attempts == ["replacement-placeholder"]
    assert preferences.api_key.text() == "replacement-placeholder"
    assert preferences.api_key.echoMode() == QLineEdit.EchoMode.Password
    assert window.status.property("error")


def test_proxy_preferences_round_trip_and_pending_connection_value(qtbot):
    window = MainWindow(Settings(api_proxy_url="http://proxy.example:8080"), True)
    qtbot.addWidget(window)
    window.settings_saved.connect(window.settings_save_succeeded)
    preferences = window.pages["preferences"]
    assert preferences.api_proxy_url.text() == "http://proxy.example:8080"
    preferences.api_proxy_url.setText("  socks5://proxy.example:1080  ")
    input_panel = window.pages["input"].tool_settings
    input_panel.models["input_model"].addItem("test-transcribe-model")
    input_panel.models["input_model"].setCurrentText("test-transcribe-model")
    assert window.connection_proxy_url() == "socks5://proxy.example:1080"
    assert input_panel.models["input_model"].currentText() == "test-transcribe-model"
    saved = preferences.collect()
    assert saved["api_proxy_url"] == "socks5://proxy.example:1080"
    window._save_preferences(saved)
    assert preferences.api_proxy_url.text() == saved["api_proxy_url"]
    assert input_panel.models["input_model"].currentText() == "test-transcribe-model"
    preferences.api_proxy_url.clear()
    assert window.connection_proxy_url() == ""
    assert preferences.collect()["api_proxy_url"] == ""


def test_translate_contains_speech_for_both_text_panes(qtbot):
    window = MainWindow(Settings(), True)
    qtbot.addWidget(window)
    window.settings_saved.connect(window.settings_save_succeeded)
    assert "tts" not in window.pages
    assert set(window.pages) == {
        "input",
        "output",
        "translate",
        "drawing",
        "history",
        "preferences",
    }
    window.show_page("tts")
    page = window.pages["translate"]
    assert window.stack.currentWidget() is page
    window.set_source_text("tts", "Original words")
    window.set_translation("Translated words")
    preferences = window.pages["preferences"]
    preferences.instructions["tts_instructions"].setPlainText("Speak slowly.")
    preferences.save_preferences.click()
    page.tool_settings.target_language.setCurrentText("Japanese")
    page.tool_settings.save_button.click()
    requested = QSignalSpy(window.audio_requested)
    page.speak_original.click()
    page.speak_translation.click()
    assert requested.count() == 2
    assert requested.at(0)[0] == "Original words"
    assert requested.at(1)[0] == "Translated words"
    assert window.settings.tts_instructions == "Speak slowly."
    assert window.settings.target_language == "Japanese"
    assert not hasattr(page, "tts_instructions")


def test_caption_translation_option_updates_generation_and_visibility(qtbot):
    window = MainWindow(Settings(), True)
    qtbot.addWidget(window)
    window.settings_saved.connect(window.settings_save_succeeded)
    saved = QSignalSpy(window.settings_saved)
    page = window.pages["output"]
    panel = page.tool_settings
    panel.translation_visible.setChecked(False)
    panel.save_button.click()
    assert not window.settings.translation_visible
    assert not window.settings.translation_enabled
    assert page.translations.isHidden()
    assert saved.count() == 1
    window.update_settings(
        replace(window.settings, translation_visible=True, translation_enabled=True)
    )
    assert saved.count() == 1
    assert panel.translation_visible.isChecked()


def test_preferences_are_global_and_tool_settings_are_on_their_pages(qtbot):
    window = MainWindow(Settings(), True)
    qtbot.addWidget(window)
    page = window.pages["preferences"]
    assert [page.tabs.tabText(i) for i in range(page.tabs.count())] == [
        "Connection", "Shared speech", "Shortcuts"
    ]
    assert set(page.models) == {"tts_model"}
    for mode in ("input", "output", "translate", "drawing"):
        assert window.pages[mode].tool_settings.mode == mode
        assert window.pages[mode].settings_button.accessibleName().endswith("settings")
        assert not window.pages[mode].settings_view.isVisible()


def test_tool_layouts_fit_and_settings_do_not_expand_into_the_work_area(qtbot):
    window = MainWindow(Settings(), True)
    qtbot.addWidget(window)
    window.show()
    for size in [(1120, 780), (850, 620)]:
        window.resize(*size)
        for mode in ("input", "output", "translate", "drawing"):
            window.show_page(mode)
            page = window.pages[mode]
            qtbot.wait(20)
            content = page.splitter if mode in ("output", "translate") else (
                page.results if mode == "input" else page.canvas
            )
            assert content.height() >= 100
            page.settings_button.click()
            qtbot.wait(20)
            view = page.settings_view
            assert window.stack.currentWidget() is view
            assert view.isVisible()
            assert not view.isWindow()
            assert window.nav_buttons[mode].isChecked()
            assert view.scroll.horizontalScrollBar().maximum() == 0
            assert page.tool_settings.actions.geometry().bottom() < view.scroll.y()
            view.back_button.click()
            assert window.stack.currentWidget() is page



def test_preferences_tabs_and_header_remain_separate_at_minimum_size(qtbot):
    window = MainWindow(Settings(), True)
    qtbot.addWidget(window)
    window.show_page("preferences")
    window.show()
    page = window.pages["preferences"]
    for size in [(1120, 780), (850, 620)]:
        window.resize(*size)
        qtbot.wait(20)
        assert page.save_preferences.geometry().bottom() < page.tabs.geometry().top()
        assert page.tabs.tabBar().sizeHint().width() <= page.tabs.tabBar().width()
        assert page.save_preferences.geometry().bottom() <= page.height()
