"""Revisable captions update existing records and cannot resurrect deleted history."""

import threading

from test_controller import FakeService

from lang_handler.results import CaptionRevision, TranslationResult

pytest_plugins = ("test_controller",)


def revised(segments):
    contextual = len(segments) > 1
    return [CaptionRevision(
        segment_id, text,
        TranslationResult("bridge" if contextual else "chopsticks", "source reading", "new pronunciation"),
    ) for segment_id, text in segments]


def test_live_context_revises_one_record_in_place_without_duplicate_history(controller, qtbot, monkeypatch):
    class Service(FakeService):
        def revise_captions(self, segments, *args):
            return revised(segments)

    monkeypatch.setattr("lang_handler.pipeline.OpenAIService", Service)
    c = controller
    c.pipeline.enqueue("output", "はし".encode(), c.settings, c.key)
    qtbot.waitUntil(lambda: not c.pipeline_busy("output"))
    first = c.store.list_history()[0]
    assert first["translated_text"] == "chopsticks"
    c.pipeline.enqueue("output", "を渡る".encode(), c.settings, c.key)
    qtbot.waitUntil(lambda: not c.pipeline_busy("output"))
    rows = c.store.list_history()
    assert len(rows) == 2
    earlier = next(row for row in rows if row["id"] == first["id"])
    assert earlier["source_text"] == first["source_text"] == "はし"
    assert earlier["created_at"] == first["created_at"]
    assert earlier["translated_text"] == "bridge"
    assert earlier["translation_pronunciation"] == "new pronunciation"
    assert len(c.caption_history) == 2


def test_file_context_revises_previous_record_in_place(controller, qtbot, monkeypatch):
    calls = []

    class Service(FakeService):
        def revise_captions(self, segments, *args):
            calls.append(list(segments))
            return revised(segments)

    monkeypatch.setattr("lang_handler.file_import.OpenAIService", Service)
    monkeypatch.setattr("lang_handler.file_import.audio_file_chunks", lambda *args: iter([b"first", b"second"]))
    c = controller
    c.workflows.import_file("output", "synthetic.wav", True)
    qtbot.waitUntil(lambda: not c.workflows.imports)
    assert len(calls) == 2
    assert calls[1][0] == calls[0][0]
    assert len(calls[1]) == 2
    rows = list(reversed(c.store.list_history()))
    assert len(rows) == 2
    assert [row["source_text"] for row in rows] == ["first", "second"]
    assert [row["translated_text"] for row in rows] == ["bridge", "bridge"]


def test_late_revisions_never_recreate_deleted_history(controller, qtbot, monkeypatch):
    started, release = threading.Event(), threading.Event()
    calls = []

    class Service(FakeService):
        def revise_captions(self, segments, *args):
            calls.append(list(segments))
            if len(calls) == 1:
                started.set()
                assert release.wait(3)
            return revised(segments)

    monkeypatch.setattr("lang_handler.pipeline.OpenAIService", Service)
    c = controller
    try:
        c.pipeline.enqueue("output", b"deleted original", c.settings, c.key)
        qtbot.waitUntil(started.is_set)
        old_id = c.store.list_history()[0]["id"]
        c.delete_history()
        assert not c.caption_history
        assert c.store.list_history() == []
        c.pipeline.enqueue("output", b"new original", c.settings, c.key)
        qtbot.waitUntil(lambda: len(c.store.list_history()) == 1)
        release.set()
        qtbot.waitUntil(lambda: not c.pipeline_busy("output"))
        rows = c.store.list_history()
        assert len(rows) == 1
        assert rows[0]["id"] != old_id
        assert rows[0]["source_text"] == "new original"
        assert rows[0]["translated_text"] == "bridge"
    finally:
        release.set()


def test_restarting_capture_waits_for_pending_revision_then_resets_context(controller, qtbot, monkeypatch):
    started, release = threading.Event(), threading.Event()
    contexts = []

    class Service(FakeService):
        def revise_captions(self, segments, *args):
            contexts.append(list(segments))
            if len(contexts) == 1:
                started.set()
                assert release.wait(3)
            return revised(segments)

    monkeypatch.setattr("lang_handler.pipeline.OpenAIService", Service)
    c = controller
    try:
        c.start("output", True)
        c.captures["output"].chunk.emit(b"previous session")
        qtbot.waitUntil(started.is_set)
        c.stop("output")
        c.start("output", True)
        assert not c.captures["output"].is_running
        assert "previous recording" in c.window.status.text()
        release.set()
        qtbot.waitUntil(lambda: not c.pipeline_busy("output"))
        c.start("output", True)
        assert c.captures["output"].is_running
        c.captures["output"].chunk.emit(b"fresh session")
        c.stop("output")
        qtbot.waitUntil(lambda: not c.pipeline_busy("output"))
        assert [text for _, text in contexts[-1]] == ["fresh session"]
        assert len(c.store.list_history()) == 2
    finally:
        release.set()


def test_coalesced_revision_updates_existing_records_instead_of_adding_snapshots(controller, qtbot, monkeypatch):
    started, release = threading.Event(), threading.Event()
    contexts = []

    class Service(FakeService):
        def revise_captions(self, segments, *args):
            contexts.append(list(segments))
            if len(contexts) == 1:
                started.set()
                assert release.wait(3)
            return revised(segments)

    monkeypatch.setattr("lang_handler.pipeline.OpenAIService", Service)
    c = controller
    try:
        c.pipeline.enqueue("output", b"one", c.settings, c.key)
        qtbot.waitUntil(started.is_set)
        c.pipeline.enqueue("output", b"two", c.settings, c.key)
        c.pipeline.enqueue("output", b"three", c.settings, c.key)
        qtbot.waitUntil(lambda: len(c.store.list_history()) == 3)
        initial = {row["source_text"]: row for row in c.store.list_history()}
        release.set()
        qtbot.waitUntil(lambda: not c.pipeline_busy("output"))
        assert len(contexts) == 2
        assert len(contexts[-1]) == 3
        final = {row["source_text"]: row for row in c.store.list_history()}
        assert set(initial) == set(final) == {"one", "two", "three"}
        for text in initial:
            assert final[text]["id"] == initial[text]["id"]
            assert final[text]["created_at"] == initial[text]["created_at"]
            assert final[text]["translated_text"] == "bridge"
    finally:
        release.set()
