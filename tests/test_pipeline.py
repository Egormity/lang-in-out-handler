"""Recognition is durable; contextual revisions remain bounded, ordered, and cancellable."""

import threading

import pytest
from PySide6.QtCore import QThread

from lang_handler.errors import ServiceError
from lang_handler.jobs import Jobs
from lang_handler.pipeline import CaptionPipeline
from lang_handler.results import CaptionRevision, TranslationResult
from lang_handler.settings import Settings


class Service:
    def __init__(self, key, **kwargs):
        pass

    def transcribe(self, audio, *args):
        return audio.decode()

    def revise_captions(self, segments, *args):
        return [CaptionRevision(segment_id, text, TranslationResult("translated " + text, "source", "target"))
                for segment_id, text in segments]

    def close(self):
        pass


@pytest.fixture
def pipeline(qapp, monkeypatch):
    monkeypatch.setattr("lang_handler.pipeline.OpenAIService", Service)
    monkeypatch.setattr("lang_handler.pipeline.transcribe_file_once",
                        lambda service, audio, model, language, instructions, **kwargs:
                        service.transcribe(audio, model, language, instructions))
    jobs = Jobs()
    pipeline = CaptionPipeline(jobs)
    yield pipeline
    pipeline.shutdown()
    jobs.cancel_all()
    assert jobs.pool.waitForDone(4000)
    qapp.processEvents()


def drained(pipeline):
    return not any(pipeline.busy.values()) and not any(pipeline.queues.values())


def test_recognition_is_saved_once_before_ui_and_revision_on_gui_thread(pipeline, qtbot, qapp):
    saved, transcript, revisions, threads, order = [], [], [], [], []

    def source(*row):
        saved.append(row)
        order.append(("save", row[1]))
        threads.append(QThread.currentThread())

    def visible(mode, text, segment_id):
        transcript.append((mode, text, segment_id))
        order.append(("show", segment_id))
        threads.append(QThread.currentThread())

    pipeline.source_ready.connect(source)
    pipeline.transcript.connect(visible)
    pipeline.revisions.connect(revisions.append)
    for audio in (b"one", b"two", b"three"):
        pipeline.enqueue("output", audio, Settings(translation_provider="openai", output_context_seconds=0), "key")
    qtbot.waitUntil(lambda: drained(pipeline))
    assert [row[2] for row in saved] == ["one", "two", "three"]
    assert len(saved) == 3
    assert [row[1] for row in transcript] == ["one", "two", "three"]
    assert order == [(kind, number) for number in range(1, 4) for kind in ("save", "show")]
    assert [item.source_text for item in revisions[-1]] == ["one", "two", "three"]
    assert all(thread == qapp.thread() for thread in threads)


def test_pending_snapshots_coalesce_and_new_context_can_revise_earlier_text(pipeline, qtbot, monkeypatch):
    started, release = threading.Event(), threading.Event()
    calls, revisions, saved = [], [], []

    class ContextService(Service):
        def revise_captions(self, segments, *args):
            calls.append(list(segments))
            if len(calls) == 1:
                started.set()
                assert release.wait(3)
            resolved = "bridge" if len(segments) > 1 else "chopsticks"
            return [CaptionRevision(segment_id, text, TranslationResult(resolved, "hashi", "reading"))
                    for segment_id, text in segments]

    monkeypatch.setattr("lang_handler.pipeline.OpenAIService", ContextService)
    pipeline.revisions.connect(revisions.append)
    pipeline.source_ready.connect(lambda *row: saved.append(row))
    try:
        pipeline.enqueue("output", "はし".encode(), Settings(translation_provider="openai", output_context_seconds=0), "key")
        qtbot.waitUntil(started.is_set)
        pipeline.enqueue("output", "を渡って".encode(), Settings(translation_provider="openai", output_context_seconds=0), "key")
        pipeline.enqueue("output", "川の向こうへ行く".encode(), Settings(translation_provider="openai", output_context_seconds=0), "key")
        qtbot.waitUntil(lambda: len(saved) == 3)
        assert len(pipeline.queues["translation"]) == 1
        release.set()
        qtbot.waitUntil(lambda: drained(pipeline))
        assert len(calls) == 2
        assert [segment_id for segment_id, _ in calls[1]] == [1, 2, 3]
        assert revisions[0][0].result.translation == "chopsticks"
        assert revisions[1][0].segment_id == revisions[0][0].segment_id
        assert revisions[1][0].result.translation == "bridge"
        assert len(saved) == 3
    finally:
        release.set()


