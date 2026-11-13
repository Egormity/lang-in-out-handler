"""Recording boundaries, rather than recognition chunks, define history entries."""

import pytest
from test_controller import FakeService

from lang_handler.results import CaptionRevision, TranslationResult

pytest_plugins = ("test_controller",)


@pytest.mark.parametrize("mode", ["input", "output"])
def test_capture_chunks_share_one_entry_and_restart_starts_another(controller, qtbot, mode):
    c = controller
    c.start(mode, True)
    first_session = c.history_sessions[mode]
    capture = c.captures[mode]
    capture.chunk.emit(b"first")
    capture.chunk.emit(b"second")
    c.stop(mode)
    qtbot.waitUntil(lambda: not c.pipeline_busy(mode))
    rows = c.store.list_history()
    assert len(rows) == 1
    assert rows[0]["source_text"] == "first second"
    assert rows[0]["session_id"] == first_session
    assert rows[0]["segment_count"] == 2
    first_id = rows[0]["id"]

    c.start(mode, True)
    assert c.history_sessions[mode] != first_session
    capture.chunk.emit(b"new recording")
    c.stop(mode)
    qtbot.waitUntil(lambda: not c.pipeline_busy(mode))
    rows = c.store.list_history()
    assert [row["source_text"] for row in rows] == ["new recording", "first second"]
    assert rows[1]["id"] == first_id
    assert len(c.store.list_history_segments()) == 3
    assert c.window.pages["history"].table.rowCount() == 2


def test_later_caption_context_revises_earlier_translation_in_the_same_entry(
    controller, qtbot, monkeypatch
):
    class Service(FakeService):
        def revise_captions(self, segments, *args):
            if len(segments) == 1:
                return [CaptionRevision(
                    segments[0][0], segments[0][1],
                    TranslationResult("chopsticks", "hashi", "old reading"),
                )]
            return [
                CaptionRevision(segments[0][0], segments[0][1],
                                TranslationResult("bridge", "hashi", "bridge reading")),
                CaptionRevision(segments[1][0], segments[1][1],
                                TranslationResult("crossing", "o wataru", "crossing reading")),
            ]

    monkeypatch.setattr("lang_handler.pipeline.OpenAIService", Service)
    c = controller
    c.start("output", True)
    c.captures["output"].chunk.emit("はし".encode())
    qtbot.waitUntil(lambda: not c.pipeline_busy("output"))
    first = c.store.list_history()[0]
    assert first["translated_text"] == "chopsticks"
    c.captures["output"].chunk.emit("を渡る".encode())
    c.stop("output")
    qtbot.waitUntil(lambda: not c.pipeline_busy("output"))
    rows = c.store.list_history()
    assert len(rows) == 1
    entry = rows[0]
    assert entry["id"] == first["id"]
    assert entry["created_at"] == first["created_at"]
    assert entry["source_text"] == "はしを渡る"
    assert entry["translated_text"] == "bridge crossing"
    assert entry["source_pronunciation"] == "hashi o wataru"
    assert entry["translation_pronunciation"] == "bridge reading crossing reading"
    assert c.window.pages["history"].table.rowCount() == 1
    assert c.window.pages["history"].translation.text.toPlainText() == "bridge crossing"


def test_simultaneous_microphone_and_output_recordings_keep_independent_groups(controller, qtbot):
    c = controller
    c.start("input", True)
    c.start("output", True)
    assert c.history_sessions["input"] != c.history_sessions["output"]
    c.captures["input"].chunk.emit(b"my first")
    c.captures["output"].chunk.emit(b"their first")
    c.captures["input"].chunk.emit(b"my second")
    c.captures["output"].chunk.emit(b"their second")
    c.stop("input")
    c.stop("output")
    qtbot.waitUntil(lambda: not c.pipeline_busy("input") and not c.pipeline_busy("output"))
    rows = c.store.list_history()
    assert len(rows) == 2
    entries = {row["mode"]: row for row in rows}
    assert entries["input"]["source_text"] == "my first my second"
    assert entries["output"]["source_text"] == "their first their second"
    assert all(entry["segment_count"] == 2 for entry in rows)
    assert len(c.store.list_history_segments()) == 4
