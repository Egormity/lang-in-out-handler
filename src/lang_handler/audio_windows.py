"""Lossless windows for the application's canonical mono PCM audio."""

from __future__ import annotations

import io
import math
import wave
from collections.abc import Iterator

SAMPLE_RATE = 16_000
BYTES_PER_SECOND = SAMPLE_RATE * 2


def read_pcm(audio: bytes) -> bytes:
    """Read complete, uncompressed 16 kHz mono PCM16 WAV data."""
    try:
        with wave.open(io.BytesIO(audio), "rb") as source:
            if (
                source.getnchannels() != 1
                or source.getsampwidth() != 2
                or source.getframerate() != SAMPLE_RATE
                or source.getcomptype() != "NONE"
            ):
                raise ValueError("Audio must be 16 kHz mono PCM16 WAV.")
            frames = source.getnframes()
            pcm = source.readframes(frames)
            if len(pcm) != frames * 2:
                raise ValueError("The WAV audio is incomplete.")
            return pcm
    except (wave.Error, EOFError) as error:
        raise ValueError("The recording is not a valid PCM WAV file.") from error


def pcm_to_wav(pcm: bytes) -> bytes:
    """Wrap complete little-endian PCM16 frames without recompression."""
    if len(pcm) % 2:
        raise ValueError("PCM16 audio must contain complete two-byte frames.")
    result = io.BytesIO()
    with wave.open(result, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        output.writeframes(pcm)
    return result.getvalue()


def duration_seconds(audio: bytes) -> float:
    return len(read_pcm(audio)) / BYTES_PER_SECOND


def split_wav(audio: bytes, seconds: float = 30) -> Iterator[bytes]:
    """Yield contiguous windows, preserving every frame exactly once.

    A subsecond final tail borrows frames from the preceding window, avoiding a
    nearly empty last request without overlapping or dropping audio.
    """
    if not math.isfinite(seconds) or not 1 <= seconds <= 30:
        raise ValueError("Audio windows must be between 1 and 30 seconds.")
    pcm = read_pcm(audio)
    target = int(seconds * SAMPLE_RATE) * 2
    start = 0
    while start < len(pcm):
        end = min(start + target, len(pcm))
        remaining = len(pcm) - end
        if 0 < remaining < BYTES_PER_SECOND:
            end -= BYTES_PER_SECOND - remaining
        yield pcm_to_wav(pcm[start:end])
        start = end
