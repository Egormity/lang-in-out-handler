"""Clipboard action with brief, local confirmation."""

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import QApplication, QPushButton

from .icons import icon


class CopyButton(QPushButton):
    def __init__(self, description, text_provider):
        super().__init__()
        self.description = description
        self.text_provider = text_provider
        self.setObjectName("iconButton")
        self.setFixedSize(36, 36)
        self.setIconSize(QSize(18, 18))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(1400)
        self.timer.timeout.connect(self.reset_feedback)
        self.clicked.connect(self._copy)
        self.reset_feedback()

    def _copy(self):
        text = self.text_provider()
        if not text.strip():
            return
        QApplication.clipboard().setText(text)
        self.setIcon(icon("check"))
        self.setToolTip("Copied to clipboard")
        self.setAccessibleName("Copied to clipboard")
        self.timer.start()

    def reset_feedback(self):
        self.timer.stop()
        self.setIcon(icon("copy"))
        self.setText("")
        self.setToolTip(self.description)
        self.setAccessibleName(self.description)
