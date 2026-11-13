"""Bounded microphone/system-output recording with PipeWire or PulseAudio."""

from __future__ import annotations

import array
import io
import math
import os
import selectors
import shutil
import subprocess
import tempfile
import threading
import wave

from PySide6.QtCore import QObject, Signal

from .audio_files import audio_file_chunks, enumerate_sources  # public convenience exports

SAMPLE_RATE = 16_000
BYTES_PER_SECOND = SAMPLE_RATE * 2
MAX_RECORD_SECONDS = 600
SILENCE_RMS = 0.0008


def pcm_to_wav(pcm: bytes) -> bytes:
    """Wrap little-endian mono signed 16-bit PCM without recompressing it."""
    result = io.BytesIO()
    with wave.open(result, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        output.writeframes(pcm[: len(pcm) // 2 * 2])
    return result.getvalue()


def rms(pcm: bytes) -> float:
    samples = array.array("h", pcm[: len(pcm) // 2 * 2])
    if not samples:
        return 0.0
    if os.sys.byteorder != "little":
        samples.byteswap()
    return math.sqrt(sum(value * value for value in samples) / len(samples)) / 32768


def capture_command(source: str = "") -> list[str]:
    """Default output follows the session's default sink without changing it."""
    if shutil.which("pw-record"):
        command = ["pw-record", "--raw", "--rate=16000", "--channels=1", "--format=s16"]
        monitor = source == "@DEFAULT_MONITOR@" or source.endswith(".monitor")
        if monitor:
            command += [
                "--properties",
                "{ stream.capture.sink=true node.name=lang-in-out-capture }",
            ]
        if source and source != "@DEFAULT_MONITOR@":
            command += ["--target", source.removesuffix(".monitor") if monitor else source]
        return command + ["-"]
    if shutil.which("parec"):
        command = ["parec", "--raw", "--format=s16le", "--rate=16000", "--channels=1"]
        if source:
            command.append(f"--device={source}")
        return command
    raise RuntimeError("Audio capture needs PipeWire's pw-record or PulseAudio's parec.")


class AudioCapture(QObject):
    """Emits independent WAV chunks; stop flushes the final partial recording.

    Capture uses a worker thread and a subprocess, so a stalled audio server cannot
    block the UI. Once mode ends explicitly at ten minutes to bound memory/upload
    size; chunk mode can run indefinitely. Silent live chunks are not submitted.
    """

    chunk = Signal(bytes)
    level = Signal(float)
    error = Signal(str)
    started = Signal()
    stopped = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._process: subprocess.Popen | None = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, source: str = "", chunked: bool = True, chunk_seconds: float = 5.0):
        if self.is_running:
            raise RuntimeError("Recording is already running.")
        if not 2 <= chunk_seconds <= 30:
            raise ValueError("Chunk length must be between 2 and 30 seconds.")
        command = capture_command(source)
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._record,
            args=(command, chunked, chunk_seconds),
            daemon=True,
            name="lang-in-out-capture",
        )
        self._thread.start()

    def stop(self):
        self._stop.set()

    def wait(self, timeout: float = 3.0):
        if self._thread:
            self._thread.join(timeout)

    def _emit_audio(self, buffer: bytes, chunked: bool):
        if len(buffer) < BYTES_PER_SECOND // 10:
            return
        if rms(buffer) < SILENCE_RMS:
            if not chunked:
                self.error.emit("No audible audio was captured. Check the selected audio source.")
            return
        self.chunk.emit(pcm_to_wav(buffer))

    def _record(self, command: list[str], chunked: bool, seconds: float):
        buffer = bytearray()
        target = int(seconds * BYTES_PER_SECOND) // 2 * 2
        process = None
        started = False
        try:
            with tempfile.TemporaryFile() as errors:
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors)
                self._process = process
                assert process.stdout is not None
                os.set_blocking(process.stdout.fileno(), False)
                with selectors.DefaultSelector() as selector:
                    selector.register(process.stdout, selectors.EVENT_READ)
                    while not self._stop.is_set():
                        ready = selector.select(0.1)
                        if not ready:
                            if process.poll() is not None:
                                break
                            continue
                        data = os.read(process.stdout.fileno(), 16_384)
                        if not data:
                            break
                        if not started:
                            started = True
                            self.started.emit()
                        self.level.emit(min(1.0, rms(data)))
                        buffer.extend(data)
                        if chunked:
                            while len(buffer) >= target:
                                self._emit_audio(bytes(buffer[:target]), True)
                                del buffer[:target]
                        elif len(buffer) >= MAX_RECORD_SECONDS * BYTES_PER_SECOND:
                            self.error.emit(
                                "The ten-minute recording limit was reached; transcribing now."
                            )
                            break
                if process.poll() is None:
                    process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
                # Retain audio already delivered to the pipe at the moment of Stop.
                tail = process.stdout.read() or b""
                buffer.extend(tail)
                if chunked:
                    while len(buffer) >= target:
                        self._emit_audio(bytes(buffer[:target]), True)
                        del buffer[:target]
                self._emit_audio(bytes(buffer), chunked)
                if process.returncode not in (0, -15) and not self._stop.is_set():
                    errors.seek(0)
                    detail = errors.read(2000).decode(errors="replace").strip()
                    self.error.emit(f"Audio capture stopped: {detail or process.returncode}")
        except (OSError, RuntimeError) as exc:
            self.error.emit(f"Audio capture failed: {exc}")
        finally:
            if process and process.poll() is None:
                process.kill()
                process.wait(timeout=2)
            if process and process.stdout:
                process.stdout.close()
            self._process = None
            self.level.emit(0.0)
            self.stopped.emit()


__all__ = ["AudioCapture", "audio_file_chunks", "enumerate_sources", "pcm_to_wav", "rms"]
