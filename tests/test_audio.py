import io
import sys
import wave
from pathlib import Path

import pytest

from lang_handler import audio
from lang_handler.audio_files import audio_file_chunks


def decoded(data):
    with wave.open(io.BytesIO(data)) as stream:
        assert stream.getnchannels() == 1
        assert stream.getsampwidth() == 2
        assert stream.getframerate() == 16000
        return stream.readframes(stream.getnframes())


def fake_command(monkeypatch, pcm):
    monkeypatch.setattr(
        audio,
        "capture_command",
        lambda source: [
            sys.executable,
            "-c",
            "import sys; sys.stdout.buffer.write(" + repr(pcm) + ")",
        ],
    )


def test_capture_emits_full_chunks_and_preserves_trailing_audio(qtbot, monkeypatch):
    # Avoid placing a large payload in argv: a subprocess generates deterministic PCM.
    monkeypatch.setattr(
        audio,
        "capture_command",
        lambda source: [
            sys.executable,
            "-c",
            "import sys; sys.stdout.buffer.write(b'\\x10\\x04' * 72000)",
        ],
    )
    capture = audio.AudioCapture()
    received = []
    capture.chunk.connect(received.append)
    with qtbot.waitSignal(capture.stopped, timeout=5000):
        capture.start(chunked=True, chunk_seconds=2)
    assert [len(decoded(data)) for data in received] == [64000, 64000, 16000]
    assert b"".join(decoded(data) for data in received) == b"\x10\x04" * 72000
    capture.wait()


def test_silent_chunks_are_consumed_without_submission(qtbot, monkeypatch):
    monkeypatch.setattr(
        audio,
        "capture_command",
        lambda source: [
            sys.executable,
            "-c",
            "import sys; sys.stdout.buffer.write(b'\\x00\\x00' * 72000)",
        ],
    )
    capture = audio.AudioCapture()
    received = []
    capture.chunk.connect(received.append)
    with qtbot.waitSignal(capture.stopped, timeout=5000):
        capture.start(chunked=True, chunk_seconds=2)
    assert received == []
    capture.wait()


def test_stop_flushes_partial_audio_and_terminates_capture(qtbot, monkeypatch):
    monkeypatch.setattr(
        audio,
        "capture_command",
        lambda source: [
            sys.executable,
            "-c",
            (
                "import sys,time; sys.stdout.buffer.write(b'\\x10\\x04'*5000); "
                "sys.stdout.buffer.flush(); time.sleep(60)"
            ),
        ],
    )
    capture = audio.AudioCapture()
    received, levels = [], []
    capture.chunk.connect(received.append)
    capture.level.connect(levels.append)
    capture.start(chunked=True, chunk_seconds=2)
    qtbot.waitUntil(lambda: bool(levels), timeout=3000)
    with qtbot.waitSignal(capture.stopped, timeout=3000):
        capture.stop()
    capture.wait()
    assert not capture.is_running
    assert b"".join(decoded(data) for data in received) == b"\x10\x04" * 5000


def test_once_recording_produces_one_complete_request(qtbot, monkeypatch):
    fake_command(monkeypatch, b"\x10\x04" * 3000)
    capture = audio.AudioCapture()
    received = []
    capture.chunk.connect(received.append)
    with qtbot.waitSignal(capture.stopped, timeout=5000):
        capture.start(chunked=False)
    assert len(received) == 1
    assert decoded(received[0]) == b"\x10\x04" * 3000
    capture.wait()


def test_monitor_uses_sink_capture_without_overriding_default(monkeypatch):
    monkeypatch.setattr(
        audio.shutil, "which", lambda name: "/usr/bin/pw-record" if name == "pw-record" else None
    )
    command = audio.capture_command("@DEFAULT_MONITOR@")
    assert "stream.capture.sink=true" in command[command.index("--properties") + 1]
    assert "--target" not in command
    command = audio.capture_command("alsa_output.speakers.monitor")
    assert command[command.index("--target") + 1] == "alsa_output.speakers"


def test_file_decoding_chunk_boundaries_and_once(tmp_path: Path):
    pcm = b"\x10\x04" * 72000
    path = tmp_path / "example.wav"
    path.write_bytes(audio.pcm_to_wav(pcm))
    chunks = list(audio_file_chunks(path, 2))
    assert b"".join(decoded(data) for data in chunks) == pcm
    assert len(chunks) == 3
    assert decoded(next(audio_file_chunks(path))) == pcm


def test_invalid_chunk_length_is_rejected_before_recording():
    capture = audio.AudioCapture()
    with pytest.raises(ValueError, match="between 2 and 30"):
        capture.start(chunk_seconds=1.5)
