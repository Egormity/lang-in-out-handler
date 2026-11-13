"""Mouse and tablet handwriting canvas with revisioned, vector-backed strokes."""

from dataclasses import dataclass

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QSizePolicy, QWidget

from .canvas_snapshot import recognition_snapshot
from .tablet_input import TabletInputMixin

Stroke = tuple[float, list[tuple[float, float]]]


@dataclass
class DrawingEdit:
    added: list[Stroke]
    removed: list[Stroke]


class DrawingCanvas(TabletInputMixin, QWidget):
    changed = Signal(int)

    def __init__(self):
        super().__init__()
        self.strokes: list[Stroke] = []
        self._undo_stack: list[DrawingEdit] = []
        self._redo_stack: list[DrawingEdit] = []
        self.revision = 0
        self.is_drawing = False
        self.pen_width = 4
        self.theme = "light"
        self.initialize_input()
        self.setMinimumSize(350, 210)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setAccessibleName("Handwriting canvas")

    @property
    def is_blank(self):
        return not self.strokes

    @property
    def can_undo(self):
        return bool(self._undo_stack)

    @property
    def can_redo(self):
        return bool(self._redo_stack)

    def _record(self, edit):
        self._undo_stack.append(edit)
        self._redo_stack.clear()

    def _point(self, position):
        return (
            max(0, min(1, position.x() / self.width())),
            max(0, min(1, position.y() / self.height())),
        )

    def _changed(self):
        self.revision += 1
        self.update()
        self.changed.emit(self.revision)

    def begin_stroke(self, position):
        self.is_drawing = True
        self._last_position = QPointF(position)
        stroke = (self.pen_width, [self._point(position)])
        self._record(DrawingEdit(added=[stroke], removed=[]))
        self.strokes.append(stroke)
        self._changed()

    def extend_stroke(self, position):
        if self.is_drawing and self.strokes:
            self._last_position = QPointF(position)
            self.strokes[-1][1].append(self._point(position))
            self._changed()

    def end_stroke(self, position):
        if self.is_drawing:
            self.extend_stroke(position)
            self.is_drawing = False
            self._stroke_source = None
            self._changed()

    def undo(self):
        if not self.can_undo:
            return
        edit = self._undo_stack.pop()
        self.is_drawing = False
        self._stroke_source = None
        if edit.added:
            del self.strokes[-len(edit.added):]
        self.strokes.extend(edit.removed)
        self._redo_stack.append(edit)
        self._changed()

    def redo(self):
        if not self.can_redo:
            return
        edit = self._redo_stack.pop()
        self.is_drawing = False
        self._stroke_source = None
        if edit.removed:
            del self.strokes[-len(edit.removed):]
        self.strokes.extend(edit.added)
        self._undo_stack.append(edit)
        self._changed()

    def clear(self):
        if self.is_blank:
            return
        self._record(DrawingEdit(added=[], removed=self.strokes.copy()))
        self.strokes.clear()
        self.is_drawing = False
        self._stroke_source = None
        self._changed()

    def set_theme(self, theme):
        """Appearance changes leave drawing history and recognition revisions intact."""
        self.theme = theme if theme in {"light", "dark"} else "light"
        self.update()

    def _paint_strokes(self, painter, width, height, *, preview=False):
        # Keep API snapshots canonical so appearance never changes recognition input.
        dark = preview and self.theme == "dark"
        painter.fillRect(0, 0, width, height, QColor("#222725" if dark else "white"))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for pen_width, points in self.strokes:
            pen = QPen(
                QColor("#f0f3ef" if dark else "#111111"),
                pen_width,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
            painter.setPen(pen)
            polygon = QPolygonF([QPointF(x * width, y * height) for x, y in points])
            if len(polygon) == 1:
                painter.drawPoint(polygon[0])
            else:
                painter.drawPolyline(polygon)

    def paintEvent(self, event):
        painter = QPainter(self)
        self._paint_strokes(painter, self.width(), self.height(), preview=True)
        if self.is_blank:
            painter.setPen(QColor("#a4b0a9" if self.theme == "dark" else "#6f7a74"))
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, "Write here with your mouse or pen"
            )
        painter.end()

    def snapshot(self) -> bytes:
        return recognition_snapshot(self)
