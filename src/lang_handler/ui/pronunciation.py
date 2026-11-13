"""A compact, selectable pronunciation guide attached to a text pane."""

from PySide6.QtWidgets import QApplication, QHBoxLayout, QPlainTextEdit, QVBoxLayout, QWidget

from .common import button, label


class PronunciationGuide(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(2)
        row = QHBoxLayout()
        row.addWidget(label("Pronunciation", True), 1)
        self.copy = button("Copy pronunciation")
        self.copy.setObjectName("quiet")
        row.addWidget(self.copy)
        layout.addLayout(row)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setAccessibleName("Pronunciation guide")
        self.text.setFixedHeight(64)
        self.text.setStyleSheet("font-size: 13px; color: #b6c9d2; padding: 2px;")
        self.copy.clicked.connect(lambda: QApplication.clipboard().setText(self.text.toPlainText()))
        layout.addWidget(self.text)
        self.hide()

    def set_text(self, text):
        self.text.setPlainText(text)
        self.setVisible(bool(text.strip()))
