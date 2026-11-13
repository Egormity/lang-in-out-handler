"""Quiet controls for the last generated audio, shown in speech preferences."""

import shutil
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QMessageBox, QWidget

from .icons import icon_button


class SpeechControls(QWidget):
    stop_requested = Signal()
    replay_requested = Signal(str)

    def __init__(self):
        super().__init__()
        self.path = ""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.stop = icon_button("stop", "Stop audio")
        self.stop.clicked.connect(self.stop_requested)
        self.play = icon_button("replay", "Replay last audio")
        self.play.setEnabled(False)
        self.play.clicked.connect(lambda: self.replay_requested.emit(self.path))
        self.save = icon_button("save", "Save last audio")
        self.save.setEnabled(False)
        self.save.clicked.connect(self._save)
        layout.addWidget(self.stop)
        layout.addWidget(self.play)
        layout.addWidget(self.save)
        layout.addStretch()

    def set_audio(self, path):
        self.path = path
        self.play.setEnabled(True)
        self.save.setEnabled(True)

    def _save(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save generated speech", "speech.wav", "WAV audio (*.wav)")
        if path and Path(path).resolve() != Path(self.path).resolve():
            try:
                shutil.copy2(self.path, path)
            except OSError as error:
                QMessageBox.warning(self, "Could not save audio", str(error))