def test_recent_context_drops_only_already_translated_sources(pipeline, qtbot, monkeypatch):
    calls = []

    class RecordingService(Service):
        def revise_captions(self, segments, *args):
            calls.append(list(segments))
            return super().revise_captions(segments, *args)

    monkeypatch.setattr("lang_handler.pipeline.OpenAIService", RecordingService)
    for index in range(10):
        pipeline.enqueue("output", str(index).encode(), Settings(translation_provider="openai", output_context_seconds=0), "key")
        qtbot.waitUntil(lambda: drained(pipeline))
    assert max(map(len, calls)) == 6
    assert [segment_id for segment_id, _ in calls[-1]] == list(range(5, 11))
    assert len(pipeline.context) == 6
    assert not pipeline.untranslated


def test_translation_overload_preserves_all_recognition_and_reports_error(pipeline, qtbot, monkeypatch):
    started, release = threading.Event(), threading.Event()
    saved, errors, revisions = [], [], []

    class SlowService(Service):
        def revise_captions(self, segments, *args):
            started.set()
            assert release.wait(3)
            return super().revise_captions(segments, *args)

    monkeypatch.setattr("lang_handler.pipeline.OpenAIService", SlowService)
    pipeline.source_ready.connect(lambda *row: saved.append(row))
    pipeline.error.connect(lambda *row: errors.append(row))
    pipeline.revisions.connect(revisions.append)
    try:
        pipeline.enqueue("output", b"first", Settings(translation_provider="openai", output_context_seconds=0), "key")
        qtbot.waitUntil(started.is_set)
        for index in range(2, 8):
            pipeline.enqueue("output", str(index).encode(), Settings(translation_provider="openai", output_context_seconds=0), "key")
            qtbot.waitUntil(lambda expected=index: len(saved) == expected)
        assert len(saved) == 7
        assert len(errors) == 1
        assert "falling behind" in errors[0][1]
        assert not pipeline.queues["translation"]
        release.set()
        qtbot.waitUntil(lambda: drained(pipeline))
        assert revisions == []
    finally:
        release.set()


def test_recognition_backlog_is_bounded_and_aborted_results_never_save(pipeline, qtbot, monkeypatch):
    started, release = threading.Event(), threading.Event()
    saved, errors = [], []

    class SlowService(Service):
        def transcribe(self, audio, *args):
            started.set()
            assert release.wait(3)
            return "old"

    monkeypatch.setattr("lang_handler.pipeline.OpenAIService", SlowService)
    pipeline.source_ready.connect(lambda *row: saved.append(row))
    pipeline.error.connect(lambda *row: errors.append(row))
    try:
        pipeline.enqueue("input", b"first", Settings(translation_provider="openai", output_context_seconds=0), "key")
        qtbot.waitUntil(started.is_set)
        for _ in range(7):
            pipeline.enqueue("input", b"queued", Settings(translation_provider="openai", output_context_seconds=0), "key")
        assert len(errors) == 1
        release.set()
        qtbot.waitUntil(lambda: drained(pipeline))
        assert saved == []
    finally:
        release.set()


@pytest.mark.parametrize("operation", ["abort", "shutdown", "begin_session"])
def test_cancel_discards_late_revisions_without_duplicating_saved_sources(pipeline, qtbot, monkeypatch, operation):
    started, release = threading.Event(), threading.Event()
    saved, revisions = [], []

    class SlowService(Service):
        def revise_captions(self, segments, *args):
            started.set()
            assert release.wait(3)
            return super().revise_captions(segments, *args)

    monkeypatch.setattr("lang_handler.pipeline.OpenAIService", SlowService)
    pipeline.source_ready.connect(lambda *row: saved.append(row))
    pipeline.revisions.connect(revisions.append)
    try:
        pipeline.enqueue("output", b"already recognized", Settings(translation_provider="openai", output_context_seconds=0), "key")
        qtbot.waitUntil(started.is_set)
        if operation == "shutdown":
            pipeline.shutdown()
        else:
            getattr(pipeline, operation)("output")
        release.set()
        qtbot.waitUntil(lambda: drained(pipeline))
        assert len(saved) == 1
        assert revisions == []
    finally:
        release.set()


