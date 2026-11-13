"""Handwriting UI behavior: no network, audio, or private images."""

from copy import deepcopy
from dataclasses import replace

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QCheckBox, QComboBox, QPlainTextEdit, QSpinBox

from lang_handler.settings import Settings
from lang_handler.ui.main_window import MainWindow


def drawing_window(qtbot, **settings):
    window = MainWindow(Settings(**settings), True)
    qtbot.addWidget(window)
    window.show_page("drawing")
    window.show()
    page = window.pages["drawing"]
    qtbot.addWidget(page.floating)
    return window, page


def stroke(qtbot, canvas, offset=0):
    qtbot.mousePress(canvas, Qt.MouseButton.LeftButton, pos=QPoint(30 + offset, 30))
    qtbot.mouseMove(canvas, QPoint(70 + offset, 50))
    qtbot.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=QPoint(100 + offset, 70))


def test_canvas_mouse_stroke_exports_png_and_manual_works_with_auto_off(qtbot):
    window, page = drawing_window(qtbot, drawing_provider="openai", drawing_auto_send=False)
    requests = QSignalSpy(window.drawing_requested)
    assert not page.send_button.isEnabled()
    stroke(qtbot, page.canvas)
    assert not page.canvas.is_blank
    assert not page.timer.isActive()
    page.send_button.click()
    assert requests.count() == 1
    image_bytes, revision = requests.at(0)
    assert image_bytes.startswith(b"\x89PNG")
    assert revision == window.drawing_revision()
    image = QImage.fromData(image_bytes)
    assert not image.isNull()
    assert image.pixelColor(0, 0).name() == "#ffffff"
    assert page.send_button.isEnabled()


def test_auto_debounce_only_sends_latest_drawing(qtbot):
    window, page = drawing_window(qtbot, drawing_auto_send=True, drawing_debounce_ms=200)
    requests = QSignalSpy(window.drawing_requested)
    stroke(qtbot, page.canvas)
    qtbot.wait(100)
    stroke(qtbot, page.canvas, 35)
    qtbot.wait(100)
    assert requests.count() == 0
    qtbot.waitUntil(lambda: requests.count() == 1, timeout=500)
    assert requests.at(0)[1] == window.drawing_revision()
    qtbot.wait(230)
    assert requests.count() == 1


def test_clear_cancels_pending_auto_and_undo_removes_one_stroke(qtbot):
    window, page = drawing_window(qtbot, drawing_auto_send=True, drawing_debounce_ms=200)
    requests = QSignalSpy(window.drawing_requested)
    cancelled = QSignalSpy(window.drawing_cancel_requested)
    stroke(qtbot, page.canvas)
    stroke(qtbot, page.canvas, 30)
    assert len(page.canvas.strokes) == 2
    page.undo_button.click()
    assert len(page.canvas.strokes) == 1
    page.clear_button.click()
    assert page.canvas.is_blank
    assert window.drawing_snapshot() == b""
    assert not page.send_button.isEnabled()
    assert not page.timer.isActive()
    qtbot.wait(250)
    assert requests.count() == 0
    assert cancelled.count() == 1


def test_stale_result_is_ignored_and_auto_off_cancels(qtbot):
    window, page = drawing_window(qtbot, drawing_auto_send=True, drawing_debounce_ms=200)
    cancelled = QSignalSpy(window.drawing_cancel_requested)
    stroke(qtbot, page.canvas)
    old_revision = window.drawing_revision()
    stroke(qtbot, page.canvas, 20)
    window.set_drawing_result(["stale"], old_revision)
    assert page.result.items == []
    window.set_drawing_result(["カフェ", "カフエ"], window.drawing_revision())
    assert page.result.items == ["カフェ", "カフエ"]
    page.update_settings(replace(page.settings, drawing_auto_send=False))
    assert cancelled.count() == 1
    assert not page.timer.isActive()
    window.set_drawing_busy(True)
    assert page.send_button.isEnabled()


def test_handwriting_preferences_disable_delay_but_keep_manual(qtbot):
    window, page = drawing_window(qtbot)
    preferences = page.tool_settings
    preferences.drawing_auto_send.setChecked(False)
    preferences.drawing_delay.setValue(2.3)
    assert not preferences.drawing_delay.isEnabled()
    selected = preferences.collect()
    assert selected["drawing_debounce_ms"] == 2300
    window._save_preferences(selected)
    assert not page.settings.drawing_auto_send
    stroke(qtbot, page.canvas)
    assert page.send_button.isEnabled()
    assert not page.timer.isActive()


def test_drawing_controls_never_overlap_canvas_at_small_window_sizes(qtbot):
    window, page = drawing_window(qtbot, drawing_auto_send=False)
    for width, height in [(1120, 780), (850, 620), (1120, 1000)]:
        window.resize(width, height)
        qtbot.wait(30)
        canvas_bottom = page.canvas.geometry().bottom()
        canvas_top = page.canvas.mapTo(page.workspace, QPoint()).y()
        for control in (page.undo_button, page.send_button):
            bottom = control.mapTo(page.workspace, QPoint(0, control.height() - 1)).y()
            assert bottom < canvas_top
        assert page.result.geometry().top() > canvas_bottom
        page.scroll.ensureWidgetVisible(page.result)
        qtbot.wait(10)
        assert page.result.isVisible()


