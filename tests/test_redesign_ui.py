"""Continuous content and compact actions preserve usability in the simpler layout."""

from PySide6.QtCore import QPoint
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QComboBox

from lang_handler.results import TranslationResult
from lang_handler.settings import Settings
from lang_handler.ui.capture_page import CapturePage
from lang_handler.ui.continuous_pane import ContinuousPane, flowing_text
from lang_handler.ui.drawing_page import DrawingPage
from lang_handler.ui.overlay import CaptionOverlay
from lang_handler.ui.text_pages import TranslatePage
from lang_handler.ui.theme import STYLE


def test_live_text_flows_and_context_replaces_existing_words(qtbot):
    pane = ContinuousPane("Transcript", "")
    qtbot.addWidget(pane)
    pane.append("I saw her", segment_id=1)
    pane.append("duck by the pond.", segment_id=2)
    assert pane.toPlainText() == "I saw her duck by the pond."
    pane.upsert(1, "I saw her duck", "reading one")
    pane.upsert(2, "by the pond.", "reading two")
    assert pane.toPlainText() == "I saw her duck by the pond."
    pane.upsert(1, "", "")
    assert pane.toPlainText() == "by the pond."
    pane.clear()
    assert not pane.revise(1, "old")
    assert pane.toPlainText() == ""
    assert not hasattr(pane, "entries")
    assert flowing_text(["今日は", "いい天気です。", "明日は雨です。"] ) == "今日はいい天気です。明日は雨です。"
    assert flowing_text(["First paragraph.\n\nSecond paragraph.", "More text."]) == "First paragraph.\n\nSecond paragraph. More text."


def test_revision_keeps_reader_scroll_and_selected_text(qtbot):
    pane = ContinuousPane("Transcript", "")
    qtbot.addWidget(pane)
    pane.setStyleSheet(STYLE)
    pane.resize(400, 250)
    pane.show()
    pane.append("\n".join(f"Line {i}: words to read" for i in range(80)), segment_id=1)
    qtbot.wait(40)
    scroll = pane.scroll.verticalScrollBar()
    assert scroll.maximum() > 200
    scroll.setValue(100)
    cursor = pane.text.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(6, QTextCursor.MoveMode.KeepAnchor)
    pane.text.setTextCursor(cursor)
    selected = cursor.selectedText()
    pane.append("another sentence", segment_id=2)
    qtbot.wait(40)
    assert scroll.value() == 100
    assert pane.text.textCursor().selectedText() == selected


def test_capture_has_one_primary_action_and_contextual_settings(qtbot):
    page = CapturePage("output", Settings())
    qtbot.addWidget(page)
    page.setStyleSheet(STYLE)
    page.resize(650, 580)
    page.show()
    assert page.start_button.isVisible()
    assert page.stop_button.isHidden()
    assert not hasattr(page, "capture_type")
    assert not hasattr(page, "option")
    page.set_recording(True)
    assert page.start_button.isHidden()
    assert page.stop_button.isVisible()
    requested = QSignalSpy(page.settings_requested)
    page.settings_button.click()
    assert requested.count() == 1
    assert page.settings_view.isAncestorOf(page.tool_settings)
    assert not page.settings_view.isWindow()


def test_text_and_pronunciation_stay_together_and_actions_are_accessible(qtbot):
    page = TranslatePage(Settings())
    qtbot.addWidget(page)
    page.setStyleSheet(STYLE)
    page.resize(650, 580)
    page.show()
    page.source.text.setPlainText("カフェ")
    page.set_result(TranslationResult("Café", "Kafe", "/kæˈfeɪ/"))
    qtbot.wait(20)
    original = page.source
    assert original.pronunciation.y() - original.text.y() < 90
    requested = QSignalSpy(page.speech_requested)
    original.speak.click()
    assert requested.at(0) == ["カフェ"]
    assert original.speak.text() == ""
    assert original.speak.accessibleName() == "Speak original"
    assert page.run.mapTo(page, QPoint()).y() < page.splitter.geometry().top()


def test_floating_canvas_keeps_settings_out_and_recognize_above_canvas(qtbot):
    page = DrawingPage(Settings(drawing_auto_send=False))
    qtbot.addWidget(page)
    page.setStyleSheet(STYLE)
    page.resize(650, 580)
    page.show_floating()
    try:
        qtbot.wait(20)
        assert not page.floating.findChildren(QComboBox)
        assert not page.floating.isAncestorOf(page.tool_settings)
        assert page.send_button.mapTo(page.workspace, QPoint()).y() < page.canvas.geometry().top()
        assert page.canvas.height() >= 200
    finally:
        page.shutdown()


def test_floating_captions_update_one_continuous_document(qtbot):
    overlay = CaptionOverlay(Settings())
    qtbot.addWidget(overlay)
    overlay.resize(460, 230)
    overlay.show()
    overlay.append_caption("今日は", segment_id=1)
    overlay.append_caption("晴れです。", segment_id=2)
    overlay.annotate_translation(1, TranslationResult("Today", "Kyō wa", "/təˈdeɪ/"))
    overlay.annotate_translation(2, TranslationResult("is sunny.", "hare desu", "/ɪz ˈsʌni/"))
    assert overlay.transcript.toPlainText() == "今日は晴れです。"
    assert overlay.translation.toPlainText() == "Today is sunny."
    overlay.annotate_translation(1, TranslationResult("It's sunny", "Kyō wa", "/ɪts ˈsʌni/"))
    overlay.annotate_translation(2, TranslationResult("today.", "hare desu", "/təˈdeɪ/"))
    assert overlay.translation.toPlainText() == "It's sunny today."
    assert all(combo.objectName() == "audioSpeed" for combo in overlay.findChildren(QComboBox))
    overlay.clear()
    overlay.annotate_translation(1, TranslationResult("stale", "stale", "stale"))
    assert overlay.translation.toPlainText() == ""
    overlay.pin_control.stop()
