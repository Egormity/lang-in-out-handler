"""Japanese kana charts that insert at the current cursor or replace a selection."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..kana import JAPANESE_PUNCTUATION, KANA_SECTIONS
from .common import button, label


class CharacterKeyboard(QWidget):
    inserted = Signal(str)

    def __init__(self):
        super().__init__()
        self.keys = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.tabs = QTabWidget()
        self.tabs.setAccessibleName("Japanese scripts")
        for script, title in (("hiragana", "Hiragana"), ("katakana", "Katakana")):
            self.tabs.addTab(self._chart(script), title)
        layout.addWidget(self.tabs, 1)
        punctuation = QHBoxLayout()
        punctuation.setSpacing(6)
        for character in JAPANESE_PUNCTUATION:
            punctuation.addWidget(self._key(character))
        punctuation.addStretch()
        layout.addLayout(punctuation)
        spacing = QHBoxLayout()
        for title, text in (("Space", " "), ("Enter", "\n")):
            control = button(title)
            control.clicked.connect(lambda checked=False, value=text: self.inserted.emit(value))
            spacing.addWidget(control)
        spacing.addStretch()
        layout.addLayout(spacing)

    def _key(self, character):
        key = button(character)
        key.setObjectName("kanaKey")
        key.setAccessibleName(f"Insert {character}")
        key.setMinimumSize(40, 42)
        key.clicked.connect(lambda checked=False: self.inserted.emit(character))
        self.keys[character] = key
        return key

    def _chart(self, script):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        columns = QHBoxLayout(body)
        columns.setContentsMargins(0, 12, 8, 8)
        columns.setSpacing(20)
        basic, variants = QVBoxLayout(), QVBoxLayout()
        for column in (basic, variants):
            column.setSpacing(10)
            columns.addLayout(column, 1)
        for index, (title, rows) in enumerate(KANA_SECTIONS[script]):
            column = basic if index == 0 else variants
            column.addWidget(label(title, True))
            grid = QGridLayout()
            grid.setSpacing(6)
            for row, characters in enumerate(rows):
                for cell, character in enumerate(characters):
                    if character:
                        grid.addWidget(self._key(character), row, cell)
            for cell in range(5):
                grid.setColumnMinimumWidth(cell, 40)
                grid.setColumnStretch(cell, 1)
            column.addLayout(grid)
        basic.addStretch()
        variants.addStretch()
        scroll.setWidget(body)
        return scroll
