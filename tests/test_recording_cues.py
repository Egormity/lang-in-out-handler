"""Recording cues follow real capture transitions, not repeated button requests."""

import io
import struct
import wave

from PySide6.QtCore import QObject, Signal
from PySide6.QtMultimedia import QSoundEffect

from lang_handler.recording_cues import RecordingCues, cue_wav


class FakeEffect(QObject):
    statusChanged = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        self.state = QSoundEffect.Status.Ready
        self.plays = 0
        self.stops = 0

    def setLoopCount(self, count):
        self.loops = count

    def setVolume(self, volume):
        self.volume = volume

    def setSource(self, source):
        self.source = source

    def status(self):
        return self.state

    def play(self):
        self.plays += 1

    def stop(self):
        self.stops += 1


def test_generated_cues_are_short_distinct_and_faded():
    assert cue_wav(True) != cue_wav(False)
    for starting in (True, False):
        with wave.open(io.BytesIO(cue_wav(starting))) as audio:
            assert audio.getnchannels() == 1
            assert audio.getsampwidth() == 2
            assert audio.getnframes() / audio.getframerate() == 0.12
            frames = audio.readframes(audio.getnframes())
        samples = struct.unpack(f"<{len(frames) // 2}h", frames)
        assert samples[0] == samples[-1] == 0
        assert 5_000 < max(samples) < 8_000


def test_cues_only_sound_once_per_successful_recording(qapp):
    cues = RecordingCues(effect_factory=FakeEffect)
    try:
        start, stop = cues.effects["start"], cues.effects["stop"]
        cues.recording_stopped()  # Failed starts still emit a capture-stopped event.
        assert stop.plays == 0
        cues.recording_started()
        cues.recording_started()
        assert start.plays == 1
        cues.recording_stopped()
        cues.recording_stopped()
        assert stop.plays == 1
        cues.recording_started()
        cues.recording_stopped()
        assert (start.plays, stop.plays) == (2, 2)
    finally:
        cues.close()


def test_delayed_load_does_not_play_a_stale_start_cue(qapp):
    cues = RecordingCues(effect_factory=FakeEffect)
    try:
        start, stop = cues.effects["start"], cues.effects["stop"]
        start.state = stop.state = QSoundEffect.Status.Loading
        cues.recording_started()
        cues.recording_stopped()
        start.state = QSoundEffect.Status.Ready
        start.statusChanged.emit()
        assert start.plays == 0
        stop.state = QSoundEffect.Status.Ready
        stop.statusChanged.emit()
        stop.statusChanged.emit()
        assert stop.plays == 1
    finally:
        cues.close()


def test_audio_unavailable_and_shutdown_do_not_block_recording(qapp):
    cues = RecordingCues(effect_factory=FakeEffect)
    start, stop = cues.effects["start"], cues.effects["stop"]
    start.state = stop.state = QSoundEffect.Status.Error
    cues.recording_started()
    cues.recording_stopped()
    assert (start.plays, stop.plays) == (0, 0)
    cues.close()
    start.state = QSoundEffect.Status.Ready
    cues.recording_started()
    start.statusChanged.emit()
    assert start.plays == 0
