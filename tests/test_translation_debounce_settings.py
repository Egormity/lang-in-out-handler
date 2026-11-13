"""Typing debounce is owned by Translate and preserves explicit saved preferences."""

from dataclasses import replace

from lang_handler.settings import Settings
from lang_handler.storage import Store
from lang_handler.ui.tool_settings import ToolSettings


def test_new_defaults_are_one_second_without_migrating_saved_delays():
    settings = Settings()
    assert settings.translation_auto_send
    assert settings.translation_debounce_ms == settings.drawing_debounce_ms == 1000
    saved = Settings.from_dict({
        "translation_auto_send": False, "translation_debounce_ms": 2700,
        "drawing_debounce_ms": 1200,
    })
    assert not saved.translation_auto_send
    assert saved.translation_debounce_ms == 2700
    assert saved.drawing_debounce_ms == 1200


def test_translate_delay_roundtrip_and_disabling_preserve_the_value(qtbot, tmp_path):
    settings = Settings(translation_auto_send=False, translation_debounce_ms=3400)
    panel = ToolSettings("translate", settings)
    qtbot.addWidget(panel)
    assert not panel.translation_delay.isEnabled()
    assert panel.translation_delay.value() == 3.4
    panel.translation_auto_send.setChecked(True)
    assert panel.translation_delay.isEnabled()
    panel.translation_delay.setValue(2.7)
    panel.translation_auto_send.setChecked(False)
    assert not panel.translation_delay.isEnabled()
    patch = panel.collect()
    assert patch["translation_debounce_ms"] == 2700
    assert not patch["translation_auto_send"]
    store = Store(tmp_path)
    try:
        store.save_settings(replace(settings, **patch))
        saved = store.load_settings()
        assert not saved.translation_auto_send
        assert saved.translation_debounce_ms == 2700
    finally:
        store.close()


def test_translation_debounce_resets_and_discard_restore_committed_state(qtbot):
    settings = Settings(translation_auto_send=False, translation_debounce_ms=2300)
    panel = ToolSettings("translate", settings)
    qtbot.addWidget(panel)
    panel.reset_buttons["translation_auto_send"].click()
    panel.reset_buttons["translation_debounce_ms"].click()
    assert panel.translation_auto_send.isChecked()
    assert panel.translation_delay.isEnabled()
    assert panel.collect()["translation_debounce_ms"] == 1000
    panel.discard_changes()
    assert not panel.translation_auto_send.isChecked()
    assert not panel.translation_delay.isEnabled()
    assert panel.translation_delay.value() == 2.3
    assert not panel.fields.has_pending
    panel.reset_section()
    assert panel.translation_auto_send.isChecked()
    assert panel.translation_delay.isEnabled()
    assert panel.translation_delay.value() == 1.0


def test_caption_settings_never_own_typing_debounce(qtbot):
    settings = Settings(translation_auto_send=False, translation_debounce_ms=2300)
    captions = ToolSettings("output", settings)
    translate = ToolSettings("translate", settings)
    qtbot.addWidget(captions)
    qtbot.addWidget(translate)
    for key in ("translation_auto_send", "translation_debounce_ms"):
        assert key not in captions.collect()
        assert key not in captions.reset_buttons
        assert key in translate.collect()
        assert key in translate.reset_buttons
    captions.reset_section()
    merged = replace(settings, **captions.collect())
    assert not merged.translation_auto_send
    assert merged.translation_debounce_ms == 2300
