"""Exercise real Qt worker delivery and queue lifetime without network access."""

import threading
import time

import pytest
from PySide6.QtCore import QThread

from lang_handler.errors import ServiceError
from lang_handler.jobs import Jobs
from lang_handler.pipeline import CaptionPipeline
from lang_handler.results import TranslationResult
from lang_handler.settings import Settings


@pytest.fixture
def pipeline(qapp):
    jobs = Jobs()
    pipeline = CaptionPipeline(jobs)
    yield pipeline
    pipeline.shutdown()
    jobs.cancel_all()
    assert jobs.pool.waitForDone(4000)
    qapp.processEvents()


def test_live_sources_and_translations_stay_ordered_on_ui_thread(
    pipeline, qtbot, qapp, monkeypatch
):
    worker_threads = []

    class Service:
        def __init__(self, key, **kwargs):
            pass

        def transcribe(self, audio, *args):
            worker_threads.append(QThread.currentThread())
            return audio.decode()

        def translate(self, text, *args):
            worker_threads.append(QThread.currentThread())
            time.sleep(0.01)
            return TranslationResult("translated " + text, "reading " + text, "translated reading " + text)

        def close(self):
            pass

    monkeypatch.setattr("lang_handler.pipeline.OpenAIService", Service)
    sources, translations, completed, delivery_threads = [], [], [], []

    def receive_source(mode, text, segment_id):
        delivery_threads.append(QThread.currentThread())
        sources.append((mode, text, segment_id))

    def receive_translation(mode, segment_id, result):
        delivery_threads.append(QThread.currentThread())
        translations.append((mode, segment_id, result.translation))

    pipeline.transcript.connect(receive_source)
    pipeline.translation.connect(receive_translation)
    pipeline.completed.connect(lambda *row: completed.append(row))
    settings = Settings(translation_enabled=True)
    for text in (b"one", b"two", b"three"):
        pipeline.enqueue("output", text, settings, "test-key")
    qtbot.waitUntil(lambda: len(completed) == 3)
    assert sources == [("output", text, index) for index, text in enumerate(("one", "two", "three"), 1)]
    assert translations == [("output", index, "translated " + text) for index, text in enumerate(("one", "two", "three"), 1)]
    assert [(row[1], row[2].translation if isinstance(row[2], TranslationResult) else row[2]) for row in completed] == [
        (text, "translated " + text) for text in ("one", "two", "three")
    ]
    assert all(thread != qapp.thread() for thread in worker_threads)
    assert all(thread == qapp.thread() for thread in delivery_threads)


def test_abort_discards_old_generation_and_allows_a_fresh_recording(pipeline, qtbot, monkeypatch):
    first_started, release_first = threading.Event(), threading.Event()
    calls = []

    class Service:
        def __init__(self, key, **kwargs):
            pass

        def transcribe(self, audio, *args):
            calls.append(audio)
            if audio == b"old":
                first_started.set()
                assert release_first.wait(2)
            return audio.decode()

        def close(self):
            pass

    monkeypatch.setattr("lang_handler.pipeline.OpenAIService", Service)
    completed = []
    pipeline.completed.connect(lambda *row: completed.append(row))
    settings = Settings(translation_enabled=False)
    pipeline.enqueue("input", b"old", settings, "key")
    pipeline.enqueue("input", b"old queued", settings, "key")
    qtbot.waitUntil(first_started.is_set)
    pipeline.abort("input")
    pipeline.enqueue("input", b"fresh", settings, "key")
    release_first.set()
    qtbot.waitUntil(lambda: len(completed) == 1)
    assert completed[0][1] == "fresh"
    assert calls == [b"old", b"fresh"]


