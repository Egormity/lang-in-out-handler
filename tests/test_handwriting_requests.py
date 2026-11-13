"""Repeated sends reuse active recognition without preventing deliberate retries."""

import threading

from test_handwriting_workflow import install_service

pytest_plugins = ("test_handwriting_workflow",)


def test_repeated_active_snapshot_uses_one_request_even_after_unrelated_setting_change(
    workflow, qtbot, monkeypatch
):
    started, release = threading.Event(), threading.Event()
    calls = []

    def recognize(png):
        calls.append(png)
        started.set()
        assert release.wait(3)
        return ["recognized"]

    install_service(monkeypatch, recognize)
    try:
        workflow.recognize(b"same canvas", 1)
        qtbot.waitUntil(started.is_set)
        workflow.recognize(b"same canvas", 1)
        workflow.c.settings.font_size += 1
        workflow.recognize(b"same canvas", 1)
        assert workflow.pending is None
        release.set()
        qtbot.waitUntil(lambda: workflow.job is None)
        assert calls == [b"same canvas"]
        assert workflow.c.window.results == [(["recognized"], 1)]
        assert len(workflow.c.history) == 1
        assert workflow.c.statuses == []
    finally:
        release.set()


def test_stale_or_empty_snapshot_does_not_start_authentication_or_recognition(workflow, monkeypatch):
    def unexpected_key_request():
        raise AssertionError("Stale drawing should not need an API key")

    monkeypatch.setattr(workflow.c, "require_key", unexpected_key_request)
    workflow.recognize(b"stale", 0)
    workflow.recognize(b"", 1)
    assert workflow.job is workflow.pending is None


def test_completed_recognition_can_be_manually_retried_without_editing(workflow, qtbot, monkeypatch):
    calls = []

    def recognize(png):
        calls.append(png)
        return [f"guess {len(calls)}"]

    install_service(monkeypatch, recognize)
    workflow.recognize(b"canvas", 1)
    qtbot.waitUntil(lambda: workflow.job is None)
    workflow.recognize(b"canvas", 1)
    qtbot.waitUntil(lambda: workflow.job is None)
    assert calls == [b"canvas", b"canvas"]
    assert workflow.c.window.results[-1] == (["guess 2"], 1)


def test_changed_recognition_language_queues_fresh_request_for_same_canvas(
    workflow, qtbot, monkeypatch
):
    started, release = threading.Event(), threading.Event()
    calls = []

    class Service:
        def __init__(self, key, **kwargs):
            pass

        def recognize_handwriting(self, png, *args, language, **kwargs):
            calls.append(language)
            if len(calls) == 1:
                started.set()
                assert release.wait(3)
            return [language]

        def close(self):
            pass

    monkeypatch.setattr("lang_handler.handwriting.OpenAIService", Service)
    try:
        workflow.c.settings.drawing_language = "en"
        workflow.recognize(b"same canvas", 1)
        qtbot.waitUntil(started.is_set)
        workflow.c.settings.drawing_language = "ja"
        workflow.recognize(b"same canvas", 1)
        assert workflow.pending is not None
        release.set()
        qtbot.waitUntil(lambda: workflow.job is None)
        assert calls == ["en", "ja"]
        assert workflow.c.window.results[-1] == (["ja"], 1)
    finally:
        release.set()
