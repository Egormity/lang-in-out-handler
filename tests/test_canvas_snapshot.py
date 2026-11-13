"""Recognition crops keep ink intact without changing the displayed drawing."""

from copy import deepcopy

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtGui import QImage
from PySide6.QtTest import QSignalSpy

from lang_handler.ui.drawing_canvas import DrawingCanvas


def canvas_widget(qtbot, width=1600, height=900):
    canvas = DrawingCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(width, height)
    return canvas


def draw(canvas, first, last, pen_width=4):
    canvas.pen_width = pen_width
    canvas.begin_stroke(QPointF(*first))
    canvas.end_stroke(QPointF(*last))


def ink_bounds(image):
    gray = image.convertToFormat(QImage.Format.Format_Grayscale8)
    data = bytes(gray.constBits())
    points = [
        (x, y) for y in range(gray.height()) for x in range(gray.width())
        if data[y * gray.bytesPerLine() + x] < 100
    ]
    assert points
    return (
        min(x for x, _ in points), min(y for _, y in points),
        max(x for x, _ in points), max(y for _, y in points),
    )


def test_small_ink_crops_blank_canvas_and_keeps_at_least_sixteen_pixels_padding(qtbot):
    canvas = canvas_widget(qtbot)
    assert canvas.snapshot() == b""
    draw(canvas, (100, 120), (200, 220))
    image = QImage.fromData(canvas.snapshot())
    assert 130 <= image.width() <= 145
    assert 130 <= image.height() <= 145
    left, top, right, bottom = ink_bounds(image)
    assert min(left, top, image.width() - right - 1, image.height() - bottom - 1) >= 16
    assert abs((right - left) - (bottom - top)) <= 1


@pytest.mark.parametrize("position", [(0, 0), (400, 0), (0, 300), (400, 300)])
def test_edge_dot_is_complete_and_surrounded_by_white_padding(qtbot, position):
    canvas = canvas_widget(qtbot, 400, 300)
    canvas.pen_width = 16
    canvas.begin_stroke(QPointF(*position))  # A one-point stroke exercises the dot renderer.
    image = QImage.fromData(canvas.snapshot())
    left, top, right, bottom = ink_bounds(image)
    assert 14 <= right - left <= 17
    assert 14 <= bottom - top <= 17
    assert min(left, top, image.width() - right - 1, image.height() - bottom - 1) >= 16


def test_crop_bounds_include_every_stroke_with_its_own_pen_radius(qtbot):
    canvas = canvas_widget(qtbot)
    draw(canvas, (100, 100), (130, 140), pen_width=2)
    draw(canvas, (300, 200), (340, 250), pen_width=16)
    image = QImage.fromData(canvas.snapshot())
    left, top, right, bottom = ink_bounds(image)
    assert right - left > 240
    assert bottom - top > 150
    assert min(left, top, image.width() - right - 1, image.height() - bottom - 1) >= 16


def test_large_crop_caps_longest_side_without_distorting_strokes(qtbot):
    canvas = canvas_widget(qtbot, 4000, 2000)
    draw(canvas, (100, 100), (3300, 900), pen_width=12)
    image = QImage.fromData(canvas.snapshot())
    assert image.width() == 1280
    assert 325 <= image.height() <= 340
    left, top, right, bottom = ink_bounds(image)
    assert abs((right - left) / (bottom - top) - 4) < 0.06


def test_snapshot_matches_current_canvas_coordinates_and_keeps_state_and_theme_independent(qtbot):
    canvas = canvas_widget(qtbot, 1000, 500)
    draw(canvas, (100, 100), (300, 200))
    canvas.resize(1500, 500)
    original = deepcopy((canvas.strokes, canvas._undo_stack, canvas._redo_stack))
    revision = canvas.revision
    changed = QSignalSpy(canvas.changed)
    light = canvas.snapshot()
    image = QImage.fromData(light)
    left, top, right, bottom = ink_bounds(image)
    assert abs((right - left) / (bottom - top) - 3) < 0.08
    canvas.set_theme("dark")
    assert canvas.snapshot() == light
    assert image.pixelColor(0, 0).name() == "#ffffff"
    assert (canvas.strokes, canvas._undo_stack, canvas._redo_stack) == original
    assert canvas.revision == revision
    assert changed.count() == 0
