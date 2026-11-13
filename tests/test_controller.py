"""Run all desktop workflows with real widgets/SQLite and fake audio/network."""

import threading
from pathlib import Path

import pytest
from PySide6.QtCore import QObject, QThread, Signal

from lang_handler.controller import Controller
from lang_handler.errors import ServiceError
from lang_handler.results import CaptionRevision, TranslationResult
from lang_handler.settings import Settings
from lang_handler.storage import Store
from lang_handler.tts_api import pcm_to_wav
from lang_handler.ui.main_window import MainWindow
from lang_handler.ui.overlay import CaptionOverlay


class FakeCapture(QObject):
    chunk = Signal(bytes)
    error = Signal(str)
    stopped = Signal()
    level = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_running = False
        self.source = None

    def start(self, source, chunked, chunk_seconds):
        self.source = source
        self.is_running = True

    def stop(self):
        self.is_running = False
        self.stopped.emit()

    def wait(self):
        pass


class FakeCredentials:
    backend_label = "Test credentials"

    def get(self):
        return "test-key"


class FakeShortcuts:
    def apply(self, shortcuts, command):
        return "Shortcuts configured."


class FakeService:
    def __init__(self, key, **kwargs):
        pass

    def transcribe(self, audio, *args):
        return audio.decode()

    def translate(self, text, *args):
        return TranslationResult("translation: " + text, "source reading", "target reading")

    def revise_captions(self, segments, *args):
        return [CaptionRevision(segment_id, text, self.translate(text, *args))
                for segment_id, text in segments]

    def synthesize(self, text, *args):
        return pcm_to_wav(b"\x00\x00" * 100)

    def close(self):
        pass


class FakePlayer:
    returncode = 0

    def poll(self):
        return 0

    def terminate(self):
        pass


