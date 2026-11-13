"""Tool panels save scoped patches and retain independent unsaved changes."""

from dataclasses import fields, replace

import pytest
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QComboBox

from lang_handler.settings import Settings
from lang_handler.ui.preferences import PreferencesPage
from lang_handler.ui.tool_settings import ToolSettings


def test_every_option_has_a_reset_in_its_relevant_settings_panel(qtbot):
    panels = [PreferencesPage(Settings())] + [
        ToolSettings(mode, Settings()) for mode in ("input", "output", "translate", "drawing")
    ]
    registered = set()
    for panel in panels:
        qtbot.addWidget(panel)
        registered.update(panel.reset_buttons)
    names = {field.name for field in fields(Settings)}
    assert {key for key in registered if not key.startswith("shortcut:")} == (
        names - {"shortcuts", "translation_enabled"}
    )
    assert all(f"shortcut:{mode}" in registered for mode in Settings().shortcuts)


@pytest.mark.parametrize("mode", ["input", "output", "translate", "drawing"])
def test_tool_save_emits_only_owned_fields_and_all_dropdowns_are_strict(qtbot, mode):
    panel = ToolSettings(mode, Settings())
    qtbot.addWidget(panel)
    saved = QSignalSpy(panel.saved)
    panel.save_button.click()
    patch = saved.at(0)[0]
    assert "tts_model" not in patch
    assert "api_proxy_url" not in patch
    assert "shortcuts" not in patch
    assert patch == panel.collect()
    for selector in panel.findChildren(QComboBox):
        assert not selector.isEditable()


def test_handwriting_language_and_reasoning_are_saved_and_reset_independently(qtbot):
    panel = ToolSettings("drawing", Settings(drawing_provider="openai"))
    qtbot.addWidget(panel)
    assert panel.drawing_reasoning.currentText() == "Low"
    assert panel.drawing_language.currentData() == "ja"
    panel.drawing_language.setCurrentText("Japanese")
    panel.drawing_reasoning.setCurrentText("High")
    patch = panel.collect()
    assert patch["drawing_language"] == "ja"
    assert patch["drawing_reasoning"] == "high"
    panel.reset_buttons["drawing_reasoning"].click()
    assert panel.collect()["drawing_reasoning"] == "low"
    assert panel.collect()["drawing_language"] == "ja"


def test_reasoning_control_tracks_model_capability(qtbot):
    panel = ToolSettings("translate", Settings(translation_provider="openai"))
    qtbot.addWidget(panel)
    panel.set_models(["gpt-4o", "gpt-6-luna"])
    panel.models["translation_model"].setCurrentText("gpt-4o")
    assert not panel.translation_reasoning.isEnabled()
    panel.models["translation_model"].setCurrentText("gpt-6-luna")
    assert panel.translation_reasoning.isEnabled()
    assert panel.collect()["translation_reasoning"] == "medium"


def test_voice_delivery_modes_are_distinct_and_chunks_are_scoped(qtbot):
    panel = ToolSettings("input", Settings())
    qtbot.addWidget(panel)
    delivery = panel.input_delivery
    assert delivery.currentData() == "copy_and_paste"
    assert [delivery.itemData(i) for i in range(delivery.count())] == ["copy", "paste", "copy_and_paste"]
    for value in ("copy", "paste", "copy_and_paste"):
        delivery.setCurrentIndex(delivery.findData(value))
        assert panel.collect()["input_delivery"] == value
    panel.input_chunk_seconds.setValue(8)
    assert panel.collect()["input_chunk_seconds"] == 8
    assert "output_chunk_seconds" not in panel.collect()


def test_caption_translation_shares_fields_but_does_not_overwrite_unsaved_translate(qtbot):
    baseline = Settings()
    captions = ToolSettings("output", baseline)
    translate = ToolSettings("translate", baseline)
    qtbot.addWidget(captions)
    qtbot.addWidget(translate)
    translate.translation_reasoning.setCurrentText("High")
    translate.instructions["translation_instructions"].setPlainText("An unsaved draft")
    captions.target_language.setCurrentText("Japanese")
    committed = replace(baseline, **captions.collect())
    translate.update_settings(committed)
    assert translate.target_language.currentText() == "Japanese"
    assert translate.translation_reasoning.currentText() == "High"
    assert translate.instructions["translation_instructions"].toPlainText() == "An unsaved draft"


def test_reset_section_restores_only_current_tool_defaults_and_waits_for_save(qtbot):
    baseline = Settings(drawing_language="ja", drawing_reasoning="high", drawing_pen_width=8)
    panel = ToolSettings("drawing", baseline)
    qtbot.addWidget(panel)
    saved = QSignalSpy(panel.saved)
    panel.reset_section()
    assert panel.collect()["drawing_language"] == "ja"
    assert panel.collect()["drawing_reasoning"] == "low"
    assert panel.collect()["drawing_pen_width"] == 4
    assert panel.settings == baseline
    assert saved.count() == 0


def test_caption_visibility_and_opacity_roundtrip(qtbot):
    panel = ToolSettings("output", Settings())
    qtbot.addWidget(panel)
    panel.translation_visible.setChecked(False)
    panel.opacity.setValue(70)
    patch = panel.collect()
    assert not patch["translation_enabled"]
    assert not patch["translation_visible"]
    assert patch["overlay_opacity"] == 0.7


def test_saved_legacy_capture_settings_map_to_new_fields():
    legacy = Settings.from_dict({"auto_paste": False, "chunk_seconds": 7})
    assert legacy.input_delivery == "copy"
    assert legacy.input_chunk_seconds == legacy.output_chunk_seconds == 7
    assert legacy.translation_reasoning == "medium"
    assert legacy.drawing_reasoning == "low"
    assert "auto_paste" not in legacy.to_dict()
    assert "chunk_seconds" not in legacy.to_dict()
    explicit = Settings.from_dict({"auto_paste": True, "input_delivery": "paste", "chunk_seconds": 7, "input_chunk_seconds": 3})
    assert explicit.input_delivery == "paste"
    assert explicit.input_chunk_seconds == 3
    assert explicit.output_chunk_seconds == 7
