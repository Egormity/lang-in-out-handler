"""Clearing captions invalidates in-flight import content, not the import itself."""

import threading
from dataclasses import replace

import pytest
from test_caption_source_context import Google, audible
from test_controller import FakeService

from lang_handler.audio_windows import duration_seconds
from lang_handler.errors import ServiceError
from lang_handler.file_transcription import transcribe_file_once

pytest_plugins = ("test_controller",)


@pytest.mark.parametrize("phase", ["source", "source_revision", "translation"])
@pytest.mark.parametrize("stale_error", [False, True])
def test_clear_import_discards_old_epoch_and_next_chunk_has_fresh_context(
    controller, qtbot, monkeypatch, phase, stale_error,
):
    c = controller
    c.save_settings(replace(c.settings, output_context_seconds=20,
                            translation_provider="google", translation_enabled=True))
    started, release = threading.Event(), threading.Event()
    recognized, translated, errors = [], [], []
    texts = (["first", "obsolete revision", "fresh"] if phase == "source_revision"
             else ["obsolete", "fresh"])

    class Recognition(FakeService):
        def transcribe(self, audio, *args, context=""):
            index = len(recognized)
            recognized.append((duration_seconds(audio), context))
            if ((phase == "source" and index == 0)
                    or (phase == "source_revision" and index == 1)):
                started.set()
                assert release.wait(4)
                if stale_error:
                    raise ServiceError("obsolete recognition failed")
            return texts[index]

    class Translation(Google):
        def revise_translation(self, segments, target):
            translated.append(list(segments))
            if phase == "translation" and len(translated) == 1:
                started.set()
                assert release.wait(4)
                if stale_error:
                    raise ServiceError("obsolete translation failed")
            return super().revise_translation(segments, target)

    monkeypatch.setattr("lang_handler.file_import.OpenAIService", Recognition)
    monkeypatch.setattr("lang_handler.file_import.GoogleService", Translation)
    monkeypatch.setattr("lang_handler.file_import.audio_file_chunks",
                        lambda *args: iter([audible()] * len(texts)))
    monkeypatch.setattr(c, "fail", errors.append)
    try:
        c.window.file_requested.emit("output", "synthetic.wav", True)
        qtbot.waitUntil(started.is_set)
        if phase != "source":
            qtbot.waitUntil(lambda: len(c.store.list_history_segments()) == 1)
        c.window.pages["output"].clear_button.click()
        release.set()
        qtbot.waitUntil(lambda: not c.workflows.imports)
        assert recognized[-1] == (5, "")
        assert [text for _, text in translated[-1]] == ["fresh"]
        assert c.window.pages["output"].results.toPlainText() == "fresh"
        assert c.overlay.transcript.toPlainText() == "fresh"
        assert c.window.pages["output"].translations.toPlainText() == "translated fresh"
        assert c.overlay.translation.toPlainText() == "translated fresh"
        rows = c.store.list_history_segments()
        expected = {"fresh"} if phase == "source" else {texts[0], "fresh"}
        assert {row["source_text"] for row in rows} == expected
        if phase == "translation":
            original = next(row for row in rows if row["source_text"] == "obsolete")
            assert original["translated_text"] == ""
        assert not errors
    finally:
        release.set()


@pytest.mark.parametrize("stale_error", [False, True])
def test_clear_during_only_one_shot_result_does_not_report_false_no_speech(
    controller, qtbot, monkeypatch, stale_error,
):
    c = controller
    started, release = threading.Event(), threading.Event()
    errors, statuses = [], []

    class Recognition(FakeService):
        def transcribe(self, audio, *args, **kwargs):
            started.set()
            assert release.wait(4)
            if stale_error:
                raise ServiceError("obsolete recognition failed")
            return "recognized before clear"

    monkeypatch.setattr("lang_handler.file_import.OpenAIService", Recognition)
    monkeypatch.setattr("lang_handler.file_import.transcribe_file_once", transcribe_file_once)
    monkeypatch.setattr("lang_handler.file_import.audio_file_chunks", lambda *args: iter([audible()]))
    monkeypatch.setattr(c, "fail", errors.append)
    monkeypatch.setattr(c, "status", statuses.append)
    try:
        c.window.file_requested.emit("output", "synthetic.wav", False)
        qtbot.waitUntil(started.is_set)
        c.clear_captions()
        release.set()
        qtbot.waitUntil(lambda: not c.workflows.imports)
        assert c.window.pages["output"].results.toPlainText() == ""
        assert c.overlay.transcript.toPlainText() == ""
        assert c.store.list_history() == []
        assert not errors
        assert "File transcription complete." in statuses
    finally:
        release.set()


def test_clear_captions_does_not_discard_dictation_file_result(controller, qtbot, monkeypatch):
    c = controller
    started, release = threading.Event(), threading.Event()

    class Recognition(FakeService):
        def transcribe(self, audio, *args, **kwargs):
            started.set()
            assert release.wait(4)
            return "dictation remains"

    monkeypatch.setattr("lang_handler.file_import.OpenAIService", Recognition)
    monkeypatch.setattr("lang_handler.file_import.audio_file_chunks", lambda *args: iter([audible()]))
    try:
        c.window.file_requested.emit("input", "synthetic.wav", True)
        qtbot.waitUntil(started.is_set)
        c.clear_captions()
        release.set()
        qtbot.waitUntil(lambda: not c.workflows.imports)
        assert c.window.pages["input"].results.toPlainText() == "dictation remains"
        assert c.store.list_history()[0]["source_text"] == "dictation remains"
    finally:
        release.set()
