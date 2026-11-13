"""Exercise revisable recognition through real controller, widgets and SQLite."""

import threading
from dataclasses import replace

import pytest
from test_controller import FakeService

from lang_handler.audio_windows import duration_seconds, pcm_to_wav
from lang_handler.errors import ServiceError
from lang_handler.file_transcription import transcribe_file_once
from lang_handler.results import CaptionRevision, TranslationResult
from lang_handler.text_utils import flowing_text

pytest_plugins = ("test_controller",)


def audible(seconds=5):
    return pcm_to_wav(b"\x00\x10" * (16_000 * seconds))


class Google:
    def __init__(self, **kwargs):
        pass

    def revise_translation(self, segments, target):
        combined = "translated " + flowing_text(text for _, text in segments)
        return [CaptionRevision(identifier, text, TranslationResult(combined if index == 0 else ""))
                for index, (identifier, text) in enumerate(segments)]

    def close(self):
        pass


def configure(c, monkeypatch, responses):
    calls = []
    responses = iter(responses)

    class Recognition(FakeService):
        def transcribe(self, audio, *args, context=""):
            calls.append((duration_seconds(audio), context))
            return next(responses)

    c.save_settings(replace(c.settings, output_context_seconds=20, output_chunked=True,
                            translation_provider="google", translation_enabled=True))
    monkeypatch.setattr("lang_handler.pipeline.OpenAIService", Recognition)
    monkeypatch.setattr("lang_handler.pipeline.GoogleService", Google)
    return calls


def submit(c, qtbot):
    c.captures["output"].chunk.emit(audible())
    qtbot.waitUntil(lambda: not c.pipeline_busy("output"))


def test_growing_source_replaces_one_history_row_then_carries_context_to_next(
    controller, qtbot, monkeypatch,
):
    c = controller
    texts = ["We", "We are", "We are going", "We are going home.", "Tomorrow."]
    calls = configure(c, monkeypatch, texts)
    c.start("output", True)
    first = None
    for text in texts[:4]:
        submit(c, qtbot)
        rows = c.store.list_history_segments()
        assert len(rows) == 1
        first = first or rows[0]
        assert rows[0]["id"] == first["id"]
        assert rows[0]["created_at"] == first["created_at"]
        assert rows[0]["source_text"] == text
        assert rows[0]["translated_text"] == "translated " + text
        assert c.window.pages["output"].results.toPlainText() == text
        assert c.overlay.transcript.toPlainText() == text
    assert calls == [(5, ""), (10, ""), (15, ""), (20, "")]
    submit(c, qtbot)
    assert calls[-1] == (5, texts[3])
    rows = c.store.list_history_segments()
    assert len(rows) == 2
    assert len({row["id"] for row in rows}) == 2
    expected_source = "We are going home. Tomorrow."
    expected_translation = "translated " + expected_source
    assert c.window.pages["output"].results.toPlainText() == expected_source
    assert c.overlay.transcript.toPlainText() == expected_source
    assert c.window.pages["output"].translations.toPlainText() == expected_translation
    assert c.overlay.translation.toPlainText() == expected_translation
    assert len(c.store.list_history()) == 1
    assert c.store.list_history()[0]["source_text"] == expected_source
    assert c.store.list_history()[0]["translated_text"] == expected_translation
    c.stop("output")


@pytest.mark.parametrize("old_error", [False, True])
def test_stale_translation_cannot_overwrite_revised_source_or_stop_latest_request(
    controller, qtbot, monkeypatch, old_error,
):
    c = controller
    configure(c, monkeypatch, ["old words", "corrected complete words"])
    started = [threading.Event(), threading.Event()]
    release = [threading.Event(), threading.Event()]
    contexts, errors = [], []

    class Blocked(Google):
        def revise_translation(self, segments, target):
            index = len(contexts)
            contexts.append(list(segments))
            started[index].set()
            assert release[index].wait(4)
            if index == 0 and old_error:
                raise ServiceError("obsolete request failed")
            return super().revise_translation(segments, target)

    monkeypatch.setattr("lang_handler.pipeline.GoogleService", Blocked)
    monkeypatch.setattr(c, "fail", errors.append)
    c.start("output", True)
    try:
        c.captures["output"].chunk.emit(audible())
        qtbot.waitUntil(started[0].is_set)
        first_id = c.store.list_history_segments()[0]["id"]
        c.captures["output"].chunk.emit(audible())
        qtbot.waitUntil(lambda: c.window.pages["output"].results.toPlainText()
                       == "corrected complete words")
        release[0].set()
        qtbot.waitUntil(started[1].is_set)
        assert contexts[0][0][0] == contexts[1][0][0]
        assert c.window.pages["output"].translations.toPlainText() == ""
        assert c.overlay.translation.toPlainText() == ""
        assert c.store.list_history_segments()[0]["translated_text"] == ""
        assert not errors
        assert c.captures["output"].is_running
        release[1].set()
        qtbot.waitUntil(lambda: not c.pipeline_busy("output"))
        rows = c.store.list_history_segments()
        assert len(rows) == 1 and rows[0]["id"] == first_id
        assert rows[0]["source_text"] == "corrected complete words"
        assert rows[0]["translated_text"] == "translated corrected complete words"
        assert c.overlay.translation.toPlainText() == "translated corrected complete words"
        assert not errors
    finally:
        for event in release:
            event.set()


