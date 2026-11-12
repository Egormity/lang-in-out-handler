"""Mouse and tablet handwriting canvas with revisioned, vector-backed strokes."""

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QSizePolicy, QWidget


class DrawingCanvas(QWidget):
    changed = Signal(int)

    def __init__(self):
        super().__init__()
        self.strokes: list[tuple[float, list[tuple[float, float]]]] = []
        self.revision = 0
        self.is_drawing = False
        self.pen_width = 4
        self.setMinimumSize(350, 210)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setAccessibleName("Handwriting canvas")
        self.setToolTip("Draw with your mouse or pen. Undo removes the latest stroke.")

    @property
    def is_blank(self):
        return not self.strokes

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
        self.strokes.append((self.pen_width, [self._point(position)]))
        self._changed()

    def extend_stroke(self, position):
        if self.is_drawing and self.strokes:
            self.strokes[-1][1].append(self._point(position))
            self._changed()

    def end_stroke(self, position):
        if self.is_drawing:
            self.extend_stroke(position)
            self.is_drawing = False
            self._changed()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.begin_stroke(event.position())
            event.accept()

    def mouseMoveEvent(self, event):
        if self.is_drawing:
            self.extend_stroke(event.position())
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.end_stroke(event.position())
            event.accept()

    def tabletEvent(self, event):
        kind = event.type()
        if kind == event.Type.TabletPress:
            self.begin_stroke(event.position())
        elif kind == event.Type.TabletMove:
            self.extend_stroke(event.position())
        elif kind == event.Type.TabletRelease:
            self.end_stroke(event.position())
        event.accept()

    def undo(self):
        if self.strokes:
            self.strokes.pop()
            self.is_drawing = False
            self._changed()

    def clear(self):
        self.strokes.clear()
        self.is_drawing = False
        self._changed()

    def _paint_strokes(self, painter, width, height):
        painter.fillRect(0, 0, width, height, QColor("white"))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for pen_width, points in self.strokes:
            pen = QPen(
                QColor("#111111"),
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
        self._paint_strokes(painter, self.width(), self.height())
        if self.is_blank:
            painter.setPen(QColor("#99a3a8"))
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, "Write here with your mouse or pen"
            )
        painter.end()

    def snapshot(self) -> bytes:
        if self.is_blank:
            return b""
        image = QImage(self.size(), QImage.Format.Format_RGB32)
        painter = QPainter(image)
        self._paint_strokes(painter, image.width(), image.height())
        painter.end()
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, "PNG")
        return bytes(data)
