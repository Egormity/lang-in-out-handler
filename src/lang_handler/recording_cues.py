"""Short local sounds confirm when microphone capture starts and ends."""

import io
import math
import struct
import tempfile
import wave
from pathlib import Path

from PySide6.QtCore import QObject, QUrl
from PySide6.QtMultimedia import QSoundEffect


def cue_wav(starting: bool) -> bytes:
    """Generate a soft ascending/descending cue, including fades to avoid clicks."""
    sample_rate = 24_000
    duration = 0.12
    frames = round(sample_rate * duration)
    low, high = (660, 990) if starting else (660, 440)
    samples = []
    for index in range(frames):
        time = index / sample_rate
        phase = 2 * math.pi * (low * time + (high - low) * time * time / (2 * duration))
        envelope = math.sin(math.pi * index / (frames - 1)) ** 2
        samples.append(round(7_000 * envelope * math.sin(phase)))
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes(struct.pack(f"<{frames}h", *samples))
    return output.getvalue()


class RecordingCues(QObject):
    """Connect to successful microphone capture events, never button clicks."""

    def __init__(self, parent=None, *, effect_factory=QSoundEffect):
        super().__init__(parent)
        self._directory = tempfile.TemporaryDirectory(prefix="lang-in-out-recording-cues-")
        self._active = False
        self._closed = False
        self._pending = None
        self.effects = {}
        for name in ("start", "stop"):
            path = Path(self._directory.name) / f"{name}.wav"
            path.write_bytes(cue_wav(name == "start"))
            effect = effect_factory(self)
            effect.setLoopCount(1)
            effect.setVolume(0.45)
            effect.statusChanged.connect(lambda selected=name: self._loaded(selected))
            self.effects[name] = effect
            effect.setSource(QUrl.fromLocalFile(str(path)))

    def recording_started(self):
        if self._closed or self._active:
            return
        self._active = True
        self._play("start")

    def recording_stopped(self):
        if self._closed or not self._active:
            return
        self._active = False
        self._play("stop")

    def _play(self, name):
        self._pending = name
        for other, effect in self.effects.items():
            if other != name:
                effect.stop()
        self._loaded(name)

    def _loaded(self, name):
        if self._closed or self._pending != name:
            return
        effect = self.effects[name]
        if effect.status() == QSoundEffect.Status.Ready:
            self._pending = None
            effect.play()
        elif effect.status() == QSoundEffect.Status.Error:
            # An unavailable audio output must never block dictation.
            self._pending = None

    def close(self):
        self._closed = True
        self._active = False
        self._pending = None
        for effect in self.effects.values():
            effect.stop()
            effect.setSource(QUrl())
        self._directory.cleanup()
