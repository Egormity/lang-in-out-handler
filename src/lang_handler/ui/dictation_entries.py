"""Individually selectable dictation results, each with its own copy and speech actions."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLayout, QScrollArea, QVBoxLayout, QWidget

from .common import label
from .copy_button import CopyButton
from .inline_audio import InlineAudio
from .pronunciation import PronunciationGuide
from .text_edit import GrowingTextEdit


class DictationEntry(QWidget):
    speech_requested = Signal(str)
    audio_requested = Signal(str, object)

    def __init__(self, text, pronunciation=""):
        super().__init__()
        self.setObjectName("dictationEntry")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 10, 8, 10)
        layout.setSpacing(4)
        self.text = GrowingTextEdit(minimum=44)
        self.text.setObjectName("contentText")
        self.text.setReadOnly(True)
        self.text.setAccessibleName("Dictation result")
        self.text.setTabChangesFocus(True)
        layout.addWidget(self.text)
        self.pronunciation = PronunciationGuide()
        layout.addWidget(self.pronunciation)
        actions = QHBoxLayout()
        actions.setSpacing(4)
        actions.addStretch()
        self.copy = CopyButton("Copy this dictation", self.text.toPlainText)
        self.audio = InlineAudio()
        self.speak = self.audio.speak
        self.speak.setAccessibleName("Speak this dictation")
        self.speak.setToolTip("Read selected text, or this dictation result.")
        self.audio.requested.connect(self._speak)
        actions.addWidget(self.copy)
        actions.addWidget(self.audio)
        layout.addLayout(actions)
        self.set_result(text, pronunciation)

    def _speak(self):
        text = (self.text.textCursor().selectedText().replace("\u2029", "\n")
                or self.text.toPlainText())
        self.speech_requested.emit(text)
        self.audio_requested.emit(text, self.audio)

    def set_result(self, text, pronunciation=""):
        if self.text.toPlainText() != text:
            self.audio.reset()
            self.text.setPlainText(text)
            self.copy.reset_feedback()
        self.pronunciation.set_text(pronunciation)
        self.copy.setEnabled(bool(text.strip()))
        self.speak.setEnabled(bool(text.strip()))


class DictationEntries(QWidget):
    speech_requested = Signal(str)
    audio_requested = Signal(str, object)
    content_changed = Signal()

    def __init__(self, title="Transcript", placeholder="Your words appear here."):
        super().__init__()
        self.entries = []
        self._segments = {}
        self._anonymous = 0
        self._following = True
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        self.heading = label(title, True)
        layout.addWidget(self.heading)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.body = QWidget()
        self.body.setObjectName("textBody")
        self.rows = QVBoxLayout(self.body)
        self.rows.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.rows.setContentsMargins(0, 0, 0, 0)
        self.rows.setSpacing(8)
        self.empty = label(placeholder, True)
        self.empty.setStyleSheet("font-size: 22px; padding: 8px;")
        self.rows.addWidget(self.empty)
        self.rows.addStretch(1)
        self.scroll.setWidget(self.body)
        layout.addWidget(self.scroll, 1)
        scrollbar = self.scroll.verticalScrollBar()
        scrollbar.rangeChanged.connect(self._range_changed)
        scrollbar.valueChanged.connect(self._position_changed)

    @property
    def speak(self):
        return self.entries[-1].speak

    @property
    def copy(self):
        return self.entries[-1].copy

    @property
    def audio(self):
        return self.entries[-1].audio

    def append(self, text, pronunciation="", *, segment_id=None):
        if not text.strip():
            return
        if segment_id is None:
            self._anonymous += 1
            segment_id = ("local", self._anonymous)
        if segment_id in self._segments:
            self._segments[segment_id].set_result(text.strip(), pronunciation.strip())
            self.content_changed.emit()
            return
        entry = DictationEntry(text.strip(), pronunciation.strip())
        entry.speech_requested.connect(self.speech_requested)
        entry.audio_requested.connect(self.audio_requested)
        self._segments[segment_id] = entry
        self.entries.append(entry)
        self.empty.hide()
        self.rows.insertWidget(len(self.entries) - 1, entry)
        self.content_changed.emit()

    def contains(self, segment_id):
        return segment_id in self._segments

    def revise(self, segment_id, text=None, pronunciation=""):
        if not self.contains(segment_id):
            return False
        entry = self._segments[segment_id]
        entry.set_result(entry.text.toPlainText() if text is None else text, pronunciation)
        self.content_changed.emit()
        return True

    def clear(self):
        for entry in self.entries:
            entry.audio.reset()
            self.rows.removeWidget(entry)
            entry.hide()
            entry.deleteLater()
        self.entries.clear()
        self._segments.clear()
        self.empty.show()
        self._following = True
        self.content_changed.emit()

    def toPlainText(self):
        return "\n".join(entry.text.toPlainText() for entry in self.entries)

    def _range_changed(self, minimum, maximum):
        if self._following:
            self.scroll.verticalScrollBar().setValue(maximum)

    def _position_changed(self, position):
        self._following = position >= self.scroll.verticalScrollBar().maximum() - 4
