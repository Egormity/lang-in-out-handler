"""Real Qt workers exercise handwriting coalescing and cancellation."""

import threading

import pytest
from PySide6.QtCore import QObject, QThread

from lang_handler.handwriting import Handwriting
from lang_handler.jobs import Jobs
from lang_handler.settings import Settings


class CanvasWindow(QObject):
    def __init__(self, ui_thread):
        super().__init__()
        self.ui_thread = ui_thread
        self.revision = 1
        self.results = []
        self.busy = False

    def drawing_revision(self):
        assert QThread.currentThread() == self.ui_thread
        return self.revision

    def set_drawing_busy(self, busy):
        assert QThread.currentThread() == self.ui_thread
        self.busy = busy

    def set_drawing_result(self, text, revision):
        assert QThread.currentThread() == self.ui_thread
        self.results.append((text, revision))


class CanvasController(QObject):
    def __init__(self, qapp):
        super().__init__()
        self.window = CanvasWindow(qapp.thread())
        self.settings = Settings(drawing_provider="openai")
        self.jobs = Jobs(self)
        self.history = []
        self.statuses = []
        self.errors = []

    def require_key(self):
        return "test-key"

    def remember(self, *record):
        assert QThread.currentThread() == self.window.ui_thread
        self.history.append(record)

    def status(self, message):
        self.statuses.append(message)

    def fail(self, message):
        self.errors.append(message)


@pytest.fixture
def workflow(qapp):
    controller = CanvasController(qapp)
    handwriting = Handwriting(controller)
    yield handwriting
    handwriting.cancel()
    controller.jobs.cancel_all()
    assert controller.jobs.pool.waitForDone(4000)
    qapp.processEvents()


def install_service(monkeypatch, work):
    class Service:
        def __init__(self, key, **kwargs):
            pass

        def recognize_handwriting(self, png, model, instructions, **kwargs):
            return work(png)

        def close(self):
            pass

    monkeypatch.setattr("lang_handler.handwriting.OpenAIService", Service)


def test_changed_revision_discards_stale_recognition(workflow, qtbot, qapp, monkeypatch):
    started, release = threading.Event(), threading.Event()
    workers = []

    def recognize(png):
        workers.append(QThread.currentThread())
        started.set()
        assert release.wait(2)
        return ["old writing"]

    install_service(monkeypatch, recognize)
    try:
        workflow.recognize(b"old image", 1)
        qtbot.waitUntil(started.is_set)
        workflow.c.window.revision = 2
        release.set()
        qtbot.waitUntil(lambda: workflow.job is None)
        assert workflow.c.window.results == []
        assert workflow.c.history == []
        assert all(thread != qapp.thread() for thread in workers)
    finally:
        release.set()


def test_fast_drawing_keeps_only_one_active_and_latest_pending_snapshot(
    workflow, qtbot, monkeypatch
):
    started = {name: threading.Event() for name in (b"first", b"latest")}
    release = {name: threading.Event() for name in started}
    calls = []

    def recognize(png):
        calls.append(png)
        started[png].set()
        assert release[png].wait(3)
        return [png.decode() + " recognized", "alternative"]

    install_service(monkeypatch, recognize)
    try:
        workflow.recognize(b"first", 1)
        qtbot.waitUntil(started[b"first"].is_set)
        workflow.c.window.revision = 2
        workflow.recognize(b"obsolete pending", 2)
        workflow.c.window.revision = 3
        workflow.recognize(b"latest", 3)
        assert calls == [b"first"]
        assert len(workflow.c.jobs.active) == 1
        release[b"first"].set()
        qtbot.waitUntil(started[b"latest"].is_set)
        assert workflow.c.window.results == []
        assert workflow.c.window.busy
        release[b"latest"].set()
        qtbot.waitUntil(lambda: workflow.job is None)
        assert calls == [b"first", b"latest"]
        assert workflow.c.window.results == [(["latest recognized", "alternative"], 3)]
        assert len(workflow.c.history) == 2
        assert workflow.c.history[0][:2] == ("drawing", "latest recognized")
    finally:
        for event in release.values():
            event.set()


@pytest.mark.parametrize("clear_canvas", [False, True])
def test_manual_mode_or_clear_cancel_active_and_pending_work(
    workflow, qtbot, monkeypatch, clear_canvas
):
    started, release = threading.Event(), threading.Event()
    calls = []

    def recognize(png):
        calls.append(png)
        started.set()
        assert release.wait(2)
        return ["canceled writing"]

    install_service(monkeypatch, recognize)
    try:
        workflow.recognize(b"active", 1)
        qtbot.waitUntil(started.is_set)
        workflow.c.window.revision = 2
        workflow.recognize(b"pending", 2)
        if clear_canvas:
            workflow.c.window.revision = 3
        workflow.cancel()
        release.set()
        qtbot.waitUntil(lambda: workflow.job is None)
        assert workflow.pending is None
        assert calls == [b"active"]
        assert workflow.c.window.results == []
        assert workflow.c.history == []
        assert not workflow.c.window.busy
    finally:
        release.set()


def test_cancel_after_worker_emits_still_prevents_ui_and_history_updates(
    workflow, qapp, monkeypatch
):
    install_service(monkeypatch, lambda png: ["already queued result"])
    workflow.recognize(b"canvas", 1)
    # Avoid processing Qt events until the worker has emitted its result.
    assert workflow.c.jobs.pool.waitForDone(2000)
    workflow.cancel()
    qapp.processEvents()
    assert workflow.job is None
    assert workflow.c.window.results == []
    assert workflow.c.history == []


def test_cancel_then_manual_send_can_restart_with_same_canvas_revision(
    workflow, qtbot, monkeypatch
):
    started, release = threading.Event(), threading.Event()
    calls = []

    def recognize(png):
        calls.append(png)
        if len(calls) == 1:
            started.set()
            assert release.wait(2)
            return ["canceled"]
        return ["manual result"]

    install_service(monkeypatch, recognize)
    try:
        workflow.recognize(b"canvas", 1)
        qtbot.waitUntil(started.is_set)
        workflow.cancel()
        workflow.recognize(b"canvas", 1)
        release.set()
        qtbot.waitUntil(lambda: len(workflow.c.history) == 1)
        qtbot.waitUntil(lambda: workflow.job is None)
        assert calls == [b"canvas", b"canvas"]
        assert workflow.c.window.results == [(["manual result"], 1)]
        assert workflow.c.history[0][1] == "manual result"
    finally:
        release.set()


def test_api_failure_for_outdated_drawing_does_not_replace_current_status(
    workflow, qtbot, monkeypatch
):
    started, release = threading.Event(), threading.Event()

    def recognize(png):
        started.set()
        assert release.wait(2)
        raise RuntimeError("outdated failure")

    install_service(monkeypatch, recognize)
    try:
        workflow.recognize(b"old canvas", 1)
        qtbot.waitUntil(started.is_set)
        workflow.c.window.revision = 2
        release.set()
        qtbot.waitUntil(lambda: workflow.job is None)
        assert workflow.c.errors == []
        assert workflow.c.history == []
    finally:
        release.set()
