"""Drawing history and shortcuts survive reparenting without stealing editor undo."""

from copy import deepcopy

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QSignalSpy

from lang_handler.settings import Settings
from lang_handler.ui.drawing_canvas import DrawingCanvas
from lang_handler.ui.main_window import MainWindow


def draw(canvas, offset=0, width=4):
    canvas.pen_width = width
    canvas.begin_stroke(QPointF(20 + offset, 25))
    canvas.extend_stroke(QPointF(70 + offset, 55))
    canvas.end_stroke(QPointF(110 + offset, 80))


def canvas_widget(qtbot):
    canvas = DrawingCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(500, 300)
    return canvas


def drawing_window(qtbot, **options):
    settings = Settings(drawing_auto_send=False, drawing_on_top=False, **options)
    window = MainWindow(settings, True)
    qtbot.addWidget(window)
    page = window.pages["drawing"]
    qtbot.addWidget(page.floating)
    window.show_page("drawing")
    window.show()
    window.activateWindow()
    page.canvas.setFocus()
    qtbot.waitUntil(page.canvas.hasFocus)
    return window, page


def undo(qtbot, widget):
    qtbot.keyClick(widget, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)


def redo(qtbot, widget):
    qtbot.keyClick(
        widget, Qt.Key.Key_Z,
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
    )


def test_undo_redo_roundtrip_preserves_stroke_geometry_width_and_png(qtbot):
    canvas = canvas_widget(qtbot)
    draw(canvas, width=3)
    first = canvas.snapshot()
    draw(canvas, offset=40, width=9)
    complete, strokes = canvas.snapshot(), deepcopy(canvas.strokes)
    previous_revision = canvas.revision
    for operation, expected in (
        (canvas.undo, first), (canvas.undo, b""),
        (canvas.redo, first), (canvas.redo, complete),
    ):
        operation()
        assert canvas.snapshot() == expected
        assert canvas.revision > previous_revision
        previous_revision = canvas.revision
        assert not canvas.is_drawing
    assert canvas.strokes == strokes
    assert canvas.can_undo
    assert not canvas.can_redo


def test_clear_is_one_undoable_action_and_new_drawing_discards_redo(qtbot):
    canvas = canvas_widget(qtbot)
    draw(canvas)
    draw(canvas, offset=30)
    before_clear = canvas.snapshot()
    canvas.clear()
    assert canvas.is_blank and canvas.can_undo
    canvas.undo()
    assert canvas.snapshot() == before_clear
    canvas.redo()
    assert canvas.is_blank
    canvas.undo()
    canvas.undo()
    assert canvas.can_redo
    draw(canvas, offset=80, width=7)
    branched = canvas.snapshot()
    assert not canvas.can_redo
    revision = canvas.revision
    canvas.redo()
    assert canvas.snapshot() == branched
    assert canvas.revision == revision


def test_empty_operations_do_not_change_revision_or_discard_redo(qtbot):
    canvas = canvas_widget(qtbot)
    changed = QSignalSpy(canvas.changed)
    canvas.undo()
    canvas.redo()
    canvas.clear()
    assert canvas.revision == 0
    assert changed.count() == 0
    draw(canvas)
    canvas.undo()
    assert canvas.is_blank and canvas.can_redo
    revision = canvas.revision
    canvas.clear()
    canvas.undo()
    assert canvas.revision == revision
    assert canvas.can_redo
    canvas.redo()
    assert not canvas.is_blank


def test_shortcuts_follow_canvas_between_main_and_floating_windows(qtbot):
    window, page = drawing_window(qtbot)
    draw(page.canvas)
    draw(page.canvas, offset=30)
    assert not page.redo_button.isEnabled()
    undo(qtbot, page.canvas)
    assert len(page.canvas.strokes) == 1
    assert page.redo_button.isEnabled()
    try:
        page.show_floating()
        page.floating.activateWindow()
        page.canvas.setFocus()
        qtbot.waitUntil(page.canvas.hasFocus)
        redo(qtbot, page.canvas)
        assert len(page.canvas.strokes) == 2
        page.undo_button.setFocus()
        undo(qtbot, page.undo_button)
        assert len(page.canvas.strokes) == 1
        page.dock_workspace()
        window.activateWindow()
        page.canvas.setFocus()
        qtbot.waitUntil(page.canvas.hasFocus)
        redo(qtbot, page.canvas)
        assert len(page.canvas.strokes) == 2
        page.clear_button.click()
        assert page.canvas.is_blank
        assert page.undo_button.isEnabled()
        undo(qtbot, page.canvas)
        assert len(page.canvas.strokes) == 2
    finally:
        page.shutdown()


def test_drawing_shortcuts_leave_settings_and_translation_text_undo_alone(qtbot):
    window, page = drawing_window(qtbot)
    draw(page.canvas)
    expected = deepcopy(page.canvas.strokes)
    try:
        window.show_tool_settings("drawing")
        editor = page.tool_settings.instructions["drawing_instructions"]
        editor.setPlainText("Original")
        editor.moveCursor(QTextCursor.MoveOperation.End)
        editor.insertPlainText(" changed")
        editor.setFocus()
        qtbot.waitUntil(editor.hasFocus)
        undo(qtbot, editor)
        assert editor.toPlainText() == "Original"
        redo(qtbot, editor)
        assert editor.toPlainText() == "Original changed"
        assert page.canvas.strokes == expected
        window.show_page("translate")
        window.activateWindow()
        editor = window.pages["translate"].source.text
        editor.setPlainText("Text")
        editor.moveCursor(QTextCursor.MoveOperation.End)
        editor.insertPlainText(" edit")
        editor.setFocus()
        qtbot.waitUntil(editor.hasFocus)
        undo(qtbot, editor)
        assert editor.toPlainText() == "Text"
        assert page.canvas.strokes == expected
    finally:
        window.show_page("drawing")
        page.shutdown()


def test_redo_invalidates_old_recognition_and_debounces_latest_snapshot(qtbot):
    from dataclasses import replace

    _, page = drawing_window(qtbot, drawing_provider="openai", drawing_debounce_ms=200)
    requested = QSignalSpy(page.requested)
    draw(page.canvas)
    old_revision = page.canvas.revision
    original = page.canvas.snapshot()
    page.set_result(["old reading"], old_revision)
    page.canvas.undo()
    page.update_settings(replace(page.settings, drawing_auto_send=True))
    page.canvas.redo()
    assert page.canvas.snapshot() == original
    assert page.canvas.revision > old_revision
    assert page.result.items == []
    page.set_result(["stale reading"], old_revision)
    assert page.result.items == []
    assert page.timer.isActive()
    qtbot.waitUntil(lambda: requested.count() == 1, timeout=700)
    assert requested.at(0) == [original, page.canvas.revision]
    qtbot.wait(230)
    assert requested.count() == 1
    page.shutdown()


def test_undo_finishes_active_input_and_redo_restores_its_partial_stroke(qtbot):
    canvas = canvas_widget(qtbot)
    canvas.begin_stroke(QPointF(20, 30))
    canvas.extend_stroke(QPointF(60, 50))
    partial = deepcopy(canvas.strokes)
    canvas.undo()
    assert canvas.is_blank
    assert not canvas.is_drawing
    canvas.end_stroke(QPointF(100, 80))
    canvas.redo()
    assert canvas.strokes == partial
    assert not canvas.is_drawing
