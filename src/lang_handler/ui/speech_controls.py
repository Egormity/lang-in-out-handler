"""Shared generated-audio controls embedded in the translation tool."""

import shutil
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QMessageBox, QWidget

from .common import button, label


class SpeechControls(QWidget):
    stop_requested = Signal()
    replay_requested = Signal(str)

    def __init__(self):
        super().__init__()
        self.path = ""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.status = label("AI-generated voice", True)
        layout.addWidget(self.status, 1)
        self.stop = button("Stop audio")
        self.stop.clicked.connect(self.stop_requested)
        self.play = button("Play again")
        self.play.setEnabled(False)
        self.play.clicked.connect(lambda: self.replay_requested.emit(self.path))
        self.save = button("Save audio…")
        self.save.setEnabled(False)
        self.save.clicked.connect(self._save)
        layout.addWidget(self.stop)
        layout.addWidget(self.play)
        layout.addWidget(self.save)

    def set_audio(self, path):
        self.path = path
        self.status.setText("Audio ready")
        self.status.setToolTip(Path(path).name)
        self.play.setEnabled(True)
        self.save.setEnabled(True)

    def _save(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save generated speech", "speech.wav", "WAV audio (*.wav)"
        )
        if path and Path(path).resolve() != Path(self.path).resolve():
            try:
                shutil.copy2(self.path, path)
            except OSError as error:
                QMessageBox.warning(self, "Could not save audio", str(error))
