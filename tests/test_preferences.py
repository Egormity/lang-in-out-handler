"""Global preferences own only connection, shared speech, and shortcuts."""

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QComboBox

from lang_handler.settings import Settings
from lang_handler.ui.preference_controls import NumberInput
from lang_handler.ui.preferences import PreferencesPage
from lang_handler.ui.theme import STYLE


def test_global_preferences_contain_only_shared_fields(qtbot):
    page = PreferencesPage(Settings(), True)
    qtbot.addWidget(page)
    assert [page.tabs.tabText(i) for i in range(page.tabs.count())] == [
        "Connection", "Shared speech", "Shortcuts"
    ]
    assert set(page.collect()) == {
        "api_proxy_url", "tts_model", "voice", "tts_instructions", "shortcuts"
    }
    assert set(page.instructions) == {"tts_instructions"}
    assert set(page.models) == {"tts_model"}


def test_reset_all_stages_global_defaults_and_notifies_shell_without_touching_key(qtbot):
    settings = Settings(api_proxy_url="http://localhost:9999", voice="cedar", tts_instructions="Custom")
    page = PreferencesPage(settings, True)
    qtbot.addWidget(page)
    page.api_key.setText("pending-test-placeholder")
    saved, keys, reset = QSignalSpy(page.saved), QSignalSpy(page.key_saved), QSignalSpy(page.reset_all_requested)
    page.reset_all_button.click()
    assert page.collect()["voice"] == Settings().voice
    assert page.collect()["api_proxy_url"] == ""
    assert page.collect()["tts_instructions"] == Settings().tts_instructions
    assert page.settings == settings
    assert page.api_key.text() == "pending-test-placeholder"
    assert page.remove_key_button.isEnabled()
    assert saved.count() == keys.count() == 0
    assert reset.count() == 1
    page.save_preferences.click()
    assert saved.count() == 1
    assert saved.at(0)[0] == page.collect()


def test_each_reset_restores_only_its_global_option(qtbot):
    page = PreferencesPage(Settings(voice="cedar", tts_instructions="Speak slowly."), True)
    qtbot.addWidget(page)
    page.reset_buttons["voice"].click()
    assert page.collect()["voice"] == Settings().voice
    assert page.collect()["tts_instructions"] == "Speak slowly."


def test_number_controls_accept_keyboard_and_have_visible_step_targets(qtbot):
    widget = NumberInput(2, 30, step=0.5, decimals=1, suffix=" seconds", name="Chunk duration")
    qtbot.addWidget(widget)
    widget.setStyleSheet(STYLE)
    widget.resize(340, 48)
    widget.show()
    widget.setValue(5)
    assert widget.spin.lineEdit().width() >= 80
    assert widget.spin.text() == "5.0 seconds"
    assert widget.increase.width() >= 36
    assert widget.increase.height() >= 36
    widget.increase.click()
    assert widget.value() == 5.5
    widget.decrease.click()
    assert widget.value() == 5
    widget.spin.lineEdit().selectAll()
    qtbot.keyClicks(widget.spin.lineEdit(), "8.5")
    qtbot.keyClick(widget.spin.lineEdit(), Qt.Key.Key_Enter)
    assert widget.value() == 8.5
    widget.setValue(2)
    assert not widget.decrease.isEnabled()
    widget.setValue(30)
    assert not widget.increase.isEnabled()


def test_global_selectors_are_not_editable(qtbot):
    page = PreferencesPage(Settings(), True)
    qtbot.addWidget(page)
    for widget in page.findChildren(QComboBox):
        assert not widget.isEditable()
        selected = widget.currentText()
        widget.setCurrentText("invalid arbitrary text")
        assert widget.currentText() == selected


def test_model_refresh_retains_selected_voice_model(qtbot):
    page = PreferencesPage(Settings(tts_model="custom-tts-model"), True)
    qtbot.addWidget(page)
    page.set_models(["gpt-6-luna", "gpt-4o-mini-tts", "gpt-realtime-transcribe"])
    model = page.models["tts_model"]
    assert model.currentText() == "custom-tts-model"
    assert model.findText("gpt-4o-mini-tts") >= 0
    assert model.findText("gpt-6-luna") < 0
    assert model.findText("gpt-realtime-transcribe") < 0


def test_external_tool_changes_preserve_unsaved_global_speech(qtbot):
    baseline = Settings()
    page = PreferencesPage(baseline, True)
    qtbot.addWidget(page)
    page.instructions["tts_instructions"].setPlainText("Pending voice instructions")
    page.update_settings(replace(baseline, translation_visible=False))
    assert page.collect()["tts_instructions"] == "Pending voice instructions"
    assert page.fields.has_pending
    applied = replace(baseline, **page.collect())
    page.update_settings(applied)
    assert not page.fields.has_pending
    page.update_settings(replace(applied, voice="cedar"))
    assert page.voice.currentText() == "cedar"


def test_connection_commit_preserves_other_pending_global_preferences(qtbot):
    baseline = Settings(api_proxy_url="http://old.example:8080")
    page = PreferencesPage(baseline, True)
    qtbot.addWidget(page)
    page.api_proxy_url.setText("  http://new.example:8080  ")
    page.voice.setCurrentText("cedar")
    page.update_settings(replace(baseline, api_proxy_url="http://new.example:8080"))
    assert page.fields.committed["api_proxy_url"] == "http://new.example:8080"
    assert page.api_proxy_url.text() == "http://new.example:8080"
    assert page.collect()["voice"] == "cedar"
