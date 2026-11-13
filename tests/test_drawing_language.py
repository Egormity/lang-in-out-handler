"""The main handwriting language control changes recognition without losing ink."""

from copy import deepcopy
from dataclasses import replace

from PySide6.QtCore import QPointF
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QComboBox

from lang_handler.settings import Settings
from lang_handler.ui.drawing_page import DrawingPage
from lang_handler.ui.main_window import MainWindow


def test_drawing_header_language_preserves_ink_and_cancels_old_recognition(qtbot):
    page = DrawingPage(Settings(drawing_auto_send=False))
    qtbot.addWidget(page)
    page.options_changed.connect(lambda patch: page.update_settings(replace(page.settings, **patch)))
    page.canvas.begin_stroke(QPointF(40, 30))
    page.canvas.end_stroke(QPointF(80, 60))
    strokes, revision = deepcopy(page.canvas.strokes), page.canvas.revision
    canceled = QSignalSpy(page.cancel_requested)
    changes = QSignalSpy(page.options_changed)
    page.language.setCurrentText("Japanese")
    assert changes.at(0) == [{"drawing_language": "ja"}]
    assert page.settings.drawing_language == "ja"
    assert page.canvas.strokes == strokes
    assert page.canvas.revision == revision
    assert page.canvas.can_undo
    assert canceled.count() == 1
    assert not page.timer.isActive()
    assert not page.language.isEditable()
    page.show_floating()
    try:
        assert not page.floating.isAncestorOf(page.language)
        assert not page.floating.findChildren(QComboBox)
        assert page.canvas.strokes == strokes
    finally:
        page.shutdown()


def test_handwriting_header_saves_immediately_and_tracks_saved_settings(qtbot):
    window = MainWindow(Settings(drawing_auto_send=False), True)
    qtbot.addWidget(window)
    page = window.pages["drawing"]
    saved = QSignalSpy(window.settings_saved)
    page.language.setCurrentText("Russian")
    assert window.settings.drawing_language == "ru"
    assert page.tool_settings.collect()["drawing_language"] == "ru"
    assert saved.count() == 1
    window.update_settings(replace(window.settings, drawing_language="ja"))
    assert page.language.currentText() == "Japanese"
    assert saved.count() == 1