@pytest.fixture
def controller(qapp, qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr("lang_handler.controller.AudioCapture", FakeCapture)
    monkeypatch.setattr("lang_handler.controller.GlobalShortcuts", FakeShortcuts)
    monkeypatch.setattr("lang_handler.dictation.deliver_transcript", lambda *args, **kwargs: "Copied.")
    monkeypatch.setattr("lang_handler.pipeline.OpenAIService", FakeService)
    monkeypatch.setattr("lang_handler.workflows.OpenAIService", FakeService)
    monkeypatch.setattr("lang_handler.file_import.OpenAIService", FakeService)
    monkeypatch.setattr("lang_handler.workflows.play_audio", lambda path: FakePlayer())
    store = Store(tmp_path)
    settings = Settings(input_delivery="copy")
    store.save_settings(settings)
    window = MainWindow(settings, api_key_present=True)
    overlay = CaptionOverlay(settings)
    qtbot.addWidget(window)
    qtbot.addWidget(overlay)
    # Guard real widget updates rather than substituting a dummy GUI.
    for widget, methods in (
        (window, ("append_result", "set_translation", "set_speech", "set_history", "set_status")),
        (overlay, ("append_caption", "set_status")),
    ):
        for name in methods:
            method = getattr(widget, name)

            def checked(*args, _method=method, **kwargs):
                assert QThread.currentThread() == qapp.thread()
                return _method(*args, **kwargs)

            monkeypatch.setattr(widget, name, checked)
    controller = Controller(window, overlay, store, FakeCredentials())
    yield controller
    controller.shutdown()
    assert controller.jobs.pool.waitForDone(4000)
    qapp.processEvents()
    store.close()


def test_all_modes_reach_widgets_and_persistent_history(controller, qtbot):
    c = controller
    c.window.capture_requested.emit("input", False)
    assert c.captures["input"].source == ""
    c.captures["input"].chunk.emit(b"microphone words")
    c.window.stop_requested.emit("input")
    qtbot.waitUntil(lambda: len(c.store.list_history()) == 1)

    c.window.capture_requested.emit("output", True)
    assert c.captures["output"].source == "@DEFAULT_MONITOR@"
    c.overlay.hide()
    assert c.captures["output"].is_running
    c.captures["output"].chunk.emit(b"speaker words")
    c.window.stop_requested.emit("output")
    qtbot.waitUntil(lambda: len(c.store.list_history()) == 2)
    qtbot.waitUntil(lambda: not c.pipeline_busy("output"))

    c.window.translate_requested.emit("text words")
    qtbot.waitUntil(lambda: len(c.store.list_history()) == 3)
    c.window.speech_requested.emit("read aloud")
    qtbot.waitUntil(lambda: len(c.store.list_history()) == 4)
    rows = {row["mode"]: row for row in c.store.list_history()}
    assert rows["input"]["source_text"] == "microphone words"
    assert rows["output"]["translated_text"] == "translation: speaker words"
    assert rows["translate"]["translated_text"] == "translation: text words"
    assert rows["tts"]["source_text"] == "read aloud"
    assert len(c.workflows.audio_files) == 1
    assert c.workflows.audio_files[0].read_bytes().startswith(b"RIFF")
    reopened = Store(c.store.data_dir)
    assert {row["mode"] for row in reopened.list_history()} == {
        "input",
        "output",
        "translate",
        "tts",
    }
    reopened.close()


def test_file_import_keeps_each_transcript_paired_with_translation(controller, qtbot, monkeypatch):
    monkeypatch.setattr(
        "lang_handler.file_import.audio_file_chunks", lambda *args: iter([b"first", b"second"])
    )
    controller.window.file_requested.emit("output", "test.wav", True)
    qtbot.waitUntil(lambda: len(controller.store.list_history()) == 2)
    qtbot.waitUntil(lambda: not controller.workflows.imports)
    rows = list(reversed(controller.store.list_history()))
    assert [(row["source_text"], row["translated_text"]) for row in rows] == [
        ("first", "translation: first"),
        ("second", "translation: second"),
    ]


def test_cancelled_import_cannot_finish_or_remove_replacement(controller, qtbot, monkeypatch):
    started = {name: threading.Event() for name in ("old", "new")}
    release = {name: threading.Event() for name in ("old", "new")}

    class BlockingService(FakeService):
        def transcribe(self, audio, *args):
            name = audio.decode()
            started[name].set()
            assert release[name].wait(3)
            return name

    monkeypatch.setattr("lang_handler.file_import.OpenAIService", BlockingService)
    monkeypatch.setattr(
        "lang_handler.file_import.audio_file_chunks",
        lambda path, seconds: iter([Path(path).stem.encode()]),
    )
    c = controller
    try:
        c.workflows.import_file("input", "old.wav", False)
        old_job = c.workflows.imports["input"]
        qtbot.waitUntil(started["old"].is_set)
        c.stop("input")
        c.workflows.import_file("input", "new.wav", False)
        new_job = c.workflows.imports["input"]
        qtbot.waitUntil(started["new"].is_set)
        release["old"].set()
        qtbot.waitUntil(lambda: old_job not in c.jobs.active)
        assert c.workflows.imports.get("input") is new_job
        assert c.store.list_history() == []
        release["new"].set()
        qtbot.waitUntil(lambda: len(c.store.list_history()) == 1)
        assert c.store.list_history()[0]["source_text"] == "new"
        qtbot.waitUntil(lambda: not c.workflows.imports)
    finally:
        for event in release.values():
            event.set()


def test_missing_api_key_does_not_start_microphone(controller):
    controller.key = ""
    controller.start("input", False)
    assert not controller.captures["input"].is_running
    assert controller.window.stack.currentWidget() is controller.window.pages["preferences"]


def test_import_keeps_recognized_source_when_translation_fails(controller, qtbot, monkeypatch):
    class FailingTranslation(FakeService):
        def translate(self, text, *args):
            raise ServiceError("OpenAI API credits are exhausted.")

    monkeypatch.setattr("lang_handler.file_import.OpenAIService", FailingTranslation)
    monkeypatch.setattr(
        "lang_handler.file_import.audio_file_chunks", lambda *args: iter([b"recognized words"])
    )
    controller.workflows.import_file("output", "test.wav", False)
    qtbot.waitUntil(lambda: not controller.workflows.imports)
    rows = controller.store.list_history()
    assert len(rows) == 1
    assert rows[0]["source_text"] == "recognized words"
    assert rows[0]["translated_text"] == ""


def test_replay_and_stop_control_the_same_player_without_new_api_request(
    controller, qtbot, monkeypatch
):
    players = []

    class Player:
        returncode = None

        def poll(self):
            return self.returncode

        def terminate(self):
            self.returncode = -15

    def play(path):
        player = Player()
        players.append(player)
        return player

    monkeypatch.setattr("lang_handler.workflows.play_audio", play)
    c = controller
    c.workflows.speak("read aloud")
    qtbot.waitUntil(lambda: len(players) == 1)
    qtbot.waitUntil(lambda: c.workflows.speech_job is None)
    c.workflows.replay(c.workflows.audio_files[0])
    assert players[0].returncode == -15
    assert c.workflows.player is players[1]
    assert c.workflows.playback_timer.isActive()
    c.workflows.stop_speech()
    assert players[1].returncode == -15
    assert c.workflows.player is None
    assert not c.workflows.playback_timer.isActive()
    assert len(c.store.list_history()) == 1
