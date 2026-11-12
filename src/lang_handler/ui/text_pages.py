"""Translation and text-to-speech pages."""

import shutil
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QPlainTextEdit,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .common import TextPane, button, label, title_block


class TranslatePage(QWidget):
    requested = Signal(str)

    def __init__(self, settings):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(14)
        layout.addWidget(
            title_block("Translate", "Carry the meaning across languages, in your own style.")
        )
        self.target = label(f"Target language: {settings.target_language} · change in Preferences")
        layout.addWidget(self.target)
        layout.addWidget(label("Instructions"))
        self.instructions = QPlainTextEdit(settings.translation_instructions)
        self.instructions.setMaximumHeight(90)
        layout.addWidget(self.instructions)
        split = QSplitter()
        self.source = TextPane("Original text", "Paste or type the text to translate…", False)
        self.result = TextPane("Translation", "Your translation will appear here.")
        split.addWidget(self.source)
        split.addWidget(self.result)
        layout.addWidget(split, 1)
        row = QHBoxLayout()
        row.addStretch()
        self.run = button("Translate text", True)
        self.run.clicked.connect(lambda: self.requested.emit(self.source.text.toPlainText()))
        row.addWidget(self.run)
        layout.addLayout(row)


class SpeechPage(QWidget):
    requested = Signal(str)
    stop_requested = Signal()
    replay_requested = Signal(str)

    def __init__(self, settings):
        super().__init__()
        self.path = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(14)
        layout.addWidget(
            title_block("Text to speech", "Listen to text with an AI-generated voice.")
        )
        self.voice = label(f"Voice: {settings.voice} · change in Preferences")
        layout.addWidget(self.voice)
        layout.addWidget(label("Voice instructions"))
        self.instructions = QPlainTextEdit(settings.tts_instructions)
        self.instructions.setPlaceholderText("Describe pace, emotion, accent, or speaking style…")
        self.instructions.setMaximumHeight(90)
        layout.addWidget(self.instructions)
        self.source = TextPane("Text to read", "Paste or type the text you want to hear…", False)
        layout.addWidget(self.source, 1)
        self.file_label = label("No audio generated yet.", True)
        layout.addWidget(self.file_label)
        row = QHBoxLayout()
        self.save = button("Save audio…")
        self.save.setEnabled(False)
        self.save.clicked.connect(self._save)
        self.play = button("Play again")
        self.play.setEnabled(False)
        self.play.clicked.connect(lambda: self.replay_requested.emit(self.path))
        stop = button("Stop playback")
        stop.clicked.connect(self.stop_requested)
        row.addWidget(self.save)
        row.addWidget(self.play)
        row.addWidget(stop)
        row.addStretch()
        self.run = button("Generate & play", True)
        self.run.clicked.connect(lambda: self.requested.emit(self.source.text.toPlainText()))
        row.addWidget(self.run)
        layout.addLayout(row)

    def set_audio(self, path: str):
        self.path = path
        self.file_label.setText(f"Ready: {Path(path).name}")
        self.file_label.setToolTip(path)
        self.save.setEnabled(True)
        self.play.setEnabled(True)

    def _save(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save generated speech", "speech.wav", "WAV audio (*.wav)"
        )
        if path and Path(path).resolve() != Path(self.path).resolve():
            shutil.copy2(self.path, path)
