"""Selectable handwriting candidates with an action for each reading."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from .common import button, label


class CandidateRow(QWidget):
    speech_requested = Signal(str)

    def __init__(self, text: str, index: int):
        super().__init__()
        self.text = text
        row = QHBoxLayout(self)
        row.setContentsMargins(2, 2, 2, 2)
        row.setSpacing(6)
        reading = QLabel(text)
        reading.setWordWrap(True)
        reading.setTextFormat(Qt.TextFormat.PlainText)
        reading.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        reading.setAccessibleName(f"Candidate {index}: {text}")
        row.addWidget(reading, 1)
        self.copy = button("Copy")
        self.copy.setObjectName("quiet")
        self.copy.setAccessibleName(f"Copy candidate {index}")
        self.copy.clicked.connect(lambda: QApplication.clipboard().setText(self.text))
        row.addWidget(self.copy)
        self.speak = button("Speak")
        self.speak.setObjectName("quiet")
        self.speak.setAccessibleName(f"Speak candidate {index}")
        self.speak.clicked.connect(lambda: self.speech_requested.emit(self.text))
        row.addWidget(self.speak)


class DrawingCandidates(QWidget):
    speech_requested = Signal(str)
    speech_stop_requested = Signal()

    def __init__(self):
        super().__init__()
        self.rows = []
        self.items = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        header = QHBoxLayout()
        header.addWidget(label("Readings"), 1)
        self.stop = button("Stop audio")
        self.stop.setObjectName("quiet")
        self.stop.clicked.connect(self.speech_stop_requested)
        self.stop.hide()
        header.addWidget(self.stop)
        layout.addLayout(header)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.body = QWidget()
        self.rows_layout = QVBoxLayout(self.body)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(2)
        self.rows_layout.addStretch()
        self.scroll.setWidget(self.body)
        layout.addWidget(self.scroll)
        self.empty = label("Recognized readings will appear here.", True)
        self.rows_layout.insertWidget(0, self.empty)
        self.setMinimumHeight(110)

    def set_items(self, items: list[str]):
        self.clear()
        self.items = list(items)
        self.empty.setVisible(not self.items)
        for index, text in enumerate(self.items, 1):
            row = CandidateRow(text, index)
            row.speech_requested.connect(self.speech_requested)
            self.rows.append(row)
            self.rows_layout.insertWidget(len(self.rows) - 1, row)

    def clear(self):
        self.items = []
        for row in self.rows:
            self.rows_layout.removeWidget(row)
            row.hide()
            row.deleteLater()
        self.rows.clear()
        self.empty.show()

    def set_speech_active(self, active):
        self.stop.setVisible(active)
