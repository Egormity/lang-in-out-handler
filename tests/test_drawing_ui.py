"""Handwriting UI behavior: no network, audio, or private images."""

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
    return window, window.pages["drawing"]


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
