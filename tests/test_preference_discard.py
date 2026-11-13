"""Discard and reopening restore saved settings without silently saving drafts."""

from dataclasses import replace

from PySide6.QtTest import QSignalSpy

from lang_handler.settings import Settings
from lang_handler.ui.capture_page import CapturePage
from lang_handler.ui.main_window import MainWindow
from lang_handler.ui.preferences import PreferencesPage


def test_global_discard_restores_latest_committed_values_and_clears_key_draft(qtbot):
    saved = Settings(voice="cedar", api_proxy_url="http://localhost:9000")
    preferences = PreferencesPage(saved)
    qtbot.addWidget(preferences)
    preferences.fields.fields["voice"].write("coral")
    preferences.api_proxy_url.setText("http://localhost:9001")
    preferences.api_key.setText("unsaved-key-draft")
    preferences.update_settings(replace(saved, voice="marin"))
    assert preferences.collect()["voice"] == "coral"
    saved_requests = QSignalSpy(preferences.saved)
    discarded = QSignalSpy(preferences.discard_requested)
    preferences.discard_button.click()
    assert preferences.collect()["voice"] == "marin"
    assert preferences.collect()["api_proxy_url"] == saved.api_proxy_url
    assert preferences.api_key.text() == ""
    assert not preferences.fields.has_pending
    assert not preferences.save_hint.text()
    assert saved_requests.count() == 0
    assert discarded.count() == 1


def test_tool_discard_and_reopen_restore_saved_settings(qtbot):
    window = MainWindow(Settings(output_language="ja", target_language="English"), True)
    qtbot.addWidget(window)
    page = window.pages["output"]
    view, panel = page.settings_view, page.tool_settings
    saved_requests = QSignalSpy(panel.saved)
    window.show_tool_settings("output")
    panel.output_language.setCurrentText("Russian")
    panel.target_language.setCurrentText("French")
    window.show_tool_settings("output")  # Re-selecting an open editor preserves its draft.
    assert panel.collect()["output_language"] == "ru"
    panel.discard_button.click()
    assert panel.collect()["output_language"] == "ja"
    assert panel.collect()["target_language"] == "English"
    panel.target_language.setCurrentText("Korean")
    view.back_button.click()
    window.show_tool_settings("output")
    try:
        assert panel.collect()["target_language"] == "English"
        assert not panel.fields.has_pending
        assert saved_requests.count() == 0
    finally:
        view.back_button.click()


def test_discard_section_uses_external_save_received_while_editing(qtbot):
    page = CapturePage("output", Settings())
    qtbot.addWidget(page)
    panel = page.tool_settings
    panel.target_language.setCurrentText("Korean")
    page.apply_settings(Settings(target_language="French"))
    assert panel.target_language.currentText() == "Korean"
    panel.discard_changes()
    assert panel.target_language.currentText() == "French"
    assert not panel.fields.has_pending


def test_preferences_reopen_discards_drafts_and_staged_global_reset(qtbot):
    saved = Settings(voice="cedar", drawing_language="ja", target_language="Russian")
    window = MainWindow(saved, True)
    qtbot.addWidget(window)
    preferences = window.pages["preferences"]
    window.show_page("preferences")
    preferences.reset_all_button.click()
    assert window._reset_all_pending
    window.show_page("drawing")
    window.show_page("preferences")
    assert preferences.collect()["voice"] == "cedar"
    assert not window._reset_all_pending
    assert window.pages["drawing"].tool_settings.collect()["drawing_language"] == "ja"
    preferences.save_preferences.click()
    assert window.settings == saved