def test_float_and_dock_keep_one_canvas_revision_and_recognized_text(qtbot):
    window, page = drawing_window(qtbot, drawing_auto_send=False)
    stroke(qtbot, page.canvas)
    original_canvas = page.canvas
    revision = window.drawing_revision()
    strokes = deepcopy(page.canvas.strokes)
    window.set_drawing_result(["日本語"], revision)
    changed = QSignalSpy(page.canvas.changed)
    page.float_button.click()
    qtbot.waitUntil(page.floating.isVisible)
    assert page.is_floating
    assert page.floating.workspace is page.workspace
    assert page.floating.scroll is page.workspace.scroll
    assert page.floating.scroll.widget() is page.workspace.body
    assert page.canvas is original_canvas
    assert page.canvas.revision == revision
    assert page.canvas.strokes == strokes
    assert page.result.items == ["日本語"]
    assert page.floating.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    assert not page.floating.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    page.floating.dock_button.click()
    assert not page.floating.isVisible()
    assert not page.is_floating
    assert page.floating.workspace is None
    assert page.floating.scroll is None
    assert page.canvas is original_canvas
    assert page.canvas.revision == revision
    assert changed.count() == 0
    assert page.result.items == ["日本語"]


def test_floating_pin_and_close_preserve_canvas(qtbot):
    _, page = drawing_window(qtbot, drawing_auto_send=False)
    stroke(qtbot, page.canvas)
    revision = page.canvas.revision
    page.show_floating()
    page.update_settings(replace(page.settings, drawing_on_top=False))
    assert not page.floating.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    assert page.floating.isVisible()
    page.update_settings(replace(page.settings, drawing_on_top=True))
    assert page.floating.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    page.floating.close()
    assert not page.is_floating
    assert page.workspace.isVisible()
    assert not page.canvas.is_blank
    assert page.canvas.revision == revision


def test_floating_hide_restore_and_manual_recognition_share_state(qtbot):
    window, page = drawing_window(qtbot, drawing_auto_send=False)
    requests = QSignalSpy(window.drawing_requested)
    page.show_floating()
    stroke(qtbot, page.canvas)
    revision = page.canvas.revision
    page.floating.hide_button.click()
    assert page.is_floating
    assert not page.floating.isVisible()
    page.show_floating()
    assert page.canvas.revision == revision
    page.send_button.click()
    assert requests.count() == 1
    assert requests.at(0)[1] == revision
    assert page.floating.isVisible()


def test_floating_editor_keeps_canvas_large_and_contains_no_preferences(qtbot):
    _, page = drawing_window(qtbot, drawing_auto_send=False)
    page.show_floating()
    qtbot.wait(20)
    assert page.floating.width() <= 700
    assert page.floating.height() <= 600
    assert page.canvas.height() >= 240
    assert page.floating.scroll.verticalScrollBar().maximum() == 0
    for width, height in ((640, 660), (480, 480), (760, 820)):
        page.floating.resize(width, height)
        qtbot.wait(20)
        assert page.canvas.height() >= 200
        assert page.canvas.height() > page.result.height()
        for control in (page.undo_button, page.send_button):
            frame = page.workspace.canvas_frame
            assert frame.isAncestorOf(control)
            assert not page.canvas.isAncestorOf(control)
            assert frame.rect().contains(control.mapTo(frame, QPoint()))
            assert frame.rect().contains(
                control.mapTo(frame, control.rect().bottomRight())
            )
        assert page.result.geometry().top() > page.workspace.canvas_frame.geometry().bottom()
    for kind in (QCheckBox, QComboBox, QSpinBox, QPlainTextEdit):
        assert page.floating.findChildren(kind) == []
    page.dock_workspace()


def test_shutdown_hides_floating_host_and_stops_pending_recognition(qtbot):
    window, page = drawing_window(qtbot, drawing_auto_send=True, drawing_debounce_ms=200)
    requests = QSignalSpy(window.drawing_requested)
    page.show_floating()
    stroke(qtbot, page.canvas)
    assert page.timer.isActive()
    page.shutdown()
    assert not page.floating.isVisible()
    assert not page.is_floating
    assert not page.timer.isActive()
    qtbot.wait(250)
    assert requests.count() == 0


def test_floating_default_size_keeps_result_visible_at_high_dpi():
    import os
    import subprocess
    import sys

    script = """
from PySide6.QtWidgets import QApplication
from lang_handler.ui.drawing_page import DrawingPage
from lang_handler.settings import Settings
app = QApplication([])
page = DrawingPage(Settings(drawing_auto_send=False))
page.show_floating()
app.processEvents()
assert page.canvas.height() >= 240
assert page.result.isVisible()
assert page.floating.scroll.verticalScrollBar().maximum() == 0
page.shutdown()
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "QT_SCALE_FACTOR": "2"},
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr


def test_each_candidate_can_be_copied_and_spoken_without_combining_alternatives(qtbot, qapp):
    window, page = drawing_window(qtbot, drawing_auto_send=False)
    stroke(qtbot, page.canvas)
    window.set_drawing_result(["カフェ", "カフエ"], page.canvas.revision)
    speech = QSignalSpy(page.speech_requested)
    page.result.rows[1].speak.click()
    assert speech.count() == 1
    assert speech.at(0) == ["カフエ"]
    page.result.rows[0].copy.click()
    assert qapp.clipboard().text() == "カフェ"
    page.show_floating()
    page.set_speech_active(True)
    stopped = QSignalSpy(page.speech_stop_requested)
    assert page.result.stop.isVisible()
    page.result.stop.click()
    assert stopped.count() == 1
    page.set_speech_active(False)
    assert page.result.stop.isHidden()


def test_preferences_change_pen_width_and_automatic_recognition(qtbot):
    _, page = drawing_window(qtbot, drawing_auto_send=False)
    stroke(qtbot, page.canvas)
    page.update_settings(replace(page.settings, drawing_auto_send=True, drawing_pen_width=8))
    assert page.canvas.pen_width == 8
    assert page.timer.isActive()
    page.update_settings(replace(page.settings, drawing_auto_send=False))
    assert not page.timer.isActive()
