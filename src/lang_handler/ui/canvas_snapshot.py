"""Small, padded recognition images rendered directly from the visible stroke geometry."""

import math

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRect
from PySide6.QtGui import QColor, QImage, QPainter

PADDING = 16
ANTIALIAS_MARGIN = 2
MAX_SIDE = 1280


def _stroke_bounds(strokes, width, height):
    left, top = math.inf, math.inf
    right, bottom = -math.inf, -math.inf
    for pen_width, points in strokes:
        radius = max(0, pen_width) / 2 + ANTIALIAS_MARGIN
        for x, y in points:
            px, py = x * width, y * height
            left, top = min(left, px - radius), min(top, py - radius)
            right, bottom = max(right, px + radius), max(bottom, py + radius)
    if not math.isfinite(left):
        return None
    x, y = math.floor(left) - PADDING, math.floor(top) - PADDING
    # Do not clamp to the widget: edge dots need their full cap and white border.
    return QRect(x, y, math.ceil(right) + PADDING - x, math.ceil(bottom) + PADDING - y)


def recognition_snapshot(canvas) -> bytes:
    """Crop blank space without changing stroke coordinates, aspect, or canvas state."""
    width, height = canvas.width(), canvas.height()
    bounds = _stroke_bounds(canvas.strokes, width, height)
    if bounds is None:
        return b""
    scale = min(1.0, MAX_SIDE / max(bounds.width(), bounds.height()))
    image = QImage(
        max(1, round(bounds.width() * scale)),
        max(1, round(bounds.height() * scale)),
        QImage.Format.Format_RGB32,
    )
    image.fill(QColor("white"))
    painter = QPainter(image)
    painter.scale(scale, scale)
    painter.translate(-bounds.x(), -bounds.y())
    canvas._paint_strokes(painter, width, height)
    painter.end()
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(data)
