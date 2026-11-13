"""Provider settings keep optional OpenAI choices while Google needs no key or model."""

from dataclasses import replace

import pytest
from PySide6.QtTest import QSignalSpy

from lang_handler.settings import Settings
from lang_handler.ui.tool_settings import ToolSettings


@pytest.mark.parametrize("mode,key", [
    ("drawing", "drawing"), ("translate", "translation"), ("output", "translation"),
])
def test_google_hides_openai_options_but_preserves_them_when_switching(qtbot, mode, key):
    initial = Settings(**{f"{key}_model": "custom-openai-model", f"{key}_instructions": "Saved style"})
    panel = ToolSettings(mode, initial)
    qtbot.addWidget(panel)
    panel.show()
    provider = getattr(panel, f"{key}_provider")
    controls = panel.provider_controls[f"{key}_provider"]
    assert provider.currentData() == "google"
    assert controls.note.isVisible()
    assert not panel.models[f"{key}_model"].isVisible()
    assert not getattr(panel, f"{key}_reasoning").isVisible()
    assert not panel.instructions[f"{key}_instructions"].isVisible()
    assert not panel.builtin_instructions[f"{key}_instructions"].isVisible()
    provider.setCurrentText("OpenAI")
    assert not controls.note.isVisible()
    assert panel.models[f"{key}_model"].isVisible()
    assert panel.instructions[f"{key}_instructions"].isVisible()
    assert panel.builtin_instructions[f"{key}_instructions"].isVisible()
    assert panel.collect()[f"{key}_model"] == "custom-openai-model"
    assert panel.collect()[f"{key}_instructions"] == "Saved style"
    assert panel.collect()[f"{key}_provider"] == "openai"


def test_existing_auto_language_is_preserved_but_requires_selection_for_google(qtbot):
    settings = Settings.from_dict({"drawing_language": "", "drawing_model": "gpt-6-luna"})
    assert settings.drawing_language == ""
    assert settings.drawing_model == "gpt-6-luna"
    panel = ToolSettings("drawing", settings)
    qtbot.addWidget(panel)
    panel.show()
    controls = panel.provider_controls["drawing_provider"]
    selector = panel.drawing_language
    auto = selector.model().item(selector.findData(""))
    assert selector.currentData() == ""
    assert not auto.isEnabled()
    assert controls.language_requirement.isVisible()
    assert not panel.fields.has_pending
    selector.setCurrentText("Japanese")
    assert not controls.language_requirement.isVisible()
    panel.drawing_provider.setCurrentText("OpenAI")
    assert auto.isEnabled()
    selector.setCurrentText("Auto detect")
    assert panel.collect()["drawing_language"] == ""
    assert not controls.language_requirement.isVisible()


def test_provider_reset_discard_and_save_preserve_scoped_values(qtbot):
    initial = Settings(drawing_provider="openai", drawing_language="", drawing_instructions="Keep names")
    panel = ToolSettings("drawing", initial)
    qtbot.addWidget(panel)
    panel.show()
    saved = QSignalSpy(panel.saved)
    panel.reset_buttons["drawing_provider"].click()
    assert panel.collect()["drawing_provider"] == "google"
    assert panel.collect()["drawing_instructions"] == "Keep names"
    assert saved.count() == 0
    panel.discard_changes()
    assert panel.drawing_provider.currentData() == "openai"
    assert panel.drawing_language.currentData() == ""
    assert panel.models["drawing_model"].isVisible()
    panel.drawing_provider.setCurrentText("Google")
    panel.drawing_language.setCurrentText("Japanese")
    panel.save_button.click()
    patch = saved.at(0)[0]
    assert patch["drawing_provider"] == "google"
    assert patch["drawing_language"] == "ja"
    assert "translation_provider" not in patch
    assert initial.drawing_provider == "openai"


def test_caption_provider_updates_translate_without_overwriting_pending_drafts(qtbot):
    initial = Settings()
    captions = ToolSettings("output", initial)
    translate = ToolSettings("translate", initial)
    qtbot.addWidget(captions)
    qtbot.addWidget(translate)
    captions.translation_provider.setCurrentText("OpenAI")
    translate.update_settings(replace(initial, **captions.collect()))
    assert translate.translation_provider.currentData() == "openai"
    translate.translation_provider.setCurrentText("Google")
    translate.update_settings(replace(initial, translation_provider="openai", target_language="Japanese"))
    assert translate.translation_provider.currentData() == "google"
    assert translate.target_language.currentText() == "Japanese"


def test_new_defaults_use_google_and_japanese_without_changing_openai_models():
    defaults = Settings()
    assert defaults.drawing_provider == defaults.translation_provider == "google"
    assert defaults.drawing_language == "ja"
    assert defaults.drawing_model == "gpt-6.1-sol"
    assert defaults.translation_model == "gpt-6-luna"
    saved = Settings.from_dict({"drawing_provider": "openai", "drawing_language": "", "drawing_model": "saved-model"})
    assert saved.drawing_provider == "openai"
    assert saved.drawing_language == ""
    assert saved.drawing_model == "saved-model"
