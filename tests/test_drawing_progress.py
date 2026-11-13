"""Handwriting progress stays on its top action in docked and floating views."""

import pytest
from PySide6.QtCore import QPoint, QPointF
from PySide6.QtTest import QSignalSpy

from lang_handler.settings import Settings
from lang_handler.ui.drawing_page import DrawingPage


def add_stroke(canvas, offset=0):
    canvas.begin_stroke(QPointF(30 + offset, 30))
    canvas.end_stroke(QPointF(80 + offset, 70))


def test_progress_uses_recognize_button_and_keeps_latest_revision_submission(qtbot):
    page = DrawingPage(Settings(drawing_auto_send=False))
    qtbot.addWidget(page)
    page.resize(650, 580)
    page.show()
    add_stroke(page.canvas)
    page.set_busy(True)
    assert page.send_button.text() == "Recognizing…"
    assert page.send_button.accessibleName() == "Recognizing handwriting"
    assert not hasattr(page, "status")
    assert not hasattr(page.workspace, "status")
    assert page.send_button.mapTo(page.workspace, QPoint()).y() < page.canvas.mapTo(
        page.workspace, QPoint()
    ).y()
    add_stroke(page.canvas, 40)
    requested = QSignalSpy(page.requested)
    page.send_button.click()
    assert requested.count() == 1
    assert requested.at(0)[1] == page.canvas.revision
    page.set_busy(False)
    assert page.send_button.text() == "Recognize"
    assert page.send_button.accessibleName() == "Send canvas to transcribe"


def test_empty_result_is_inline_and_new_drawing_restores_placeholder(qtbot):
    page = DrawingPage(Settings(drawing_auto_send=False))
    qtbot.addWidget(page)
    add_stroke(page.canvas)
    page.set_result([], page.canvas.revision)
    assert page.result.empty.text() == "No readable handwriting found."
    assert not page.result.empty.isHidden()
    add_stroke(page.canvas, 40)
    assert page.result.empty.text() == "Recognized readings will appear here."
    page.set_result(["わ", "ね"], page.canvas.revision)
    assert page.result.empty.isHidden()


def test_floating_canvas_has_the_same_progress_action_and_no_footer(qtbot):
    page = DrawingPage(Settings(drawing_auto_send=False))
    qtbot.addWidget(page)
    add_stroke(page.canvas)
    page.show_floating()
    try:
        page.set_busy(True)
        assert page.floating.isAncestorOf(page.send_button)
        assert page.send_button.text() == "Recognizing…"
        frame = page.workspace.canvas_frame
        assert frame.isAncestorOf(page.send_button)
        assert frame.rect().contains(page.send_button.mapTo(frame, QPoint()))
        page.canvas.clear()
        assert not page.send_button.isEnabled()
        assert page.send_button.text() == "Recognize"
        page.set_busy(False)
    finally:
        page.shutdown()


@pytest.mark.parametrize("floating", [False, True])
def test_previous_readings_stay_usable_until_latest_drawing_has_new_candidates(qtbot, floating):
    page = DrawingPage(Settings(drawing_auto_send=False, drawing_on_top=False))
    qtbot.addWidget(page)
    page.show()
    if floating:
        page.show_floating()
    try:
        add_stroke(page.canvas)
        previous_revision = page.canvas.revision
        page.set_result(["とも", "友"], previous_revision)
        previous_rows = list(page.result.rows)
        qtbot.waitUntil(lambda: all(row.isVisible() for row in previous_rows))
        page.canvas.begin_stroke(QPointF(120, 30))
        page.canvas.extend_stroke(QPointF(140, 50))
        assert page.result.rows == previous_rows
        assert all(row.isVisible() for row in previous_rows)
        page.canvas.end_stroke(QPointF(160, 70))
        page.set_busy(True)
        page.set_result(["obsolete response"], previous_revision)
        assert page.result.items == ["とも", "友"]
        assert page.result.rows == previous_rows
        assert all(row.copy.isEnabled() and row.speak.isEnabled() for row in previous_rows)
        # An empty response or failed request must not erase the last useful guesses.
        page.set_result([], page.canvas.revision)
        page.set_busy(False)
        assert page.result.rows == previous_rows
        page.canvas.undo()
        page.canvas.redo()
        assert page.result.rows == previous_rows
        page.set_result(["ともだち"], page.canvas.revision)
        assert page.result.items == ["ともだち"]
        assert page.result.rows != previous_rows
        page.canvas.clear()
        assert page.result.items == []
        assert not page.result.empty.isHidden()
    finally:
        page.shutdown()