def test_clear_during_source_recognition_does_not_restore_old_text(
    controller, qtbot, monkeypatch,
):
    c = controller
    configure(c, monkeypatch, [])
    started, release = threading.Event(), threading.Event()
    calls = []

    class Blocked(FakeService):
        def transcribe(self, audio, *args, context=""):
            calls.append((duration_seconds(audio), context))
            if len(calls) == 2:
                started.set()
                assert release.wait(4)
                return "outdated expanded source"
            return "first source" if len(calls) == 1 else "fresh source"

    monkeypatch.setattr("lang_handler.pipeline.OpenAIService", Blocked)
    c.start("output", True)
    try:
        submit(c, qtbot)
        first = c.store.list_history_segments()[0]
        c.captures["output"].chunk.emit(audible())
        qtbot.waitUntil(started.is_set)
        c.window.pages["output"].clear_button.click()
        release.set()
        qtbot.waitUntil(lambda: not c.pipeline_busy("output"))
        assert c.window.pages["output"].results.toPlainText() == ""
        assert c.overlay.transcript.toPlainText() == ""
        assert c.store.list_history_segments() == [first]
        submit(c, qtbot)
        assert calls[-1] == (5, "")
        assert c.window.pages["output"].results.toPlainText() == "fresh source"
        assert c.overlay.translation.toPlainText() == "translated fresh source"
        assert len(c.store.list_history_segments()) == 2
    finally:
        release.set()


def test_source_revision_never_recreates_deleted_history(controller, qtbot, monkeypatch):
    c = controller
    configure(c, monkeypatch, [])
    started, release = threading.Event(), threading.Event()
    responses = iter(["first", "first corrected", "first corrected again"])

    class Blocked(FakeService):
        def transcribe(self, audio, *args, context=""):
            result = next(responses)
            if result == "first corrected":
                started.set()
                assert release.wait(4)
            return result

    monkeypatch.setattr("lang_handler.pipeline.OpenAIService", Blocked)
    c.start("output", True)
    try:
        submit(c, qtbot)
        c.captures["output"].chunk.emit(audible())
        qtbot.waitUntil(started.is_set)
        c.window.history_delete_requested.emit()
        assert not c.caption_history
        assert c.store.list_history() == []
        release.set()
        qtbot.waitUntil(lambda: not c.pipeline_busy("output"))
        assert c.store.list_history() == []
        submit(c, qtbot)
        assert c.window.pages["output"].results.toPlainText() == "first corrected again"
        assert c.overlay.transcript.toPlainText() == "first corrected again"
        assert c.store.list_history_segments() == []
    finally:
        release.set()


@pytest.mark.parametrize("mode", ["input", "output"])
def test_one_shot_file_ui_route_splits_internally_but_creates_one_result(
    controller, qtbot, monkeypatch, mode,
):
    c = controller
    c.save_settings(replace(c.settings, translation_provider="google"))
    calls = []

    class Recognition(FakeService):
        def transcribe(self, audio, *args, context=""):
            calls.append((duration_seconds(audio), context))
            return "first part" if len(calls) == 1 else "second part"

    monkeypatch.setattr("lang_handler.file_import.OpenAIService", Recognition)
    monkeypatch.setattr("lang_handler.file_import.GoogleService", Google)
    monkeypatch.setattr("lang_handler.file_import.transcribe_file_once", transcribe_file_once)
    monkeypatch.setattr("lang_handler.file_import.audio_file_chunks", lambda *args: iter([audible(35)]))
    c.window.file_requested.emit(mode, "synthetic.wav", False)
    qtbot.waitUntil(lambda: not c.workflows.imports)
    assert calls == [(30, ""), (5, "first part")]
    assert c.window.pages[mode].results.toPlainText() == "first part second part"
    rows = c.store.list_history_segments()
    assert len(rows) == 1 and rows[0]["source_text"] == "first part second part"
    if mode == "output":
        assert rows[0]["translated_text"] == "translated first part second part"
        assert c.overlay.transcript.toPlainText() == "first part second part"
    assert not c.capture_errors[mode]


def test_empty_one_shot_file_reports_failure_without_success_or_history(
    controller, qtbot, monkeypatch,
):
    c = controller
    errors, statuses = [], []

    class Empty(FakeService):
        def transcribe(self, audio, *args, **kwargs):
            return "♪…"

    monkeypatch.setattr("lang_handler.file_import.OpenAIService", Empty)
    monkeypatch.setattr("lang_handler.file_import.transcribe_file_once", transcribe_file_once)
    monkeypatch.setattr("lang_handler.file_import.audio_file_chunks", lambda *args: iter([audible(35)]))
    monkeypatch.setattr(c, "fail", errors.append)
    monkeypatch.setattr(c, "status", statuses.append)
    c.window.file_requested.emit("output", "synthetic.wav", False)
    qtbot.waitUntil(lambda: not c.workflows.imports)
    assert len(errors) == 1 and "No speech could be recognized" in errors[0]
    assert c.store.list_history() == []
    assert c.window.pages["output"].results.toPlainText() == ""
    assert c.capture_errors["output"] == errors[0]
    assert not any("complete" in message.lower() for message in statuses)
