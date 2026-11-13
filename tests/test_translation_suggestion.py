"""Correction suggestions require an explicit action and render model text literally."""

from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy

from lang_handler.results import TranslationResult
from lang_handler.settings import Settings
from lang_handler.ui.text_pages import TranslatePage
from lang_handler.ui.translation_suggestion import TranslationSuggestion


def test_suggestion_is_applied_only_when_clicked(qtbot):
    suggestion = TranslationSuggestion()
    qtbot.addWidget(suggestion)
    applied = QSignalSpy(suggestion.applied)
    suggestion.set_suggestion("これはねこです。", "これはぬこです。")
    assert not suggestion.isHidden()
    assert applied.count() == 0
    suggestion.use_button.click()
    assert applied.at(0) == ["これはねこです。"]
    assert suggestion.isHidden()
    suggestion.use_button.click()
    assert applied.count() == 1


def test_dismissal_and_empty_corrections_do_not_apply(qtbot):
    suggestion = TranslationSuggestion()
    qtbot.addWidget(suggestion)
    applied = QSignalSpy(suggestion.applied)
    suggestion.set_suggestion("Hello", "Helo")
    suggestion.dismiss_button.click()
    assert suggestion.isHidden()
    assert applied.count() == 0
    for correction in ("", "  Helo  "):
        suggestion.set_suggestion(correction, "Helo")
        assert suggestion.isHidden()


def test_model_text_cannot_be_rendered_as_rich_html(qtbot):
    suggestion = TranslationSuggestion()
    qtbot.addWidget(suggestion)
    value = '<a href="https://example.com">hello</a>'
    suggestion.set_suggestion(value)
    assert suggestion.text.textFormat() == Qt.TextFormat.PlainText
    assert suggestion.text.text() == value


def test_translation_page_keeps_original_until_suggestion_is_applied(qtbot):
    page = TranslatePage(Settings())
    qtbot.addWidget(page)
    original = "これはぬこです。"
    corrected = "これはねこです。"
    page.source.text.setPlainText(original)
    requested = QSignalSpy(page.requested)
    result = TranslationResult("This is a kitteh.", "Kore wa nuko desu.", "", corrected)
    assert page.set_result(result, original, "English")
    assert page.source.text.toPlainText() == original
    assert page.result.text.toPlainText() == "This is a kitteh."
    assert page.source.pronunciation.text.toPlainText() == "Kore wa nuko desu."
    assert requested.count() == 0
    assert page.source.content_layout.indexOf(page.suggestion) == 2
    page.suggestion.use_button.click()
    assert page.source.text.toPlainText() == corrected
    assert page.suggestion.isHidden()
    assert requested.at(0) == [corrected]


def test_editing_source_or_target_invalidates_previous_suggestion(qtbot):
    page = TranslatePage(Settings())
    qtbot.addWidget(page)
    page.source.text.setPlainText("Helo")
    result = TranslationResult("こんにちは", source_correction="Hello")
    assert page.set_result(result, "Helo", "English")
    page.source.text.setPlainText("Something else")
    assert page.suggestion.isHidden()
    assert not page.set_result(result, "Helo", "English")
    assert page.suggestion.isHidden()
    page.source.text.setPlainText("Helo")
    page.set_result(result)
    page.target.setCurrentText("Japanese")
    assert page.suggestion.isHidden()
    page.set_result(result)
    page.apply_settings(Settings(target_language="German"))
    assert page.suggestion.isHidden()


def test_suggestion_cannot_replace_source_during_an_active_translation(qtbot):
    page = TranslatePage(Settings())
    qtbot.addWidget(page)
    page.source.text.setPlainText("Helo")
    page.set_result(TranslationResult("こんにちは", source_correction="Hello"))
    requested = QSignalSpy(page.requested)
    page.set_busy(True)
    page.suggestion.use_button.click()
    assert page.source.text.toPlainText() == "Helo"
    assert requested.count() == 0
    page.set_busy(False)
    page.suggestion.use_button.click()
    assert requested.at(0) == ["Hello"]