def test_backlog_is_bounded_and_reports_failure_instead_of_dropping_silently(
    pipeline, qtbot, monkeypatch
):
    started, release = threading.Event(), threading.Event()

    class Service:
        def __init__(self, key, **kwargs):
            pass

        def transcribe(self, audio, *args):
            started.set()
            assert release.wait(2)
            return "stale result"

        def close(self):
            pass

    monkeypatch.setattr("lang_handler.pipeline.OpenAIService", Service)
    errors, transcripts = [], []
    pipeline.error.connect(lambda *args: errors.append(args))
    pipeline.transcript.connect(lambda *args: transcripts.append(args))
    settings = Settings(translation_enabled=False)
    pipeline.enqueue("input", b"active", settings, "key")
    qtbot.waitUntil(started.is_set)
    for _ in range(7):
        pipeline.enqueue("input", b"queued", settings, "key")
    assert len(errors) == 1
    assert "falling behind" in errors[0][1]
    assert not pipeline.queues["input"]
    release.set()
    qtbot.waitUntil(lambda: not pipeline.busy["input"])
    assert transcripts == []


def test_quota_failure_aborts_remaining_audio_requests(pipeline, qtbot, monkeypatch):
    calls = []

    class Service:
        def __init__(self, key, **kwargs):
            pass

        def transcribe(self, audio, *args):
            calls.append(audio)
            raise ServiceError("OpenAI API credits are exhausted.")

        def close(self):
            pass

    monkeypatch.setattr("lang_handler.pipeline.OpenAIService", Service)
    errors = []
    pipeline.error.connect(lambda *args: errors.append(args))
    for _ in range(4):
        pipeline.enqueue("output", b"audio", Settings(), "key")
    qtbot.waitUntil(lambda: bool(errors))
    qtbot.waitUntil(lambda: not pipeline.busy["output"])
    assert len(calls) == 1
    assert not pipeline.queues["output"]
    assert "credits" in errors[0][1]


def test_cancelled_job_drops_already_queued_results_but_still_cleans_up(qapp):
    jobs = Jobs()
    results, progress, finished = [], [], []

    def work(cancel, report):
        report("old progress")
        return "old result"

    job = jobs.submit(
        work, results.append, progress=progress.append, finished=lambda: finished.append(True)
    )
    # Deliberately let the worker finish while UI delivery is paused, then cancel.
    assert jobs.pool.waitForDone(2000)
    job.cancelled.set()
    qapp.processEvents()
    assert results == []
    assert progress == []
    assert finished == [True]
    assert not jobs.active


def test_translation_failure_preserves_every_recognized_source_exactly_once(
    pipeline, qtbot, monkeypatch
):
    release_failure = threading.Event()

    class Service:
        def __init__(self, key, **kwargs):
            pass

        def transcribe(self, audio, *args):
            return audio.decode()

        def translate(self, text, *args):
            if text == "one":
                return TranslationResult("translated one", "one", "one")
            assert release_failure.wait(2)
            raise ServiceError("OpenAI API credits are exhausted.")

        def close(self):
            pass

    monkeypatch.setattr("lang_handler.pipeline.OpenAIService", Service)
    sources, completed, errors = [], [], []
    pipeline.transcript.connect(lambda *args: sources.append(args))
    pipeline.completed.connect(lambda *args: completed.append(args))
    pipeline.error.connect(lambda *args: errors.append(args))
    try:
        for audio in (b"one", b"two", b"three"):
            pipeline.enqueue("output", audio, Settings(), "key")
        qtbot.waitUntil(lambda: len(sources) == 3)
        release_failure.set()
        qtbot.waitUntil(lambda: bool(errors))
        qtbot.waitUntil(lambda: not pipeline.busy["translation"])
        assert [(row[1], row[2].translation if isinstance(row[2], TranslationResult) else row[2]) for row in completed] == [
            ("one", "translated one"),
            ("two", ""),
            ("three", ""),
        ]
        pipeline.shutdown()
        assert len(completed) == 3
    finally:
        release_failure.set()


