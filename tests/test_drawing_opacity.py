"""Floating background alpha never fades ink or changes recognition input."""

from dataclasses import replace

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QLabel

from lang_handler.settings import Settings
from lang_handler.storage import Store
from lang_handler.ui.drawing_page import DrawingPage
from lang_handler.ui.theme import STYLE
from lang_handler.ui.tool_settings import ToolSettings


@pytest.fixture
def page(qtbot):
    widget = DrawingPage(Settings(drawing_auto_send=False, drawing_on_top=False))
    qtbot.addWidget(widget)
    widget.setStyleSheet(STYLE)
    widget.resize(650, 500)
    widget.show()
    qtbot.wait(10)
    yield widget
    widget.shutdown()


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_floating_canvas_alpha_replaces_parent_and_updates_without_accumulating(page, qtbot, theme):
    page.update_settings(replace(page.settings, drawing_opacity=0.5, drawing_canvas_theme=theme))
    page.show_floating()
    qtbot.wait(10)
    window = page.floating
    assert window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert window.windowOpacity() == 1.0
    blank = page.canvas.mapTo(window, QPoint(30, page.canvas.height() - 20))
    for opacity in (0.5, 0.0, 0.7, 1.0):
        page.update_settings(replace(page.settings, drawing_opacity=opacity))
        for _ in range(3):
            window.repaint()
            image = window.grab().toImage()
            assert image.hasAlphaChannel()
            assert image.pixelColor(1, 1).alpha() == round(opacity * 255)
            # The canvas is painted over multiple scroll/viewport/frame widgets.
            # Half opacity must be 128, never 192 from two stacked fills.
            assert image.pixelColor(blank).alpha() == round(opacity * 255)


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_transparent_float_keeps_pen_readings_and_buttons_visible_and_clickable(page, qtbot, theme):
    page.update_settings(replace(page.settings, drawing_opacity=0.0, drawing_canvas_theme=theme))
    page.show_floating()
    qtbot.wait(10)
    page.canvas.pen_width = 12
    page.canvas.begin_stroke(QPointF(80, 100))
    page.canvas.end_stroke(QPointF(200, 100))
    page.result.set_items(["Readable handwriting"])
    qtbot.wait(10)
    image = page.floating.grab().toImage()
    stroke = page.canvas.mapTo(page.floating, QPoint(140, 100))
    assert image.pixelColor(stroke).alpha() == 255
    reading = page.result.rows[0].findChild(QLabel)
    origin = reading.mapTo(page.floating, QPoint())
    assert image.pixelColor(origin + QPoint(reading.width() - 2, reading.height() - 2)).alpha() == 0
    assert sum(
        image.pixelColor(origin + QPoint(x, y)).alpha() > 245
        for x in range(reading.width())
        for y in range(reading.height())
    ) > 50
    cluster = page.workspace.left_controls
    assert image.pixelColor(cluster.mapTo(page.floating, QPoint(1, cluster.height() // 2))).alpha() > 200
    qtbot.mouseClick(page.undo_button, Qt.MouseButton.LeftButton)
    assert page.canvas.is_blank
    qtbot.mouseClick(page.redo_button, Qt.MouseButton.LeftButton)
    assert not page.canvas.is_blank
    requested = QSignalSpy(page.requested)
    qtbot.mouseClick(page.send_button, Qt.MouseButton.LeftButton)
    assert requested.count() == 1


def test_opacity_does_not_change_docked_canvas_or_canonical_png_or_ink(page, qtbot):
    page.canvas.begin_stroke(QPointF(80, 100))
    page.canvas.end_stroke(QPointF(200, 100))
    revision = page.canvas.revision
    for floating in (False, True, False, True):
        if floating:
            page.show_floating()
        else:
            page.dock_workspace()
        qtbot.wait(10)
        png, ink = page.canvas.snapshot(), page.canvas.ink_snapshot()
        for opacity in (0.0, 0.5, 1.0):
            page.update_settings(replace(page.settings, drawing_opacity=opacity))
            assert page.canvas.revision == revision
            assert page.canvas.snapshot() == png
            assert page.canvas.ink_snapshot() == ink
            image = QImage.fromData(page.canvas.snapshot())
            assert image.pixelColor(0, 0).name() == "#ffffff"
            assert image.pixelColor(0, 0).alpha() == 255
            if not floating:
                assert page.canvas.background_opacity == 1.0
                assert page.canvas.grab().toImage().pixelColor(20, 20).alpha() == 255
        page.update_settings(replace(page.settings, drawing_opacity=0.5))
    page.dock_workspace()
    assert page.canvas.background_opacity == 1.0
    assert page.canvas.grab().toImage().pixelColor(20, 20).alpha() == 255


def test_drawing_opacity_has_scoped_preference_reset_and_survives_restart(qtbot, tmp_path):
    baseline = Settings(drawing_opacity=0.75)
    panel = ToolSettings("drawing", baseline)
    qtbot.addWidget(panel)
    assert panel.drawing_opacity.value() == 75
    panel.drawing_opacity.setValue(35)
    patch = panel.collect()
    assert patch["drawing_opacity"] == 0.35
    assert "overlay_opacity" not in patch
    store = Store(tmp_path)
    store.save_settings(replace(baseline, **patch))
    store.close()
    reopened = Store(tmp_path)
    assert reopened.load_settings().drawing_opacity == 0.35
    reopened.close()
    panel.reset_buttons["drawing_opacity"].click()
    assert panel.collect()["drawing_opacity"] == 1.0
    panel.drawing_opacity.setValue(0)
    assert panel.collect()["drawing_opacity"] == 0
    assert Settings.from_dict({}).drawing_opacity == 1.0
