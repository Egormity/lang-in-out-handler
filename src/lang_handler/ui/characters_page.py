"""Compose Japanese text locally with selectable hiragana and katakana keys."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from .character_keyboard import CharacterKeyboard
from .common import TextPane, button, label, selection_combo
from .icons import icon_button


class CharactersPage(QWidget):
    translate_requested = Signal(str)
    audio_requested = Signal(str, object)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(14)
        heading = QHBoxLayout()
        title = label("Characters")
        title.setObjectName("title")
        heading.addWidget(title, 1)
        self.language = selection_combo(["Japanese"], "Japanese")
        self.language.setItemData(0, "ja")
        self.language.setAccessibleName("Character input language")
        self.language.setFixedWidth(160)
        heading.addWidget(self.language)
        self.translate_button = button("Translate", True)
        self.translate_button.clicked.connect(self._translate)
        heading.addWidget(self.translate_button)
        layout.addLayout(heading)
        self.composer = TextPane("Character input", "Click kana below or type here…", False)
        self.composer.heading.hide()
        self.composer.setFixedHeight(155)
        self.editor = self.composer.text
        self.backspace_button = icon_button("backspace", "Backspace")
        self.backspace_button.clicked.connect(self.backspace)
        self.clear_button = icon_button("clear", "Clear character input")
        self.clear_button.clicked.connect(self.editor.clear)
        self.composer.actions.insertWidget(0, self.backspace_button)
        self.composer.actions.insertWidget(1, self.clear_button)
        self.composer.audio_requested.connect(self.audio_requested)
        self.editor.textChanged.connect(self._text_changed)
        layout.addWidget(self.composer)
        self.keyboard = CharacterKeyboard()
        self.keyboard.inserted.connect(self.insert_text)
        layout.addWidget(self.keyboard, 1)
        self._text_changed()

    def insert_text(self, text):
        # QTextCursor preserves insertion/selection semantics and native undo.
        self.editor.insertPlainText(text)
        self.editor.setFocus(Qt.FocusReason.OtherFocusReason)

    def backspace(self):
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            cursor.removeSelectedText()
        else:
            cursor.deletePreviousChar()
        self.editor.setTextCursor(cursor)
        self.editor.setFocus(Qt.FocusReason.OtherFocusReason)

    def _text_changed(self):
        text = self.editor.toPlainText()
        self.translate_button.setEnabled(bool(text.strip()))
        self.backspace_button.setEnabled(bool(text))
        self.clear_button.setVisible(bool(text))

    def _translate(self):
        text = self.editor.toPlainText()
        if text.strip():
            self.translate_requested.emit(text)
