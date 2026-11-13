"""Selectable handwriting candidates with an action for each reading."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from .common import label
from .copy_button import CopyButton
from .icons import icon_button
from .inline_audio import InlineAudio


class CandidateRow(QWidget):
    speech_requested = Signal(str)
    audio_requested = Signal(str, object)

    def __init__(self, text: str, index: int):
        super().__init__()
        self.text = text
        self.setObjectName("candidateRow")
        row = QHBoxLayout(self)
        row.setContentsMargins(4, 5, 4, 5)
        row.setSpacing(6)
        reading = QLabel(text)
        reading.setWordWrap(True)
        reading.setStyleSheet("font-size: 20px;")
        reading.setTextFormat(Qt.TextFormat.PlainText)
        reading.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        reading.setAccessibleName(f"Candidate {index}: {text}")
        row.addWidget(reading, 1)
        self.copy = CopyButton(f"Copy candidate {index}", lambda: self.text)
        self.copy.setObjectName("quiet")
        self.copy.setAccessibleName(f"Copy candidate {index}")
        row.addWidget(self.copy)
        self.audio = InlineAudio()
        self.speak = self.audio.speak
        self.speak.setObjectName("quiet")
        self.speak.setAccessibleName(f"Speak candidate {index}")
        self.audio.requested.connect(self._request_audio)
        row.addWidget(self.audio)

    def _request_audio(self):
        self.speech_requested.emit(self.text)
        self.audio_requested.emit(self.text, self.audio)


class DrawingCandidates(QWidget):
    speech_requested = Signal(str)
    audio_requested = Signal(str, object)
    speech_stop_requested = Signal()

    def __init__(self):
        super().__init__()
        self.rows = []
        self.items = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        header = QHBoxLayout()
        header.addStretch()
        self.stop = icon_button("stop", "Stop audio")
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
        self.setMinimumHeight(90)
        self.setMaximumHeight(190)

    def set_items(self, items: list[str]):
        self.clear()
        self.items = list(items)
        self.empty.setVisible(not self.items)
        for index, text in enumerate(self.items, 1):
            row = CandidateRow(text, index)
            row.speech_requested.connect(self.speech_requested)
            row.audio_requested.connect(self.audio_requested)
            self.rows.append(row)
            self.rows_layout.insertWidget(len(self.rows) - 1, row)

    def clear(self):
        self.items = []
        for row in self.rows:
            row.audio.reset()
            self.rows_layout.removeWidget(row)
            row.hide()
            row.deleteLater()
        self.rows.clear()
        self.empty.show()

    def set_speech_active(self, active):
        self.stop.setVisible(active)
