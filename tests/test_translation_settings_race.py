"""Changing providers or target languages never applies an obsolete caption response."""

import threading
from dataclasses import replace

import pytest
from test_controller import FakeService

from lang_handler.results import CaptionRevision, TranslationResult

pytest_plugins = ("test_controller",)


def revisions(segments, text="obsolete translation"):
    return [CaptionRevision(segment_id, source, TranslationResult(text))
            for segment_id, source in segments]


@pytest.mark.parametrize("change", [
    {"translation_provider": "openai"}, {"target_language": "Russian"},
])
def test_live_translation_switch_drops_pending_response_without_another_chunk(
    controller, qtbot, monkeypatch, change,
):
    started, release = threading.Event(), threading.Event()

    class Google:
        def __init__(self, **kwargs):
            pass

        def revise_translation(self, segments, target):
            started.set()
            assert release.wait(3)
            return revisions(segments)

        def close(self):
            pass

    monkeypatch.setattr("lang_handler.pipeline.GoogleService", Google)
    c = controller
    c.save_settings(replace(c.settings, translation_provider="google"))
    try:
        c.pipeline.enqueue("output", b"original words", c.settings, c.key)
        qtbot.waitUntil(started.is_set)
        qtbot.waitUntil(lambda: len(c.store.list_history()) == 1)
        original = c.store.list_history()[0]
        c.save_settings(replace(c.settings, **change))
        release.set()
        qtbot.waitUntil(lambda: not c.pipeline_busy("output"))
        saved = c.store.list_history()[0]
        assert saved["id"] == original["id"]
        assert saved["source_text"] == "original words"
        assert saved["translated_text"] == ""
        assert c.window.pages["output"].translations.toPlainText() == ""
        assert c.overlay.translation.toPlainText() == ""
        assert c.overlay.transcript.toPlainText() == "original words"
    finally:
        release.set()


@pytest.mark.parametrize("change", [
    {"translation_provider": "openai"}, {"target_language": "Russian"},
])
def test_import_preserves_all_sources_but_discards_old_translation_after_settings_change(
    controller, qtbot, monkeypatch, change,
):
    started, release = threading.Event(), threading.Event()
    calls = []

    class Google:
        def __init__(self, **kwargs):
            pass

        def revise_translation(self, segments, target):
            calls.append((list(segments), target))
            started.set()
            assert release.wait(3)
            return revisions(segments)

        def close(self):
            pass

    monkeypatch.setattr("lang_handler.file_import.GoogleService", Google)
    monkeypatch.setattr("lang_handler.file_import.audio_file_chunks", lambda *args: iter([b"first", b"second"]))
    c = controller
    c.save_settings(replace(c.settings, translation_provider="google"))
    try:
        c.workflows.import_file("output", "synthetic.wav", True)
        qtbot.waitUntil(started.is_set)
        c.save_settings(replace(c.settings, **change))
        release.set()
        qtbot.waitUntil(lambda: not c.workflows.imports)
        segments = list(reversed(c.store.list_history_segments()))
        assert [entry["source_text"] for entry in segments] == ["first", "second"]
        assert all(entry["translated_text"] == "" for entry in segments)
        assert len(calls) == 1
        assert len(c.store.list_history()) == 1
        assert c.store.list_history()[0]["source_text"] == "first second"
        assert c.overlay.transcript.toPlainText() == "first second"
        assert c.overlay.translation.toPlainText() == ""
    finally:
        release.set()


def test_pending_recognition_uses_new_translation_provider_when_it_completes(
    controller, qtbot, monkeypatch,
):
    started, release = threading.Event(), threading.Event()
    google_calls = []

    class Recognizer(FakeService):
        def transcribe(self, audio, *args):
            started.set()
            assert release.wait(3)
            return audio.decode()

        def revise_captions(self, *args):
            pytest.fail("The old OpenAI translation provider must not receive a new request")

    class Google:
        def __init__(self, **kwargs):
            pass

        def revise_translation(self, segments, target):
            google_calls.append((list(segments), target))
            return revisions(segments, "new Google translation")

        def close(self):
            pass

    monkeypatch.setattr("lang_handler.pipeline.OpenAIService", Recognizer)
    monkeypatch.setattr("lang_handler.pipeline.GoogleService", Google)
    c = controller
    try:
        c.pipeline.enqueue("output", b"original", c.settings, c.key)
        qtbot.waitUntil(started.is_set)
        c.save_settings(replace(c.settings, translation_provider="google"))
        release.set()
        qtbot.waitUntil(lambda: not c.pipeline_busy("output"))
        assert len(google_calls) == 1
        assert c.store.list_history()[0]["source_text"] == "original"
        assert c.store.list_history()[0]["translated_text"] == "new Google translation"
    finally:
        release.set()