def test_translation_failure_keeps_recognition_once(pipeline, qtbot, monkeypatch):
    saved, errors = [], []

    class FailingService(Service):
        def revise_captions(self, segments, *args):
            raise ServiceError("OpenAI API credits are exhausted.")

    monkeypatch.setattr("lang_handler.pipeline.OpenAIService", FailingService)
    pipeline.source_ready.connect(lambda *row: saved.append(row))
    pipeline.error.connect(lambda *row: errors.append(row))
    pipeline.enqueue("output", b"recognized words", Settings(translation_provider="openai", output_context_seconds=0), "key")
    qtbot.waitUntil(lambda: drained(pipeline))
    pipeline.shutdown()
    assert len(saved) == 1
    assert saved[0][2] == "recognized words"
    assert "credits" in errors[0][1]


def test_context_restarts_for_target_changes_and_translation_toggles(pipeline, qtbot, monkeypatch):
    calls = []

    class RecordingService(Service):
        def revise_captions(self, segments, model, target, instructions, reasoning):
            calls.append((list(segments), target, reasoning))
            return super().revise_captions(segments)

    monkeypatch.setattr("lang_handler.pipeline.OpenAIService", RecordingService)
    settings = Settings(translation_provider="openai", output_context_seconds=0)
    for index, (enabled, target) in enumerate([(True, "English"), (True, "English"), (False, "English"), (True, "English"), (True, "French")], 1):
        settings.translation_enabled = enabled
        settings.target_language = target
        pipeline.enqueue("output", str(index).encode(), settings, "key")
        qtbot.waitUntil(lambda: drained(pipeline))
    assert [[item[0] for item in segments] for segments, _, _ in calls] == [[1], [1, 2], [4], [5]]
    assert [target for _, target, _ in calls] == ["English", "English", "English", "French"]
    assert all(reasoning == "medium" for _, _, reasoning in calls)


def test_new_session_has_new_ids_and_no_previous_context(pipeline, qtbot, monkeypatch):
    calls = []

    class RecordingService(Service):
        def revise_captions(self, segments, *args):
            calls.append(list(segments))
            return super().revise_captions(segments)

    monkeypatch.setattr("lang_handler.pipeline.OpenAIService", RecordingService)
    pipeline.enqueue("output", b"same phrase", Settings(translation_provider="openai", output_context_seconds=0), "key")
    qtbot.waitUntil(lambda: drained(pipeline))
    pipeline.begin_session("output")
    pipeline.enqueue("output", b"same phrase", Settings(translation_provider="openai", output_context_seconds=0), "key")
    qtbot.waitUntil(lambda: drained(pipeline))
    assert calls == [[(1, "same phrase")], [(2, "same phrase")]]


def test_pending_count_includes_revision_after_recognition_finishes(pipeline, qtbot, monkeypatch):
    started, release = threading.Event(), threading.Event()
    pending = []

    class SlowService(Service):
        def revise_captions(self, segments, *args):
            started.set()
            assert release.wait(3)
            return super().revise_captions(segments)

    monkeypatch.setattr("lang_handler.pipeline.OpenAIService", SlowService)
    pipeline.pending_changed.connect(lambda mode, count: pending.append((mode, count)))
    try:
        pipeline.enqueue("output", b"pending", Settings(translation_provider="openai", output_context_seconds=0), "key")
        qtbot.waitUntil(started.is_set)
        qtbot.waitUntil(lambda: not pipeline.busy["output"])
        assert pending[-1][1] > 0
        release.set()
        qtbot.waitUntil(lambda: drained(pipeline))
        assert pending[-1] == ("output", 0)
    finally:
        release.set()


def test_cancelled_job_drops_queued_results_but_cleans_up(qapp):
    jobs = Jobs()
    results, progress, finished = [], [], []

    def work(cancel, report):
        report("old progress")
        return "old result"

    job = jobs.submit(work, results.append, progress=progress.append, finished=lambda: finished.append(True))
    assert jobs.pool.waitForDone(2000)
    job.cancelled.set()
    qapp.processEvents()
    assert results == progress == []
    assert finished == [True]
    assert not jobs.active