@pytest.mark.parametrize("operation", ["abort", "shutdown"])
def test_abort_and_shutdown_flush_recognized_sources_without_late_duplicates(
    pipeline,
    qtbot,
    monkeypatch,
    operation,
):
    release = threading.Event()

    class Service:
        def __init__(self, key, **kwargs):
            pass

        def transcribe(self, audio, *args):
            return audio.decode()

        def translate(self, text, *args):
            assert release.wait(2)
            return TranslationResult("late translation", "source", "target")

        def close(self):
            pass

    monkeypatch.setattr("lang_handler.pipeline.OpenAIService", Service)
    sources, completed, translated = [], [], []
    pipeline.transcript.connect(lambda *args: sources.append(args))
    pipeline.completed.connect(lambda *args: completed.append(args))
    pipeline.translation.connect(lambda *args: translated.append(args))
    try:
        for audio in (b"one", b"two"):
            pipeline.enqueue("output", audio, Settings(), "key")
        qtbot.waitUntil(lambda: len(sources) == 2)
        if operation == "abort":
            pipeline.abort("output")
        else:
            pipeline.shutdown()
        assert [(row[1], row[2].translation if isinstance(row[2], TranslationResult) else row[2]) for row in completed] == [("one", ""), ("two", "")]
        release.set()
        qtbot.waitUntil(lambda: not pipeline.busy["translation"])
        assert len(completed) == 2
        assert translated == []
    finally:
        release.set()


def test_repeated_text_keeps_segment_identity_across_translation_setting_snapshots(
    pipeline, qtbot, monkeypatch
):
    started, release = threading.Event(), threading.Event()
    calls = []

    class Service:
        def __init__(self, key, **kwargs):
            pass

        def transcribe(self, audio, *args):
            if audio == b"first":
                started.set()
                assert release.wait(2)
            return "はし"

        def translate(self, text, model, target, instructions, reasoning):
            calls.append((text, target, reasoning))
            return TranslationResult(target + " result", "hashi", target + " reading")

        def close(self):
            pass

    monkeypatch.setattr("lang_handler.pipeline.OpenAIService", Service)
    sources, translated, completed = [], [], []
    pipeline.transcript.connect(lambda *args: sources.append(args))
    pipeline.translation.connect(lambda *args: translated.append(args))
    pipeline.completed.connect(lambda *args: completed.append(args))
    settings = Settings(translation_enabled=False)
    try:
        pipeline.enqueue("output", b"first", settings, "key")
        qtbot.waitUntil(started.is_set)
        settings.translation_enabled = True
        pipeline.enqueue("output", b"second", settings, "key")
        settings.translation_enabled = False
        pipeline.enqueue("output", b"third", settings, "key")
        settings.translation_enabled = True
        settings.target_language = "French"
        settings.translation_reasoning = "high"
        pipeline.enqueue("output", b"fourth", settings, "key")
        release.set()
        qtbot.waitUntil(lambda: len(completed) == 4)
        assert sources == [("output", "はし", index) for index in range(1, 5)]
        assert [(mode, segment_id) for mode, segment_id, _ in translated] == [
            ("output", 2), ("output", 4)
        ]
        assert calls == [("はし", "English", "medium"), ("はし", "French", "high")]
        assert translated[0][2].translation == "English result"
        assert translated[1][2].translation == "French result"
    finally:
        release.set()


def test_aborted_translation_id_is_not_reused_by_new_identical_speech(
    pipeline, qtbot, monkeypatch
):
    started, release = threading.Event(), threading.Event()
    count = 0

    class Service:
        def __init__(self, key, **kwargs):
            pass

        def transcribe(self, audio, *args):
            return "こんにちは"

        def translate(self, text, *args):
            nonlocal count
            count += 1
            if count == 1:
                started.set()
                assert release.wait(2)
            return TranslationResult("Hello", "Konnichiwa", "hello")

        def close(self):
            pass

    monkeypatch.setattr("lang_handler.pipeline.OpenAIService", Service)
    sources, translated, completed = [], [], []
    pipeline.transcript.connect(lambda *args: sources.append(args))
    pipeline.translation.connect(lambda *args: translated.append(args))
    pipeline.completed.connect(lambda *args: completed.append(args))
    try:
        pipeline.enqueue("output", b"old", Settings(), "key")
        qtbot.waitUntil(started.is_set)
        pipeline.abort("output")
        pipeline.enqueue("output", b"new", Settings(), "key")
        qtbot.waitUntil(lambda: len(sources) == 2)
        assert sources[0][2] != sources[1][2]
        release.set()
        qtbot.waitUntil(lambda: len(completed) == 2)
        assert len(translated) == 1
        assert translated[0][1] == sources[1][2]
        assert completed[0][2] == ""
        assert completed[1][2].translation == "Hello"
    finally:
        release.set()
