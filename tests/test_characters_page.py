"""Compose kana at the cursor, keep drafts, and translate a Japanese input once."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication

from lang_handler.settings import Settings
from lang_handler.ui.characters_page import CharactersPage
from lang_handler.ui.main_window import MainWindow


@pytest.fixture
def page(qtbot):
    widget = CharactersPage()
    qtbot.addWidget(widget)
    widget.resize(700, 700)
    widget.show()
    return widget


def test_kana_clicks_replace_selection_and_support_native_undo_and_backspace(page, qtbot):
    page.editor.setPlainText("あいう")
    cursor = page.editor.textCursor()
    cursor.setPosition(1)
    cursor.setPosition(2, QTextCursor.MoveMode.KeepAnchor)
    page.editor.setTextCursor(cursor)
    qtbot.mouseClick(page.keyboard.keys["か"], Qt.MouseButton.LeftButton)
    assert page.editor.toPlainText() == "あかう"
    page.editor.undo()
    assert page.editor.toPlainText() == "あいう"
    page.editor.redo()
    page.backspace_button.click()
    assert page.editor.toPlainText() == "あう"
    cursor = page.editor.textCursor()
    cursor.select(QTextCursor.SelectionType.Document)
    page.editor.setTextCursor(cursor)
    page.backspace_button.click()
    assert page.editor.toPlainText() == ""
    assert not page.translate_button.isEnabled()
    assert page.clear_button.isHidden()


def test_scripts_share_composer_and_copy_speech_actions(page, qtbot):
    page.keyboard.keys["あ"].click()
    page.keyboard.tabs.setCurrentIndex(1)
    page.keyboard.keys["カ"].click()
    page.keyboard.keys["ー"].click()
    assert page.editor.toPlainText() == "あカー"
    assert page.language.count() == 1
    assert page.language.currentText() == "Japanese"
    assert page.language.currentData() == "ja"
    assert not page.language.isEditable()
    page.composer.copy.click()
    assert QApplication.clipboard().text() == "あカー"
    assert page.composer.copy.accessibleName() == "Copied to clipboard"
    speech = QSignalSpy(page.audio_requested)
    page.composer.speak.click()
    assert speech.count() == 1
    assert speech.at(0)[0] == "あカー"
    page.clear_button.click()
    assert page.editor.toPlainText() == ""


@pytest.mark.parametrize("automatic", [False, True])
def test_characters_send_to_translate_sets_japanese_and_submits_once(qtbot, automatic):
    window = MainWindow(Settings(translation_auto_send=automatic), True)
    qtbot.addWidget(window)
    window.settings_saved.connect(window.settings_save_succeeded)
    window.nav_buttons["characters"].click()
    page = window.pages["characters"]
    page.insert_text("ともだち")
    translated = QSignalSpy(window.translate_requested)
    automatic_requests = QSignalSpy(window.automatic_translate_requested)
    page.translate_button.click()
    assert window.stack.currentWidget() is window.pages["translate"]
    assert window.settings.translation_source_language == "ja"
    assert window.pages["translate"].source.text.toPlainText() == "ともだち"
    assert translated.count() == 1
    assert translated.at(0) == ["ともだち"]
    assert not window.pages["translate"].timer.isActive()
    assert automatic_requests.count() == 0
    window.show_page("characters")
    assert page.editor.toPlainText() == "ともだち"


def test_failed_language_save_preserves_composer_without_submitting(qtbot):
    window = MainWindow(Settings(), True)
    qtbot.addWidget(window)
    window.settings_saved.connect(lambda _: window.settings_save_failed())
    window.show_page("characters")
    page = window.pages["characters"]
    page.insert_text("あ")
    translated = QSignalSpy(window.translate_requested)
    page.translate_button.click()
    assert translated.count() == 0
    assert window.stack.currentWidget() is page
    assert page.editor.toPlainText() == "あ"
