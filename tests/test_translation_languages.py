"""Source selection and swapping produce one current translation with saved languages."""

from dataclasses import replace

import pytest
from PySide6.QtTest import QSignalSpy

from lang_handler.results import TranslationResult
from lang_handler.settings import Settings
from lang_handler.ui.text_pages import TranslatePage
from lang_handler.ui.tool_settings import ToolSettings


def make_page(qtbot, **options):
    page = TranslatePage(Settings(translation_debounce_ms=200, **options))
    qtbot.addWidget(page)
    return page


def test_source_selector_matches_target_languages_with_auto_and_saves_only_its_field(qtbot):
    page = make_page(qtbot)
    changed = QSignalSpy(page.options_changed)
    assert page.source.heading.isHidden()
    assert page.source_language.parentWidget() is page.source
    assert not page.source_language.isEditable()
    assert page.source_language.currentText() == "Auto detect"
    assert [page.source_language.itemData(i) for i in range(1, page.source_language.count())] == [
        page.target.itemData(i) for i in range(page.target.count())
    ]
    page.source_language.setCurrentText("Russian")
    assert changed.count() == 1
    assert changed.at(0) == [{"translation_source_language": "ru"}]
    page.apply_settings(replace(page.settings, translation_source_language="ja"))
    assert page.source_language.currentText() == "Japanese"
    assert changed.count() == 1
    assert not page.result.text.isReadOnly()


@pytest.mark.parametrize("automatic", [False, True])
def test_explicit_swap_exchanges_both_texts_and_languages_then_sends_once(qtbot, automatic):
    page = make_page(qtbot, translation_source_language="ja", translation_auto_send=automatic)
    page.source.text.setPlainText("おはよう")
    page.set_result(TranslationResult("Good morning", "ohayou", "gud morning", "おはよう。"))
    page.result.text.setPlainText("Edited translation")
    manual, auto = QSignalSpy(page.requested), QSignalSpy(page.automatic_requested)
    changes = QSignalSpy(page.options_changed)
    revisions = (page.source.audio.revision, page.result.audio.revision)
    assert page.swap_button.isEnabled()
    page.swap_button.click()
    assert changes.count() == 1
    assert changes.at(0) == [{"translation_source_language": "en", "target_language": "Japanese"}]
    assert page.source.text.toPlainText() == "Edited translation"
    assert page.result.text.toPlainText() == "おはよう"
    assert page.source_language.currentText() == "English"
    assert page.target.currentText() == "Japanese"
    assert page.settings.translation_source_language == "en"
    assert manual.count() == 1 and manual.at(0) == ["Edited translation"]
    assert page.source.pronunciation.text.toPlainText() == ""
    assert page.result.pronunciation.text.toPlainText() == ""
    assert page.suggestion.isHidden()
    assert page.source.audio.revision > revisions[0]
    assert page.result.audio.revision > revisions[1]
    qtbot.wait(250)
    assert auto.count() == 0 and manual.count() == 1


def test_auto_swap_requires_latest_valid_detected_source_and_does_not_guess(qtbot):
    page = make_page(qtbot, translation_auto_send=False)
    page.source.text.setPlainText("こんにちは")
    page.result.text.setPlainText("Hello")
    assert not page.swap_button.isEnabled()
    assert "Choose" in page.swap_button.toolTip()
    for detected in ("", "xx-unsupported"):
        page.set_result(TranslationResult("Hello", source_language=detected))
        assert not page.swap_button.isEnabled()
    page.set_result(TranslationResult("Hello", source_language="ja"), "こんにちは", "English", "")
    assert page.swap_button.isEnabled()
    page.source.text.setPlainText("different source")
    assert not page.swap_button.isEnabled()
    assert not page.set_result(TranslationResult("Hello", source_language="ja"), "こんにちは")
    assert not page.swap_button.isEnabled()
    page.source.text.setPlainText("こんにちは")
    page.set_result(TranslationResult("Hello", source_language="ja"))
    page.swap_button.click()
    assert page.source_language.currentData() == "en"
    assert page.target.currentText() == "Japanese"
    assert page.source.text.toPlainText() == "Hello"


def test_detected_language_survives_auto_toggle_but_source_language_change_clears_it(qtbot):
    page = make_page(qtbot)
    page.source.text.setPlainText("こんにちは")
    page.set_result(TranslationResult("Hello", source_language="ja"))
    page.apply_settings(replace(page.settings, translation_auto_send=False))
    assert page.swap_button.isEnabled()
    page.source_language.setCurrentText("Russian")
    assert not page.set_result(TranslationResult("stale", source_language="ja"), source_language="")
    page.source_language.setCurrentText("Auto detect")
    assert not page.swap_button.isEnabled()


def test_source_selection_invalidates_running_intent_and_debounces_latest_request(qtbot):
    page = make_page(qtbot)
    sent = QSignalSpy(page.automatic_requested)
    invalidated = QSignalSpy(page.invalidated)
    page.source.text.setPlainText("a word")
    page.set_result(TranslationResult("word", "pronunciation", "result pronunciation"))
    page.source_language.setCurrentText("English")
    assert page.source.pronunciation.text.toPlainText() == ""
    assert page.result.pronunciation.text.toPlainText() == ""
    page.source_language.setCurrentText("French")
    qtbot.waitUntil(lambda: sent.count() == 1)
    assert page.settings.translation_source_language == "fr"
    assert invalidated.count() >= 3
    assert sent.at(0) == ["a word"]
    qtbot.wait(250)
    assert sent.count() == 1


def test_blank_translation_and_custom_unsupported_target_disable_swap(qtbot):
    page = make_page(qtbot, translation_source_language="ja", translation_auto_send=False)
    assert not page.swap_button.isEnabled()
    page.source.text.setPlainText("こんにちは")
    page.result.text.setPlainText("  ")
    assert not page.swap_button.isEnabled()
    page.apply_settings(replace(page.settings, target_language="Custom language"))
    page.result.text.setPlainText("translated")
    assert not page.swap_button.isEnabled()
    requested = QSignalSpy(page.requested)
    page.swap()
    assert requested.count() == 0


def test_source_language_option_is_scoped_to_translate_and_has_reset(qtbot):
    panel = ToolSettings("translate", Settings(translation_source_language="ja"))
    captions = ToolSettings("output", Settings())
    qtbot.addWidget(panel)
    qtbot.addWidget(captions)
    assert panel.translation_source_language.currentText() == "Japanese"
    panel.translation_source_language.setCurrentText("English")
    assert panel.collect()["translation_source_language"] == "en"
    panel.reset_buttons["translation_source_language"].click()
    assert panel.collect()["translation_source_language"] == ""
    assert "translation_source_language" not in captions.collect()
