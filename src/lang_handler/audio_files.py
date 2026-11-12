"""Device discovery and local audio decoding. No model or network calls."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path


def enumerate_sources() -> list[dict]:
    if shutil.which("pw-dump"):
        result = subprocess.run(["pw-dump"], capture_output=True, text=True, timeout=5, check=True)
        devices = []
        for obj in json.loads(result.stdout):
            props = obj.get("info", {}).get("props", {})
            category = props.get("media.class")
            if category not in ("Audio/Source", "Audio/Sink"):
                continue
            name = props.get("node.name", "")
            if not name:
                continue
            monitor = category == "Audio/Sink"
            devices.append(
                {
                    "name": name + (".monitor" if monitor else ""),
                    "description": props.get("node.description", name)
                    + (" — output" if monitor else ""),
                    "is_monitor": monitor,
                }
            )
        return devices
    if shutil.which("pactl"):
        result = subprocess.run(
            ["pactl", "--format=json", "list", "sources"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        return [
            {
                "name": value["name"],
                "description": value.get("description", value["name"]),
                "is_monitor": value["name"].endswith(".monitor"),
            }
            for value in json.loads(result.stdout)
        ]
    return []


def ffmpeg_binary() -> str:
    installed = shutil.which("ffmpeg")
    if installed:
        return installed
    try:
        from imageio_ffmpeg import get_ffmpeg_exe

        return get_ffmpeg_exe()
    except (ImportError, RuntimeError) as exc:
        raise RuntimeError("Audio import requires ffmpeg or the imageio-ffmpeg package.") from exc


def audio_file_chunks(path: Path, seconds: float | None = None):
    """Decode media to 16 kHz mono WAV requests; files over ten minutes need chunks."""
    from .audio import BYTES_PER_SECOND, MAX_RECORD_SECONDS, pcm_to_wav

    path = Path(path).expanduser().resolve(strict=True)
    if not path.is_file():
        raise ValueError("Choose an audio or video file.")
    if seconds is not None and not 2 <= seconds <= 30:
        raise ValueError("Chunk length must be between 2 and 30 seconds.")
    target = int((seconds or MAX_RECORD_SECONDS) * BYTES_PER_SECOND) // 2 * 2
    command = [
        ffmpeg_binary(),
        "-nostdin",
        "-v",
        "error",
        "-i",
        str(path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-f",
        "s16le",
        "pipe:1",
    ]
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors)
        assert process.stdout is not None
        buffer = bytearray()
        try:
            while True:
                data = process.stdout.read(32_768)
                if not data:
                    break
                buffer.extend(data)
                if seconds is None and len(buffer) > target:
                    raise ValueError(
                        "This file exceeds ten minutes. Enable chunks to transcribe it."
                    )
                if seconds is not None:
                    while len(buffer) >= target:
                        yield pcm_to_wav(bytes(buffer[:target]))
                        del buffer[:target]
            process.wait(timeout=10)
            if process.returncode:
                errors.seek(0)
                detail = errors.read(1500).decode(errors="replace").strip()
                raise RuntimeError(f"Could not decode audio: {detail}")
            if buffer:
                yield pcm_to_wav(bytes(buffer))
            elif seconds is None:
                raise ValueError("The file contains no audio.")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=2)
            process.stdout.close()
