"""Preferences restore defaults without touching credentials or auto-saving edits."""

from dataclasses import fields, replace

from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QComboBox

from lang_handler.settings import Settings
from lang_handler.ui.preference_controls import NumberInput
from lang_handler.ui.preferences import PreferencesPage
from lang_handler.ui.theme import STYLE


def test_every_saved_option_has_an_individual_reset(qtbot):
    page = PreferencesPage(Settings(), True)
    qtbot.addWidget(page)
    registered = set(page.reset_buttons)
    setting_names = {field.name for field in fields(Settings)}
    assert registered - {key for key in registered if key.startswith("shortcut:")} == (
        setting_names - {"shortcuts", "translation_enabled"}
    )
    assert {key for key in registered if key.startswith("shortcut:")} == {
        f"shortcut:{mode}" for mode in Settings().shortcuts
    }


def test_reset_all_restores_all_values_but_keeps_key_and_waits_for_save(qtbot):
    settings = Settings(
        api_proxy_url="http://localhost:9999",
        input_model="other-transcribe",
        output_model="other-asr",
        translation_model="other-text",
        tts_model="other-voice",
        drawing_model="other-vision",
        input_language="fr",
        output_language="ru",
        target_language="Japanese",
        voice="cedar",
        input_instructions="Custom input",
        output_instructions="Custom captions",
        translation_instructions="Custom translation",
        tts_instructions="Custom speech",
        drawing_instructions="Custom reading",
        drawing_auto_send=False,
        drawing_debounce_ms=3000,
        drawing_pen_width=12,
        drawing_on_top=False,
        chunk_seconds=10,
        input_chunked=True,
        output_chunked=False,
        translation_visible=False,
        translation_enabled=False,
        transcript_visible=False,
        auto_paste=False,
        microphone_source="usb.mic",
        output_source="desk.monitor",
        font_size=40,
        overlay_opacity=0.55,
        overlay_on_top=False,
        shortcuts={mode: "Ctrl+Alt+9" for mode in Settings().shortcuts},
    )
    page = PreferencesPage(settings, True)
    qtbot.addWidget(page)
    assert page.collect() == settings
    page.api_key.setText("pending-test-placeholder")
    saved = QSignalSpy(page.saved)
    keys = QSignalSpy(page.key_saved)
    page.reset_all_button.click()
    assert page.collect() == Settings()
    assert page.settings == settings
    assert page.api_key.text() == "pending-test-placeholder"
    assert page.remove_key_button.isEnabled()
    assert saved.count() == 0
    assert keys.count() == 0
    page.save_preferences.click()
    assert saved.count() == 1
    assert saved.at(0) == [Settings()]


def test_each_reset_restores_only_its_option(qtbot):
    page = PreferencesPage(Settings(chunk_seconds=12, drawing_pen_width=10, voice="cedar"), True)
    qtbot.addWidget(page)
    page.instructions["tts_instructions"].setPlainText("Whisper slowly.")
    page.reset_buttons["chunk_seconds"].click()
    assert page.collect().chunk_seconds == Settings().chunk_seconds
    assert page.collect().drawing_pen_width == 10
    assert page.collect().voice == "cedar"
    assert page.collect().tts_instructions == "Whisper slowly."
    page.reset_buttons["tts_instructions"].click()
    assert page.collect().tts_instructions == Settings().tts_instructions


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


def test_speech_instructions_and_percent_opacity_roundtrip(qtbot):
    page = PreferencesPage(Settings(), True)
    qtbot.addWidget(page)
    assert page.opacity.value() == 95
    page.opacity.setValue(70)
    page.instructions["tts_instructions"].setPlainText("Read with a Japanese accent.")
    result = page.collect()
    assert result.overlay_opacity == 0.7
    assert result.tts_instructions == "Read with a Japanese accent."
    page.update_settings(result)
    page.update_settings(replace(result, overlay_opacity=0.85))
    assert page.opacity.value() == 85


