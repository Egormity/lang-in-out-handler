"""Capture controls follow actual recording and draining work, including silent stops."""

import threading
from dataclasses import replace

import pytest
from test_controller import FakeService

pytest_plugins = ("test_controller",)


def test_opening_idle_floating_captions_never_exposes_stop(controller, monkeypatch):
    c = controller
    original_stop = c.captures["output"].stop
    monkeypatch.setattr(c.captures["output"], "stop", lambda: pytest.fail("Idle Stop must be a no-op"))
    c.show_overlay()
    assert c.overlay.capture_state == "idle"
    assert c.overlay.start_button.isVisible()
    assert c.overlay.stop_button.isHidden()
    c.stop("output")
    assert c.overlay.capture_state == "idle"
    assert not c.overlay.status.text()
    # Restore shutdown's unconditional low-level stop cleanup.
    monkeypatch.setattr(c.captures["output"], "stop", original_stop)


@pytest.mark.parametrize("mode", ["input", "output"])
def test_repeated_start_and_silent_stop_are_idempotent(controller, monkeypatch, mode):
    c = controller
    capture = c.captures[mode]
    starts, stops = [], []
    start, stop = capture.start, capture.stop
    monkeypatch.setattr(capture, "start", lambda *args: (starts.append(args), start(*args)))
    monkeypatch.setattr(capture, "stop", lambda: (stops.append(True), stop()))
    c.start(mode, True)
    session = c.history_sessions[mode]
    c.start(mode, True)
    assert len(starts) == 1
    assert c.history_sessions[mode] == session
    c.stop(mode)
    c.stop(mode)
    assert len(stops) == 1
    assert c.capture_phases[mode] == "idle"
    assert c.window.pages[mode].start_button.isEnabled()
    assert "finishing" not in c.window.status.text().lower()
    assert c.store.list_history() == []
    if mode == "output":
        assert c.overlay.capture_state == "idle"
        assert c.overlay.stop_button.isHidden()
        assert not c.overlay.status.text()


def test_delayed_stopped_and_late_started_signals_do_not_reactivate_capture(controller, monkeypatch):
    c = controller
    capture = c.captures["output"]
    stops = []
    monkeypatch.setattr(capture, "stop", lambda: stops.append(True))
    c.start("output", True)
    c.stop("output")
    assert c.overlay.capture_state == "finishing"
    assert not c.overlay.stop_button.isEnabled()
    assert not c.window.pages["output"].start_button.isEnabled()
    capture.started.emit()
    c.start("output", True)
    c.stop("output")
    assert stops == [True]
    assert c.overlay.capture_state == "finishing"
    capture.is_running = False
    capture.stopped.emit()
    assert c.overlay.capture_state == "idle"
    assert c.overlay.start_button.isEnabled()
    assert not c.overlay.status.text()


def test_final_chunk_drains_before_start_returns_and_is_not_discarded(controller, qtbot, monkeypatch):
    c = controller
    capture = c.captures["output"]
    started, release = threading.Event(), threading.Event()

    class Slow(FakeService):
        def transcribe(self, audio, *args):
            started.set()
            assert release.wait(3)
            return audio.decode()

    monkeypatch.setattr("lang_handler.pipeline.OpenAIService", Slow)

    def stop_with_tail():
        capture.chunk.emit(b"last words")
        capture.is_running = False
        capture.stopped.emit()

    monkeypatch.setattr(capture, "stop", stop_with_tail)
    try:
        c.start("output", True)
        c.stop("output")
        qtbot.waitUntil(started.is_set)
        assert c.overlay.capture_state == "finishing"
        assert c.pipeline.pending_count("output") > 0
        assert not c.window.pages["output"].start_button.isEnabled()
        c.start("output", True)
        assert "previous recording" in c.window.status.text()
        release.set()
        qtbot.waitUntil(lambda: not c.pipeline_busy("output"))
        assert c.store.list_history()[0]["source_text"] == "last words"
        assert c.overlay.capture_state == "idle"
        assert c.overlay.start_button.isEnabled()
        assert not c.overlay.status.text()
    finally:
        release.set()


@pytest.mark.parametrize("failure", ["missing-key", "start", "runtime"])
def test_capture_failures_restore_idle_controls_and_next_start_clears_error(
    controller, monkeypatch, failure,
):
    c = controller
    capture = c.captures["output"]
    original_start = capture.start
    c.show_overlay()
    if failure == "missing-key":
        c.key = ""
    elif failure == "start":
        monkeypatch.setattr(capture, "start", lambda *args: (_ for _ in ()).throw(RuntimeError("No audio source")))
    c.start("output", True)
    if failure == "runtime":
        capture.error.emit("Audio source disconnected")
    assert c.overlay.capture_state == "idle"
    assert c.overlay.start_button.isEnabled()
    assert c.overlay.stop_button.isHidden()
    monkeypatch.setattr(capture, "start", original_start)
    c.key = "test-key"
    c.start("output", True)
    assert c.overlay.capture_state == "recording"
    assert not c.overlay.status.text()


def test_reopening_active_float_preserves_recording_and_live_language_changes(controller):
    c = controller
    c.start("output", True)
    c.overlay.hide()
    c.show_overlay()
    assert c.overlay.capture_state == "recording"
    assert c.overlay.stop_button.isVisible()
    assert c.overlay.source_language.isEnabled()
    assert c.window.pages["output"].source_language.isEnabled()
    c.overlay.source_language.setCurrentText("English")
    c.overlay.target.setCurrentText("Russian")
    assert c.settings.output_language == "en"
    assert c.settings.target_language == "Russian"
    assert c.overlay.capture_state == "recording"


def test_resetting_translation_context_keeps_finishing_until_active_job_exits(controller, qtbot, monkeypatch):
    c = controller
    started, release = threading.Event(), threading.Event()

    class Slow(FakeService):
        def revise_captions(self, *args):
            started.set()
            assert release.wait(3)
            return super().revise_captions(*args)

    monkeypatch.setattr("lang_handler.pipeline.OpenAIService", Slow)
    try:
        c.start("output", True)
        c.captures["output"].chunk.emit(b"pending")
        qtbot.waitUntil(started.is_set)
        c.stop("output")
        c.save_settings(replace(c.settings, target_language="Russian"))
        assert c.pipeline.pending_count("output") > 0
        assert c.overlay.capture_state == "finishing"
        release.set()
        qtbot.waitUntil(lambda: not c.pipeline_busy("output"))
        assert c.pipeline.pending_count("output") == 0
        assert c.overlay.capture_state == "idle"
    finally:
        release.set()


def test_cancelling_import_while_microphone_idle_does_not_enter_finishing(controller, qtbot, monkeypatch):
    c = controller
    started, release = threading.Event(), threading.Event()

    class Slow(FakeService):
        def transcribe(self, audio, *args):
            started.set()
            assert release.wait(3)
            return audio.decode()

    monkeypatch.setattr("lang_handler.file_import.OpenAIService", Slow)
    monkeypatch.setattr("lang_handler.file_import.audio_file_chunks", lambda *args: iter([b"file"]))
    stops = []
    monkeypatch.setattr(c.captures["output"], "stop", lambda: stops.append(True))
    try:
        c.workflows.import_file("output", "synthetic.wav", True)
        qtbot.waitUntil(started.is_set)
        assert c.overlay.capture_state == "recording"
        c.stop("output")
        assert not stops
        assert c.overlay.capture_state == "idle"
        assert not c.overlay.status.text()
    finally:
        release.set()
