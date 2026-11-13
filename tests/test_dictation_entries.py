"""Microphone recognitions remain separate rows with independent actions."""

from PySide6.QtTest import QSignalSpy

from lang_handler.settings import Settings
from lang_handler.ui.continuous_pane import ContinuousPane
from lang_handler.ui.dictation_entries import DictationEntries
from lang_handler.ui.main_window import MainWindow


def test_dictation_keeps_each_recognition_separate_while_captions_flow(qtbot, qapp):
    window = MainWindow(Settings(), True)
    qtbot.addWidget(window)
    window.append_result("input", "first phrase", segment_id=1)
    window.append_result("input", "second phrase", segment_id=2)
    results = window.pages["input"].results
    assert isinstance(results, DictationEntries)
    assert [entry.text.toPlainText() for entry in results.entries] == [
        "first phrase", "second phrase"
    ]
    assert results.toPlainText() == "first phrase\nsecond phrase"
    requests = QSignalSpy(window.audio_requested)
    first, second = results.entries
    first.speak.click()
    second.speak.click()
    assert requests.at(0) == ["first phrase", first.audio]
    assert requests.at(1) == ["second phrase", second.audio]
    first.copy.click()
    assert qapp.clipboard().text() == "first phrase"
    second.copy.click()
    assert qapp.clipboard().text() == "second phrase"

    window.append_result("output", "first phrase", segment_id=3)
    window.append_result("output", "second phrase", segment_id=4)
    captions = window.pages["output"].results
    assert isinstance(captions, ContinuousPane)
    assert captions.toPlainText() == "first phrase second phrase"


def test_new_dictation_does_not_invalidate_audio_requested_for_an_older_result(qtbot):
    results = DictationEntries()
    qtbot.addWidget(results)
    results.append("older result", segment_id=1)
    audio = results.entries[0].audio
    revision = audio.revision
    audio.set_generating(True)
    results.append("newer result", segment_id=2)
    assert audio.revision == revision
    assert not audio.speak.isEnabled()
    assert results.entries[1].speak.isEnabled()
    results.clear()
    assert audio.revision > revision
    assert results.toPlainText() == ""
    assert results.entries == []
    assert not results.empty.isHidden()


def test_repeated_segment_updates_its_row_and_preserves_other_entries(qtbot):
    results = DictationEntries()
    qtbot.addWidget(results)
    results.append("こんにちは", "Konnichiwa", segment_id=1)
    results.append("second", segment_id=2)
    second = results.entries[1]
    results.append("こんばんは", "Konbanwa", segment_id=1)
    assert len(results.entries) == 2
    assert results.entries[1] is second
    assert results.entries[0].text.toPlainText() == "こんばんは"
    assert results.entries[0].pronunciation.text.toPlainText() == "Konbanwa"
    assert results.revise(1, pronunciation="updated guide")
    assert results.entries[0].pronunciation.text.toPlainText() == "updated guide"
    assert not results.revise(99, "missing")


def test_result_list_keeps_scroll_position_when_reading_older_dictations(qtbot):
    results = DictationEntries()
    qtbot.addWidget(results)
    results.resize(600, 330)
    results.show()
    for index in range(12):
        results.append(f"Recognized result {index}", segment_id=index)
    scrollbar = results.scroll.verticalScrollBar()
    qtbot.waitUntil(lambda: scrollbar.maximum() > 200)
    scrollbar.setValue(70)
    results.append("latest dictation", segment_id=12)
    qtbot.waitUntil(lambda: results.entries[-1].isVisible())
    assert scrollbar.value() == 70
