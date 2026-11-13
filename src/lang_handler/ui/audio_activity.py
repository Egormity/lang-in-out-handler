"""A compact, recording-only audio status; no full-width meter."""

import math

from PySide6.QtWidgets import QLabel


class AudioActivity(QLabel):
    def __init__(self):
        super().__init__()
        self.setObjectName("muted")
        self.setAccessibleName("Audio activity")
        self.recording = False
        self.hide()

    def set_recording(self, active):
        self.recording = active
        self.setVisible(active)
        self.set_level(0)

    def set_level(self, amplitude):
        if not self.recording:
            return
        audible = math.isfinite(amplitude) and amplitude > 0.001
        self.setText("● Audio detected" if audible else "Listening…")
        self.setToolTip("Incoming audio detected." if audible else "Waiting for audio from the selected source.")
