"""Floating captions keep native alpha, readable controls, and real capture state."""

from dataclasses import replace

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QSignalSpy

from lang_handler.settings import Settings
from lang_handler.ui.overlay import CaptionOverlay


def make_overlay(qtbot, **changes):
    overlay = CaptionOverlay(Settings(overlay_on_top=False, **changes))
    qtbot.addWidget(overlay)
    overlay.resize(460, 260)
    overlay.show()
    qtbot.wait(10)
    return overlay


def test_opacity_is_painted_alpha_through_nested_content_and_updates(qtbot):
    overlay = make_overlay(qtbot, overlay_opacity=0.5)
    assert overlay.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert overlay.windowOpacity() == 1.0
    image = overlay.grab().toImage()
    assert image.hasAlphaChannel()
    assert image.pixelColor(1, 1).alpha() == 128
    viewport = overlay.transcript.scroll.viewport()
    blank = viewport.mapTo(overlay, QPoint(viewport.width() - 16, viewport.height() - 12))
    assert image.pixelColor(blank).alpha() == 128
    for _ in range(3):
        overlay.repaint()
        assert overlay.grab().toImage().pixelColor(blank).alpha() == 128
    overlay.update_settings(replace(overlay.settings, overlay_opacity=0.9))
    qtbot.wait(10)
    assert overlay.grab().toImage().pixelColor(blank).alpha() == 230
    overlay.update_settings(replace(overlay.settings, overlay_opacity=1.0))
    qtbot.wait(10)
    assert overlay.grab().toImage().pixelColor(blank).alpha() == 255


def test_translucent_background_keeps_text_opaque_and_buttons_clickable(qtbot):
    overlay = make_overlay(qtbot, overlay_opacity=0.5)
    overlay.append_caption("Readable captions", "Readable translation")
    qtbot.wait(10)
    image = overlay.grab().toImage()
    viewport = overlay.transcript.text.viewport()
    origin = viewport.mapTo(overlay, QPoint())
    opaque_pixels = sum(
        image.pixelColor(origin.x() + x, origin.y() + y).alpha() > 245
        for x in range(viewport.width())
        for y in range(min(50, viewport.height()))
    )
    assert opaque_pixels > 40
    started = QSignalSpy(overlay.start_requested)
    qtbot.mouseClick(overlay.start_button, Qt.MouseButton.LeftButton)
    assert started.count() == 1


def test_start_stop_and_finishing_follow_controller_state(qtbot):
    overlay = make_overlay(qtbot)
    started = QSignalSpy(overlay.start_requested)
    stopped = QSignalSpy(overlay.stop_requested)
    assert overlay.capture_state == "idle"
    assert overlay.start_button.isVisible()
    assert overlay.stop_button.isHidden()
    assert not overlay.stop_button.isEnabled()
    overlay.stop_button.click()
    assert stopped.count() == 0
    overlay.start_button.click()
    assert started.count() == 1
    overlay.set_capture_state("recording")
    assert overlay.start_button.isHidden()
    assert not overlay.start_button.isEnabled()
    assert overlay.stop_button.isVisible() and overlay.stop_button.isEnabled()
    overlay.stop_button.click()
    assert stopped.count() == 1
    overlay.set_capture_state("finishing", pending=3)
    assert overlay.stop_button.text() == "Finishing…"
    assert not overlay.stop_button.isEnabled()
    assert "3" in overlay.stop_button.toolTip()
    overlay.stop_button.click()
    overlay.start_button.click()
    assert stopped.count() == 1 and started.count() == 1
    overlay.set_capture_state("idle")
    assert overlay.start_button.isVisible()
    assert overlay.stop_button.isHidden()


def test_language_headers_emit_scoped_patches_and_refresh_without_feedback(qtbot):
    overlay = make_overlay(qtbot)
    changed = QSignalSpy(overlay.options_changed)
    assert overlay.source_language.parentWidget() is overlay.transcript
    assert overlay.target.parentWidget() is overlay.translation
    assert overlay.transcript.heading.isHidden() and overlay.translation.heading.isHidden()
    assert not overlay.source_language.isEditable() and not overlay.target.isEditable()
    assert overlay.source_language.width() <= 160 and overlay.target.width() <= 160
    overlay.source_language.setCurrentText("Russian")
    overlay.target.setCurrentText("Japanese")
    assert changed.at(0) == [{"output_language": "ru"}]
    assert changed.at(1) == [{"target_language": "Japanese"}]
    overlay.update_settings(replace(overlay.settings, output_language="fr", target_language="Korean"))
    assert changed.count() == 2
    assert overlay.source_language.currentText() == "French"
    assert overlay.target.currentText() == "Korean"


def test_language_popup_remains_opaque_above_transparent_overlay(qtbot):
    overlay = make_overlay(qtbot, overlay_opacity=0.5)
    overlay.source_language.showPopup()
    qtbot.wait(10)
    popup = overlay.source_language.view().window()
    try:
        image = popup.grab().toImage()
        assert popup.width() <= 360
        assert image.pixelColor(image.width() - 20, 20).alpha() == 255
    finally:
        overlay.source_language.hidePopup()
