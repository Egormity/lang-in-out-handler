"""Text editors that use their content height inside a shared scrolling pane."""

import math

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPlainTextEdit


class GrowingTextEdit(QPlainTextEdit):
    def __init__(self, *, minimum=90):
        super().__init__()
        self.minimum = minimum
        self._sizing = False
        self.setMinimumWidth(0)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.document().documentLayout().documentSizeChanged.connect(self.fit_content)
        self.textChanged.connect(self.fit_content)

    def fit_content(self, *_):
        if self._sizing:
            return
        self._sizing = True
        lines = max(1, self.document().documentLayout().documentSize().height())
        height = math.ceil(lines * self.fontMetrics().lineSpacing() + 18)
        self.setFixedHeight(max(self.minimum, min(16_000_000, height)))
        self._sizing = False

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_content()
