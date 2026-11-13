"""Handwriting UI behavior: no network, audio, or private images."""

from copy import deepcopy

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QSignalSpy

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
    window, page = drawing_window(qtbot, drawing_auto_send=False)
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
    window.set_drawing_result("stale", old_revision)
    assert page.result.text.toPlainText() == ""
    window.set_drawing_result("カフェ", window.drawing_revision())
    assert page.result.text.toPlainText() == "カフェ"
    page.auto_send.setChecked(False)
    assert cancelled.count() == 1
    assert not page.timer.isActive()
    window.set_drawing_busy(True)
    assert page.send_button.isEnabled()


def test_handwriting_preferences_disable_delay_but_keep_manual(qtbot):
    window, page = drawing_window(qtbot)
    preferences = window.pages["preferences"]
    preferences.drawing_auto_send.setChecked(False)
    preferences.drawing_delay.setValue(2.3)
    assert not preferences.drawing_delay.isEnabled()
    selected = preferences.collect()
    assert selected.drawing_debounce_ms == 2300
    window._save_preferences(selected)
    assert not page.auto_send.isChecked()
    stroke(qtbot, page.canvas)
    assert page.send_button.isEnabled()
    assert not page.timer.isActive()


def test_drawing_controls_never_overlap_canvas_at_small_window_sizes(qtbot):
    window, page = drawing_window(qtbot, drawing_auto_send=False)
    for width, height in [(1120, 780), (850, 620), (1120, 1000)]:
        window.resize(width, height)
        qtbot.wait(30)
        canvas_bottom = page.canvas.geometry().bottom()
        assert canvas_bottom < page.auto_send.geometry().top()
        assert canvas_bottom < page.send_button.geometry().top()
        assert page.result.geometry().top() > page.send_button.geometry().bottom()
        page.scroll.ensureWidgetVisible(page.result)
        qtbot.wait(10)
        assert page.result.isVisible()


def test_float_and_dock_keep_one_canvas_revision_and_recognized_text(qtbot):
    window, page = drawing_window(qtbot, drawing_auto_send=False)
    stroke(qtbot, page.canvas)
    original_canvas = page.canvas
    revision = window.drawing_revision()
    strokes = deepcopy(page.canvas.strokes)
    window.set_drawing_result("日本語", revision)
    changed = QSignalSpy(page.canvas.changed)
    page.float_button.click()
    qtbot.waitUntil(page.floating.isVisible)
    assert page.is_floating
    assert page.floating.scroll.widget() is page.workspace
    assert page.canvas is original_canvas
    assert page.canvas.revision == revision
    assert page.canvas.strokes == strokes
    assert page.result.text.toPlainText() == "日本語"
    assert page.floating.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    assert not page.floating.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    page.floating.dock_button.click()
    assert not page.floating.isVisible()
    assert not page.is_floating
    assert page.floating.scroll.widget() is None
    assert page.canvas is original_canvas
    assert page.canvas.revision == revision
    assert changed.count() == 0
    assert page.result.text.toPlainText() == "日本語"


def test_floating_pin_and_close_preserve_canvas(qtbot):
    _, page = drawing_window(qtbot, drawing_auto_send=False)
    stroke(qtbot, page.canvas)
    revision = page.canvas.revision
    page.show_floating()
    page.floating.pin.setChecked(False)
    assert not page.floating.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    assert page.floating.isVisible()
    page.floating.pin.setChecked(True)
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


def test_floating_editor_keeps_canvas_large_and_instructions_collapsed(qtbot):
    _, page = drawing_window(qtbot, drawing_auto_send=False)
    assert not page.instructions.isVisible()
    page.show_floating()
    qtbot.wait(20)
    assert page.floating.size().width() == 750
    assert page.floating.size().height() == 600
    assert page.floating.scroll.verticalScrollBar().maximum() == 0
    for width, height in ((640, 660), (480, 480), (760, 820)):
        page.floating.resize(width, height)
        qtbot.wait(20)
        assert page.canvas.height() >= 240
        assert page.canvas.geometry().bottom() < page.auto_send.geometry().top()
        assert page.canvas.geometry().bottom() < page.send_button.geometry().top()
        assert page.result.geometry().top() > page.send_button.geometry().bottom()
    page.advanced_toggle.setChecked(True)
    assert page.instructions.isVisible()
    page.dock_workspace()
    assert page.instructions.isVisible()


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
