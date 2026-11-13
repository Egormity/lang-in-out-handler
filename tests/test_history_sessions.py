"""Chunk boundaries stay editable internally while history shows complete sessions."""

import sqlite3

from lang_handler.storage import Store
from lang_handler.ui.history import HistoryPage


def test_session_combines_ordered_transcript_translation_and_revised_guides(tmp_path):
    store = Store(tmp_path)
    first = store.add_history("output", "今日は", "Today", session_id="recording")
    second = store.add_history("output", "晴れです。", "is sunny.", session_id="recording")
    started = store.list_history()[0]["created_at"]
    assert store.update_history_translation(first, "It's sunny", "Kyō wa", "its sunny")
    assert store.update_history_translation(second, "today.", "hare desu", "today")
    rows = store.list_history()
    assert len(rows) == 1
    assert rows[0]["id"] == first
    assert rows[0]["source_text"] == "今日は晴れです。"
    assert rows[0]["translated_text"] == "It's sunny today."
    assert rows[0]["source_pronunciation"] == "Kyō wa hare desu"
    assert rows[0]["translation_pronunciation"] == "its sunny today"
    assert rows[0]["segment_count"] == 2
    assert rows[0]["created_at"] == started
    assert [part["id"] for part in store.list_history_segments(session_id="recording")] == [
        second, first
    ]
    store.close()
    reopened = Store(tmp_path)
    assert reopened.list_history() == rows
    reopened.close()


def test_limits_count_complete_sessions_even_with_interleaved_tools(tmp_path):
    store = Store(tmp_path)
    first = store.add_history("input", "first", session_id="dictation")
    standalone = store.add_history("translate", "  original text\n")
    store.add_history("input", "second", session_id="dictation")
    latest = store.list_history(1)
    assert len(latest) == 1
    assert latest[0]["id"] == first
    assert latest[0]["source_text"] == "first second"
    assert latest[0]["segment_count"] == 2
    all_entries = store.list_history(2)
    assert [entry["id"] for entry in all_entries] == [first, standalone]
    assert all_entries[1]["source_text"] == "  original text\n"
    store.close()


def test_separate_recordings_and_modes_never_merge_by_timestamp_or_text(tmp_path):
    store = Store(tmp_path)
    store.add_history("input", "one", session_id="first")
    store.add_history("input", "two", session_id="second")
    store.add_history("output", "three", session_id="second")
    store.add_history("input", "legacy one")
    store.add_history("input", "legacy two")
    assert len(store.list_history()) == 5
    assert len(store.list_history_segments(session_id="second", mode="input")) == 1
    store.delete_history()
    assert store.list_history() == store.list_history_segments() == []
    store.close()


def test_v2_upgrade_preserves_unidentified_sessions_as_individual_entries(tmp_path):
    path = tmp_path / "history.sqlite3"
    with sqlite3.connect(path) as database:
        database.executescript("""
            CREATE TABLE preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mode TEXT NOT NULL,
                source_text TEXT NOT NULL,
                translated_text TEXT NOT NULL DEFAULT '',
                source_pronunciation TEXT NOT NULL DEFAULT '',
                translation_pronunciation TEXT NOT NULL DEFAULT '',
                model TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT '2026-11-13T12:00:00Z'
            );
            INSERT INTO history(mode, source_text) VALUES ('input', 'first'), ('input', 'second');
            PRAGMA user_version=2;
        """)
    store = Store(tmp_path)
    entries = store.list_history()
    assert [entry["source_text"] for entry in entries] == ["second", "first"]
    assert all(entry["session_id"] == "" for entry in entries)
    assert all(entry["created_at"] == "2026-11-13T12:00:00Z" for entry in entries)
    store.close()
    with sqlite3.connect(path) as database:
        assert database.execute("PRAGMA user_version").fetchone()[0] == 3


def test_history_session_selection_stays_on_same_entry_when_more_chunks_arrive(qtbot, tmp_path):
    store = Store(tmp_path)
    first = store.add_history("output", "first", "one", session_id="captions")
    store.add_history("translate", "other entry")
    page = HistoryPage()
    qtbot.addWidget(page)
    page.set_entries(store.list_history())
    page.table.selectRow(1)
    assert page.detail.text.toPlainText() == "first"
    store.add_history("output", "second", "two", session_id="captions")
    page.set_entries(store.list_history())
    assert page.table.rowCount() == 2
    assert page.visible_entries[page.table.currentRow()]["id"] == first
    assert page.detail.text.toPlainText() == "first second"
    assert page.translation.text.toPlainText() == "one two"
    revision = page.detail.audio.revision
    page.set_entries(store.list_history())
    assert page.detail.audio.revision == revision
    page.search.setText("first second")
    assert page.table.rowCount() == 1
    store.close()
