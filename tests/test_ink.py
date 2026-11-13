"""Stroke recognizers receive immutable pixel paths with original pen timing."""

from dataclasses import FrozenInstanceError, replace

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtTest import QSignalSpy

from lang_handler.ink import InkSnapshot
from lang_handler.settings import Settings
from lang_handler.ui.drawing_canvas import DrawingCanvas
from lang_handler.ui.drawing_page import DrawingPage


def two_strokes(canvas, monkeypatch):
    times = iter([1_000_000_000, 1_005_000_000, 1_008_000_000,
                  1_020_000_000, 1_025_000_000])
    monkeypatch.setattr("lang_handler.ui.drawing_canvas.monotonic_ns", lambda: next(times))
    canvas.begin_stroke(QPointF(50, 30))
    canvas.extend_stroke(QPointF(75, 45))
    canvas.end_stroke(QPointF(100, 60))
    canvas.begin_stroke(QPointF(150, 90))
    canvas.end_stroke(QPointF(200, 120))


def test_canvas_exports_pixel_coordinates_original_timing_and_immutable_copy(qtbot, monkeypatch):
    canvas = DrawingCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(500, 300)
    two_strokes(canvas, monkeypatch)
    snapshot = canvas.ink_snapshot()
    assert snapshot.width == 500
    assert snapshot.height == 300
    assert snapshot.strokes == (
        ((50.0, 30.0, 0.0), (75.0, 45.0, 5.0), (100.0, 60.0, 8.0)),
        ((150.0, 90.0, 20.0), (200.0, 120.0, 25.0)),
    )
    with pytest.raises(FrozenInstanceError):
        snapshot.width = 100
    with pytest.raises(TypeError):
        snapshot.strokes[0][0][0] = 999
    canvas.clear()
    assert len(snapshot.strokes) == 2
    assert not canvas.ink_snapshot()


def test_undo_redo_and_clear_restore_exact_original_stroke_timing(qtbot, monkeypatch):
    canvas = DrawingCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(500, 300)
    two_strokes(canvas, monkeypatch)
    complete = canvas.ink_snapshot()
    canvas.undo()
    assert canvas.ink_snapshot().strokes == complete.strokes[:1]
    canvas.redo()
    assert canvas.ink_snapshot() == complete
    canvas.clear()
    assert not canvas.ink_snapshot()
    canvas.undo()
    assert canvas.ink_snapshot() == complete
    canvas.redo()
    assert not canvas.ink_snapshot()
    canvas.undo()
    canvas.resize(1000, 600)
    resized = canvas.ink_snapshot()
    assert resized.strokes[0][1] == (150.0, 90.0, 5.0)
    assert resized.strokes[1][-1] == (400.0, 240.0, 25.0)


def test_snapshot_does_not_hold_caller_owned_lists():
    points = [[[1, 2, 0], [3, 4, 5]]]
    snapshot = InkSnapshot(100, 200, points)
    points[0][0][0] = 999
    points.append([[5, 6, 7]])
    assert snapshot.strokes == (((1.0, 2.0, 0.0), (3.0, 4.0, 5.0)),)


def test_drawing_page_switches_png_and_strokes_and_cancels_old_provider(qtbot):
    page = DrawingPage(Settings(drawing_provider="openai", drawing_auto_send=False))
    qtbot.addWidget(page)
    requested, cancelled = QSignalSpy(page.requested), QSignalSpy(page.cancel_requested)
    page.canvas.begin_stroke(QPointF(20, 30))
    page.canvas.end_stroke(QPointF(60, 70))
    page.send()
    assert requested.at(0)[0].startswith(b"\x89PNG")
    ink = page.canvas.ink_snapshot()
    page.update_settings(replace(page.settings, drawing_provider="google"))
    assert cancelled.count() == 1
    page.send()
    assert requested.at(1)[0] == ink
    assert isinstance(requested.at(1)[0], InkSnapshot)
    assert requested.at(1)[1] == page.canvas.revision
    page.shutdown()


def test_google_requires_explicit_language_and_reschedules_after_selection(qtbot):
    page = DrawingPage(Settings(
        drawing_provider="google", drawing_language="", drawing_auto_send=True,
        drawing_debounce_ms=200,
    ))
    qtbot.addWidget(page)
    requested = QSignalSpy(page.requested)
    page.canvas.begin_stroke(QPointF(20, 30))
    page.canvas.end_stroke(QPointF(60, 70))
    page.send()
    assert requested.count() == 0
    assert not page.timer.isActive()
    assert not page.send_button.isEnabled()
    assert "Choose a handwriting language" in page.result.empty.text()
    assert page.language.currentData() == ""
    assert not page.language.model().item(page.language.findData("")).isEnabled()
    page.update_settings(replace(page.settings, drawing_language="ja"))
    assert page.send_button.isEnabled()
    assert page.timer.isActive()
    qtbot.waitUntil(lambda: requested.count() == 1, timeout=1000)
    assert isinstance(requested.at(0)[0], InkSnapshot)
    page.shutdown()
