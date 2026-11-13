"""Paint a real alpha background without relying on compositor-wide window opacity."""

import math

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

# Ordinary child containers must not cover the alpha surface with the theme's
# opaque QWidget background. Dropdown menus remain opaque for readability.
TRANSLUCENT_CONTENT_STYLE = """
QWidget[translucentSurface="true"], QWidget[translucentSurface="true"] QWidget {
    background: transparent;
}
QWidget[translucentSurface="true"] QComboBox QAbstractItemView,
QWidget[translucentSurface="true"] QComboBox QAbstractItemView QWidget {
    background: #252d28;
}
"""


class TranslucentWindow(QWidget):
    """Only the client-area background fades; text and controls retain their alpha."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._background_opacity = 1.0
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAutoFillBackground(False)
        self.setProperty("translucentSurface", True)

    @property
    def background_opacity(self):
        return self._background_opacity

    def set_background_opacity(self, opacity):
        opacity = float(opacity)
        self._background_opacity = min(1.0, max(0.0, opacity)) if math.isfinite(opacity) else 1.0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        # Source replaces the previous buffer pixels, so repeated paints cannot
        # accumulate alpha and turn a half-transparent window opaque again.
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        background = QColor("#1d2021")
        background.setAlpha(round(self._background_opacity * 255))
        painter.fillRect(self.rect(), background)
        painter.end()
