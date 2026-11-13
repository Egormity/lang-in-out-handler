"""Generated speech belongs to the originating text and survives local replay."""

import threading
from pathlib import Path

from shiboken6 import isValid
from test_controller import FakeService

from lang_handler.ui.inline_audio import InlineAudio

pytest_plugins = ("test_controller",)


def delayed_service(monkeypatch):
    started, release = threading.Event(), threading.Event()

    class Service(FakeService):
        def synthesize(self, text, *args):
            started.set()
            assert release.wait(3)
            return super().synthesize(text)

    monkeypatch.setattr("lang_handler.workflows.OpenAIService", Service)
    return started, release


def test_edited_text_discards_inflight_speech(controller, qtbot, monkeypatch):
    started, release = delayed_service(monkeypatch)
    pane = controller.window.pages["translate"].source
    pane.text.setPlainText("original words")
    pane.speak.click()
    try:
        qtbot.waitUntil(started.is_set)
        pane.text.setPlainText("revised words")
        release.set()
        qtbot.waitUntil(lambda: controller.workflows.speech_job is None)
        assert pane.audio.path == ""
        assert pane.speak.isEnabled()
        assert controller.workflows.audio_files == []
        assert controller.store.list_history() == []
    finally:
        release.set()


def test_deleted_candidate_does_not_receive_inflight_speech(controller, qtbot, monkeypatch):
    started, release = delayed_service(monkeypatch)
    candidates = controller.window.pages["drawing"].result
    candidates.set_items(["old candidate"])
    origin = candidates.rows[0].audio
    origin.speak.click()
    try:
        qtbot.waitUntil(started.is_set)
        candidates.set_items(["replacement candidate"])
        qtbot.waitUntil(lambda: not isValid(origin))
        release.set()
        qtbot.waitUntil(lambda: controller.workflows.speech_job is None)
        assert candidates.rows[0].audio.path == ""
        assert controller.workflows.audio_files == []
        assert controller.store.list_history() == []
    finally:
        release.set()


def test_stop_before_queued_result_is_delivered_leaves_no_player(controller, qapp):
    pane = controller.window.pages["translate"].source
    pane.text.setPlainText("queued words")
    pane.speak.click()
    assert controller.jobs.pool.waitForDone(2000)
    controller.workflows.stop_speech()
    qapp.processEvents()
    assert controller.workflows.speech_job is None
    assert pane.audio.path == ""
    assert pane.speak.isEnabled()
    assert controller.workflows.audio_files == []


def test_replay_and_speed_use_cached_audio_without_more_api_requests(
    controller, qtbot, monkeypatch
):
    calls = []

    class Service(FakeService):
        def synthesize(self, text, *args):
            calls.append(text)
            return super().synthesize(text)

    monkeypatch.setattr("lang_handler.workflows.OpenAIService", Service)
    original_play = InlineAudio.play

    def play_muted(control):
        control.audio_output.setMuted(True)
        original_play(control)

    monkeypatch.setattr(InlineAudio, "play", play_muted)
    pane = controller.window.pages["translate"].source
    pane.text.setPlainText("cached words")
    pane.speak.click()
    qtbot.waitUntil(lambda: controller.workflows.speech_job is None)
    assert Path(pane.audio.path).is_file()
    assert pane.audio.controls.isHidden() is False
    pane.audio.stop()
    pane.audio.speed.setCurrentIndex(pane.audio.speed.findData(0.75))
    pane.audio.play_button.click()
    qtbot.wait(20)
    pane.audio.stop()
    pane.audio.play_button.click()
    assert pane.audio.player.playbackRate() == 0.75
    assert calls == ["cached words"]
    assert len(controller.workflows.audio_files) == 1
    assert controller.workflows.player is None
