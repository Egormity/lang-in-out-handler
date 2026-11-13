"""Preserve the preferred clipboard representation during a temporary paste."""

import os
import shutil
import subprocess
from dataclasses import dataclass

MAX_SNAPSHOT_BYTES = 32 * 1024 * 1024
PREFERRED_TYPES = (
    "x-special/gnome-copied-files",
    "text/uri-list",
    "text/html",
    "image/png",
    "image/jpeg",
    "image/webp",
    "text/plain;charset=utf-8",
    "text/plain",
    "UTF8_STRING",
    "STRING",
)
METADATA_TYPES = {"TARGETS", "TIMESTAMP", "MULTIPLE", "SAVE_TARGETS"}


@dataclass(frozen=True)
class ClipboardSnapshot:
    mime_type: str | None
    content: bytes = b""
    wayland: bool = True


def _run(command):
    return subprocess.run(command, check=True, capture_output=True, timeout=5)


def snapshot_clipboard() -> ClipboardSnapshot:
    """Read before changing anything; failure leaves the existing selection intact.

    wl-copy/xclip publish one preferred representation. Preserve its original MIME
    type and bytes, including rich text, images, and file selections when offered.
    """
    wayland = bool(os.environ.get("WAYLAND_DISPLAY"))
    if wayland:
        if not shutil.which("wl-paste") or not shutil.which("wl-copy"):
            raise RuntimeError("Paste to selection needs wl-clipboard to preserve your clipboard.")
        command = ["wl-paste", "--list-types"]
    else:
        if not shutil.which("xclip"):
            raise RuntimeError("Paste to selection needs xclip to preserve your clipboard.")
        command = ["xclip", "-selection", "clipboard", "-o", "-target", "TARGETS"]
    try:
        types = _run(command).stdout.decode(errors="replace").splitlines()
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or b"").decode(errors="replace").lower()
        if "nothing is copied" in message or "no selection" in message:
            return ClipboardSnapshot(None, wayland=wayland)
        raise RuntimeError("Could not preserve the clipboard. Nothing was pasted.") from None
    types = [item.strip() for item in types if item.strip() not in METADATA_TYPES]
    if not types:
        return ClipboardSnapshot(None, wayland=wayland)
    mime_type = next((item for item in PREFERRED_TYPES if item in types), types[0])
    command = (
        ["wl-paste", "--no-newline", "--type", mime_type]
        if wayland
        else ["xclip", "-selection", "clipboard", "-o", "-target", mime_type]
    )
    try:
        content = _run(command).stdout
    except (OSError, subprocess.SubprocessError):
        raise RuntimeError("Could not preserve the clipboard. Nothing was pasted.") from None
    if len(content) > MAX_SNAPSHOT_BYTES:
        raise RuntimeError("The clipboard is too large to preserve. Nothing was pasted.")
    return ClipboardSnapshot(mime_type, content, wayland)


def clipboard_still_contains(text: str, wayland: bool) -> bool:
    command = (
        ["wl-paste", "--no-newline", "--type", "text/plain;charset=utf-8"]
        if wayland
        else ["xclip", "-selection", "clipboard", "-o", "-target", "UTF8_STRING"]
    )
    try:
        return _run(command).stdout == text.encode()
    except (OSError, subprocess.SubprocessError):
        return False


def restore_clipboard(snapshot: ClipboardSnapshot):
    if snapshot.wayland:
        command = ["wl-copy", "--type", snapshot.mime_type] if snapshot.mime_type else ["wl-copy", "--clear"]
    else:
        command = ["xclip", "-selection", "clipboard", "-target", snapshot.mime_type or "UTF8_STRING"]
    subprocess.run(
        command,
        input=snapshot.content,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=5,
    )