def test_preferences_selectors_reject_typed_arbitrary_values(qtbot):
    page = PreferencesPage(Settings(), True)
    qtbot.addWidget(page)
    for widget in page.findChildren(QComboBox):
        assert not widget.isEditable()
        selected = widget.currentText()
        widget.setCurrentText("invalid arbitrary text")
        assert widget.currentText() == selected
    assert page.models["drawing_model"].currentText() == "gpt-6-luna"
    assert page.models["drawing_model"].findText("gpt-6.1-sol") >= 0


def test_refresh_and_reset_preserve_default_and_saved_model_choices(qtbot):
    page = PreferencesPage(Settings(drawing_model="saved-vision-model"), True)
    qtbot.addWidget(page)
    page.set_models(["gpt-6.1-sol"])
    assert page.models["drawing_model"].currentText() == "saved-vision-model"
    page.reset_buttons["drawing_model"].click()
    assert page.models["drawing_model"].currentText() == "gpt-6-luna"
    page.update_settings(page.collect())
    page.update_settings(Settings(drawing_model="another-saved-model"))
    assert page.models["drawing_model"].currentText() == "another-saved-model"


def test_disabling_automatic_recognition_disables_delay_steps(qtbot):
    page = PreferencesPage(Settings(drawing_auto_send=True), True)
    qtbot.addWidget(page)
    page.drawing_auto_send.setChecked(False)
    assert not page.drawing_delay.isEnabled()
    page.reset_buttons["drawing_auto_send"].click()
    assert page.drawing_delay.isEnabled()


def test_external_settings_refresh_preserves_drafts_and_updates_untouched_fields(qtbot):
    baseline = Settings()
    page = PreferencesPage(baseline, True)
    qtbot.addWidget(page)
    page.instructions["tts_instructions"].setPlainText("Pending voice instructions")
    page.drawing_pen_width.setValue(8)
    page.drawing_auto_send.setChecked(False)
    page.update_settings(replace(baseline, translation_visible=False, translation_enabled=False))
    assert page.collect().tts_instructions == "Pending voice instructions"
    assert page.collect().drawing_pen_width == 8
    assert not page.collect().translation_visible
    assert not page.drawing_delay.isEnabled()
    assert page.fields.has_pending
    applied = page.collect()
    page.update_settings(applied)
    assert not page.fields.has_pending
    page.update_settings(replace(applied, drawing_pen_width=10))
    assert page.drawing_pen_width.value() == 10


def test_committed_baseline_does_not_alias_mutable_application_settings(qtbot):
    settings = Settings()
    page = PreferencesPage(settings, True)
    qtbot.addWidget(page)
    page.drawing_pen_width.setValue(8)
    settings.drawing_pen_width = 12
    settings.voice = "cedar"
    page.update_settings(settings)
    assert page.collect().drawing_pen_width == 8
    assert page.collect().voice == "cedar"


def test_reset_all_draft_survives_external_refresh_and_save_rebases(qtbot):
    baseline = Settings(
        drawing_pen_width=12,
        drawing_model="gpt-6.1-sol",
        tts_instructions="Custom voice",
        api_proxy_url="http://old.example:8080",
    )
    page = PreferencesPage(baseline, True)
    qtbot.addWidget(page)
    page.reset_all_button.click()
    page.update_settings(replace(baseline, input_chunked=True))
    assert page.collect().drawing_model == "gpt-6-luna"
    assert page.collect().drawing_pen_width == 4
    assert page.collect().tts_instructions == Settings().tts_instructions
    assert page.collect().api_proxy_url == ""
    assert page.collect().input_chunked
    applied = page.collect()
    page.update_settings(applied)
    assert not page.fields.has_pending


def test_connection_commit_preserves_other_pending_preferences(qtbot):
    baseline = Settings(api_proxy_url="http://old.example:8080")
    page = PreferencesPage(baseline, True)
    qtbot.addWidget(page)
    page.api_proxy_url.setText("http://new.example:8080")
    page.drawing_pen_width.setValue(8)
    committed = replace(baseline, api_proxy_url=page.api_proxy_url.text())
    page.update_settings(committed)
    assert page.fields.committed["api_proxy_url"] == "http://new.example:8080"
    assert page.collect().api_proxy_url == "http://new.example:8080"
    assert page.collect().drawing_pen_width == 8
