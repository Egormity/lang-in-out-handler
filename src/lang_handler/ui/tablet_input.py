"""Pen contact handling shared by the handwriting canvas input handlers."""

import time

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtWidgets import QApplication


class TabletInputMixin:
    """Recover missing tablet presses while leaving unsupported events to Qt.

    Some tablet/XWayland drivers deliver a pressure-bearing move when a tip
    enters a widget that did not receive its press. Treat contact, rather than
    an earlier press alone, as sufficient to start a stroke. Hover never inks.
    """

    def initialize_input(self):
        self._stroke_source = None
        self._last_position = QPointF()
        self._last_tablet_position = QPointF()
        self._last_tablet_time = -1.0
        self.setTabletTracking(True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        application = QApplication.instance()
        if application:
            application.installEventFilter(self)

    def _finish_input(self, position=None):
        if self.is_drawing:
            self.end_stroke(position if position is not None else self._last_position)
        self._stroke_source = None

    def _start_or_extend(self, position, source):
        self._last_position = QPointF(position)
        if self.is_drawing and self._stroke_source not in (None, source):
            self._finish_input()
        if not self.is_drawing:
            self._stroke_source = source
            self.begin_stroke(position)
        else:
            self.extend_stroke(position)

    def _duplicate_mouse(self, event):
        if self._stroke_source == "tablet" and self.is_drawing:
            return True
        if time.monotonic() - self._last_tablet_time > 0.12:
            return False
        delta = event.position() - self._last_tablet_position
        nearby = abs(delta.x()) <= 4 and abs(delta.y()) <= 4
        synthesized = event.source() != Qt.MouseEventSource.MouseEventNotSynthesized
        return synthesized or nearby

    def mousePressEvent(self, event):
        if self._duplicate_mouse(event):
            event.accept()
        elif event.button() == Qt.MouseButton.LeftButton:
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            self._start_or_extend(event.position(), "mouse")
            event.accept()
        else:
            event.ignore()

    def mouseMoveEvent(self, event):
        if self._duplicate_mouse(event):
            event.accept()
        elif event.buttons() & Qt.MouseButton.LeftButton:
            self._start_or_extend(event.position(), "mouse")
            event.accept()
        elif self.is_drawing and self._stroke_source == "mouse":
            self._finish_input(event.position())
            event.accept()
        else:
            event.ignore()

    def mouseReleaseEvent(self, event):
        if self._duplicate_mouse(event):
            event.accept()
        elif event.button() == Qt.MouseButton.LeftButton and self._stroke_source == "mouse":
            self._finish_input(event.position())
            event.accept()
        else:
            event.ignore()

    def tabletEvent(self, event):
        kind = event.type()
        contact = event.pressure() > 0 or bool(event.buttons() & Qt.MouseButton.LeftButton)
        if kind == QEvent.Type.TabletRelease and event.button() == Qt.MouseButton.LeftButton:
            contact = False
        if kind not in (QEvent.Type.TabletPress, QEvent.Type.TabletMove, QEvent.Type.TabletRelease):
            event.ignore()
            return
        if contact:
            self._last_tablet_time = time.monotonic()
            self._last_tablet_position = QPointF(event.position())
            if kind == QEvent.Type.TabletPress:
                self.setFocus(Qt.FocusReason.MouseFocusReason)
            self._start_or_extend(event.position(), "tablet")
            event.accept()
        elif self.is_drawing and self._stroke_source == "tablet":
            self._last_tablet_time = time.monotonic()
            self._last_tablet_position = QPointF(event.position())
            self._finish_input(event.position())
            event.accept()
        else:
            # Preserve Qt's mouse fallback for hover, cursor devices, and events
            # we did not actually use; unconditional accept used to swallow it.
            event.ignore()

    def leaveEvent(self, event):
        self._finish_input()
        super().leaveEvent(event)

    def hideEvent(self, event):
        self._finish_input()
        super().hideEvent(event)

    def focusOutEvent(self, event):
        self._finish_input()
        super().focusOutEvent(event)

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Type.TabletLeaveProximity, QEvent.Type.ApplicationDeactivate):
            self._finish_input()
        return super().eventFilter(watched, event)
