"""Clipboard, paste, and playback helpers for Linux desktop sessions."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def _run(command: list[str], **kwargs):
    return subprocess.run(command, check=True, capture_output=True, timeout=5, **kwargs)


def _qt_application():
    from PySide6.QtCore import QThread
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance()
    if application is not None and QThread.currentThread() == application.thread():
        return application
    return None


def _background_wayland(application) -> bool:
    return bool(
        application is not None
        and application.platformName().startswith("wayland")
        and application.activeWindow() is None
    )


def copy_text(text: str):
    application = _qt_application()
    if application is not None and not _background_wayland(application):
        application.clipboard().setText(text)
    elif os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-copy"):
        # Clipboard helpers fork a long-lived selection owner. Do not leave
        # stdout/stderr pipes open in that child and wait forever on communicate.
        subprocess.run(
            ["wl-copy", "--type", "text/plain;charset=utf-8"],
            input=text.encode(),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    elif shutil.which("xclip"):
        subprocess.run(
            ["xclip", "-selection", "clipboard"],
            input=text.encode(),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    else:
        raise RuntimeError(
            "Clipboard needs a desktop session and wl-copy, xclip, or the running app."
        )


def clipboard_text() -> str:
    application = _qt_application()
    if application is not None and (
        not _background_wayland(application) or application.clipboard().ownsClipboard()
    ):
        # Reading our own Qt selection through a blocking wl-paste would wait
        # for this GUI thread to serve the request. Read it directly instead.
        return application.clipboard().text()
    if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-paste"):
        return _run(["wl-paste", "--no-newline"], text=True).stdout
    if shutil.which("xclip"):
        return _run(["xclip", "-selection", "clipboard", "-o"], text=True).stdout
    return ""


def copy_and_paste(text: str, auto_paste: bool = True) -> str:
    """Copy first, then send Ctrl+V without activating the app or altering focus."""
    if not text:
        return "Nothing to paste."
    copy_text(text)
    if not auto_paste:
        return "Copied to clipboard."
    wayland = bool(os.environ.get("WAYLAND_DISPLAY"))
    try:
        if wayland and shutil.which("ydotool"):
            environment = os.environ.copy()
            socket = (
                Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
                / ".ydotool_socket"
            )
            if "YDOTOOL_SOCKET" not in environment and socket.exists():
                environment["YDOTOOL_SOCKET"] = str(socket)
            _run(
                ["ydotool", "key", "--key-delay", "20", "29:1", "47:1", "47:0", "29:0"],
                env=environment,
            )
            return "Pasted into the active app; also copied to clipboard."
        if not wayland and shutil.which("xdotool"):
            _run(["xdotool", "key", "--clearmodifiers", "ctrl+v"])
            return "Pasted into the active app; also copied to clipboard."
    except (OSError, subprocess.SubprocessError):
        return "Copied. Automatic paste failed; press Ctrl+V to insert it."
    return "Copied. Automatic paste needs ydotool on Wayland or xdotool on X11."


def play_audio(path: str | Path) -> subprocess.Popen:
    path = Path(path).expanduser().resolve(strict=True)
    for executable in ("pw-play", "paplay"):
        if shutil.which(executable):
            return subprocess.Popen(
                [executable, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
    raise RuntimeError("Audio playback needs PipeWire's pw-play or PulseAudio's paplay.")
