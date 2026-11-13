"""Cross-page saves, resets, and shared fields keep the user in control of drafts."""

from PySide6.QtWidgets import QComboBox

from lang_handler.settings import Settings
from lang_handler.ui.main_window import MainWindow


def test_saving_one_tool_preserves_other_tool_and_global_drafts(qtbot):
    window = MainWindow(Settings(drawing_language="en", translation_provider="openai"), True)
    qtbot.addWidget(window)
    window.settings_saved.connect(window.settings_save_succeeded)
    drawing = window.pages["drawing"].tool_settings
    translation = window.pages["translate"].tool_settings
    global_settings = window.pages["preferences"]
    drawing.drawing_language.setCurrentText("Japanese")
    global_settings.instructions["tts_instructions"].setPlainText("Unsaved voice instruction")
    translation.translation_reasoning.setCurrentText("High")
    translation.save_button.click()
    assert window.settings.translation_reasoning == "high"
    assert window.settings.drawing_language == "en"
    assert window.settings.tts_instructions == Settings().tts_instructions
    assert drawing.collect()["drawing_language"] == "ja"
    assert global_settings.collect()["tts_instructions"] == "Unsaved voice instruction"
    drawing.save_button.click()
    assert window.settings.drawing_language == "ja"
    assert window.settings.translation_reasoning == "high"


def test_shared_translation_settings_refresh_both_tools_without_losing_drafts(qtbot):
    window = MainWindow(Settings(), True)
    qtbot.addWidget(window)
    window.settings_saved.connect(window.settings_save_succeeded)
    captions = window.pages["output"].tool_settings
    translation = window.pages["translate"].tool_settings
    translation.instructions["translation_instructions"].setPlainText("Unsaved translation style")
    captions.translation_reasoning.setCurrentText("High")
    captions.target_language.setCurrentText("Japanese")
    captions.save_button.click()
    assert window.settings.translation_reasoning == "high"
    assert translation.translation_reasoning.currentText() == "High"
    assert window.pages["translate"].target.currentText() == "Japanese"
    assert translation.instructions["translation_instructions"].toPlainText() == "Unsaved translation style"


def test_global_reset_all_stages_all_sections_then_global_save_applies(qtbot):
    window = MainWindow(Settings(
        drawing_language="en", drawing_reasoning="high", input_delivery="copy",
        target_language="Russian", output_chunk_seconds=9, voice="cedar",
    ), True)
    qtbot.addWidget(window)
    window.settings_saved.connect(window.settings_save_succeeded)
    preferences = window.pages["preferences"]
    preferences.reset_all_button.click()
    assert window.settings.drawing_language == "en"
    assert window.pages["drawing"].tool_settings.collect()["drawing_language"] == "ja"
    assert window.pages["input"].tool_settings.collect()["input_delivery"] == "copy_and_paste"
    preferences.save_preferences.click()
    assert window.settings == Settings()
    for mode in ("input", "output", "translate", "drawing"):
        assert not window.pages[mode].tool_settings.fields.has_pending


def test_floating_handwriting_does_not_carry_tool_settings(qtbot):
    window = MainWindow(Settings(drawing_auto_send=False), True)
    qtbot.addWidget(window)
    drawing = window.pages["drawing"]
    drawing.settings_button.click()
    assert window.stack.currentWidget() is drawing.settings_view
    drawing.show_floating()
    try:
        assert not drawing.floating.isAncestorOf(drawing.tool_settings)
        assert drawing.settings_view.isAncestorOf(drawing.tool_settings)
        assert drawing.settings_view.parentWidget() is window.stack
        assert not drawing.floating.findChildren(QComboBox)
    finally:
        window.show_page("drawing")
        drawing.shutdown()
