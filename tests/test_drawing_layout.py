"""Canvas and every candidate share one scroll document in both editor hosts."""

import wave
from copy import deepcopy

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtWidgets import QLabel, QScrollArea

from lang_handler.settings import Settings
from lang_handler.ui.drawing_page import DrawingPage
from lang_handler.ui.theme import STYLE


def editor(qtbot):
    page = DrawingPage(Settings(drawing_auto_send=False))
    qtbot.addWidget(page)
    page.setStyleSheet(STYLE)
    page.resize(650, 580)
    page.show()
    return page


def test_canvas_and_candidates_scroll_together_without_nested_result_scrollbar(qtbot):
    page = editor(qtbot)
    try:
        for floating in (False, True):
            if floating:
                page.show_floating()
            page.result.set_items([f"Candidate {index}" for index in range(12)])
            scroll = page.workspace.scroll
            assert page.workspace.findChildren(QScrollArea) == [scroll]
            assert scroll.widget().isAncestorOf(page.canvas)
            assert scroll.widget().isAncestorOf(page.result)
            qtbot.waitUntil(lambda area=scroll: area.verticalScrollBar().maximum() > 200)
            scroll.verticalScrollBar().setValue(0)
            before = page.canvas.mapTo(scroll.viewport(), QPoint()).y()
            scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
            assert page.canvas.mapTo(scroll.viewport(), QPoint()).y() < before
            final = page.result.rows[-1]
            bottom = final.mapTo(scroll.viewport(), final.rect().bottomRight()).y()
            assert bottom < scroll.viewport().height()
            assert not page.result.findChildren(QScrollArea)
    finally:
        page.shutdown()


def test_compact_floating_overlay_leaves_empty_canvas_and_corners_usable(qtbot):
    page = editor(qtbot)
    page.show_floating()
    try:
        page.floating.resize(440, 260)
        qtbot.waitUntil(lambda: page.canvas.height() == 200)
        assert page.floating.height() == 260
        assert page.result.height() <= 40
        assert page.workspace.toolbar.isHidden()
        assert page.scroll.verticalScrollBar().maximum() == 0
        assert not any(label.text() == "Draw" for label in page.floating.findChildren(QLabel))
        controls = (
            page.undo_button, page.redo_button, page.clear_button, page.send_button,
            page.floating.dock_button, page.floating.hide_button,
        )
        for control in controls:
            assert not page.canvas.isAncestorOf(control)
            frame = page.workspace.canvas_frame
            assert frame.isAncestorOf(control)
            assert frame.rect().contains(control.mapTo(frame, QPoint()))
            assert frame.rect().contains(
                control.mapTo(frame, control.rect().bottomRight())
            )
        left, right = page.workspace.left_controls, page.workspace.right_controls
        assert not left.geometry().intersects(right.geometry())
        qtbot.mousePress(page.canvas, Qt.MouseButton.LeftButton, pos=QPoint(160, 100))
        qtbot.mouseRelease(page.canvas, Qt.MouseButton.LeftButton, pos=QPoint(220, 140))
        assert len(page.canvas.strokes) == 1
        page.undo_button.click()
        assert page.canvas.is_blank
        page.redo_button.click()
        assert len(page.canvas.strokes) == 1
    finally:
        page.shutdown()


def test_repeated_float_and_dock_preserve_pen_state_and_do_not_duplicate_controls(qtbot):
    page = editor(qtbot)
    page.canvas.begin_stroke(QPointF(100, 100))
    page.canvas.end_stroke(QPointF(200, 160))
    original, revision = deepcopy(page.canvas.strokes), page.canvas.revision
    times = tuple(tuple(point[2] for point in stroke) for stroke in page.canvas.ink_snapshot().strokes)
    try:
        for _ in range(3):
            page.show_floating()
            assert page.workspace.left_controls.layout().count() == 3
            assert page.workspace.right_controls.layout().count() == 3
            page.floating.dock_button.click()
            assert not page.is_floating
            assert page.workspace.tools.count() == 3  # left group, stretch, right group
            assert page.workspace.left_controls.layout().count() == 3
            assert page.workspace.right_controls.layout().count() == 1
            assert not page.workspace.toolbar.isHidden()
            assert page.canvas.strokes == original
            assert page.canvas.revision == revision
            assert tuple(tuple(point[2] for point in stroke)
                         for stroke in page.canvas.ink_snapshot().strokes) == times
    finally:
        page.shutdown()


def test_long_candidate_and_expanded_audio_grow_the_outer_document(qtbot, tmp_path):
    page = editor(qtbot)
    page.show_floating()
    page.floating.resize(440, 300)
    try:
        text = ("This is a long recognition candidate that must wrap and remain readable "
                "when its generated audio player appears beside the copy button.")
        page.result.set_items([text, "Second candidate"])
        row = page.result.rows[0]
        qtbot.waitUntil(lambda: row.width() == page.scroll.viewport().width())
        assert row.height() > 70
        before = row.height()
        path = tmp_path / "silent.wav"
        with wave.open(str(path), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(16000)
            audio.writeframes(b"\0\0" * 1600)
        row.audio.set_audio(path, autoplay=False)
        qtbot.waitUntil(lambda: row.height() > before + 30)
        assert page.result.height() > row.height()
        assert row.audio.mapTo(row, row.audio.rect().bottomRight()).x() < row.width()
        scroll = page.workspace.scroll
        qtbot.waitUntil(lambda: scroll.verticalScrollBar().maximum() > 200)
        scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
        final = page.result.rows[-1]
        assert final.mapTo(scroll.viewport(), final.rect().bottomRight()).y() < scroll.height()
    finally:
        page.shutdown()


def test_floating_pen_controls_and_margin_never_create_ink(qtbot):
    from test_tablet import pen_device, tablet

    page = editor(qtbot)
    page.show_floating()
    try:
        device = pen_device()
        page.send_button.setEnabled(True)
        pressed = tablet(
            page.send_button, device, QEvent.Type.TabletPress, pressure=1,
            button=Qt.MouseButton.LeftButton, buttons=Qt.MouseButton.LeftButton,
            point=(10, 10),
        )
        tablet(
            page.send_button, device, QEvent.Type.TabletRelease,
            button=Qt.MouseButton.LeftButton, point=(10, 10),
        )
        assert not pressed.isAccepted()  # Qt may synthesize the standard button click.
        assert not page.canvas.is_drawing
        assert page.canvas.is_blank
        qtbot.mouseClick(page.workspace.left_controls, Qt.MouseButton.LeftButton, pos=QPoint(1, 1))
        assert page.canvas.is_blank
        tablet(
            page.canvas, device, QEvent.Type.TabletPress, pressure=1,
            button=Qt.MouseButton.LeftButton, buttons=Qt.MouseButton.LeftButton,
            point=(180, 130),
        )
        tablet(
            page.canvas, device, QEvent.Type.TabletRelease,
            button=Qt.MouseButton.LeftButton, point=(230, 170),
        )
        assert not page.canvas.is_drawing
        assert len(page.canvas.strokes) == 1
    finally:
        page.shutdown()
