"""A quiet pronunciation guide immediately below its text."""

from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QWidget

from .text_edit import GrowingTextEdit


class PronunciationGuide(QWidget):
    def __init__(self):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(4)
        self.text = GrowingTextEdit(minimum=38)
        self.text.setObjectName("pronunciationText")
        self.text.setReadOnly(True)
        self.text.setAccessibleName("Pronunciation guide")
        layout.addWidget(self.text, 1)
        self.hide()

    def set_text(self, text):
        self.text.setPlainText(text)
        self.setVisible(bool(text.strip()))
