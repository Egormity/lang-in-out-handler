"""Dictation delivery with temporary clipboard use for paste-only mode."""

import subprocess
import threading
import time

from . import desktop
from .clipboard_snapshot import clipboard_still_contains, restore_clipboard, snapshot_clipboard

# The controller submits a FIFO queue; this also protects direct callers from
# overlapping temporary selections. None of this work belongs on Qt's GUI thread.
_delivery_lock = threading.Lock()


def deliver(text: str, mode: str, *, allow_paste: bool = True) -> str:
    if mode not in {"copy", "paste", "copy_and_paste"}:
        raise ValueError("Choose how to deliver voice input: copy, paste, or copy and paste.")
    if not text:
        return "Nothing to deliver."
    with _delivery_lock:
        if mode == "copy":
            desktop.copy_text(text)
            return "Copied to clipboard."
        if not allow_paste:
            if mode == "copy_and_paste":
                desktop.copy_text(text)
                return "Copied. Focus another app to paste dictation automatically."
            return "Transcript ready. Focus another app to paste; clipboard unchanged."
        if mode == "copy_and_paste":
            return desktop.copy_and_paste(text)
        return _paste_without_copying(text)


def _paste_without_copying(text: str) -> str:
    if not desktop.paste_supported():
        return "Paste needs ydotool on Wayland or xdotool on X11; clipboard unchanged."
    snapshot = snapshot_clipboard()
    changed = pasted = False
    try:
        desktop.copy_text(text)
        changed = True
        pasted = desktop.paste_keys()
        if pasted:
            # Allow the destination's asynchronous clipboard request to finish.
            # This runs on a worker, leaving our Qt clipboard owner responsive.
            time.sleep(0.35)
    except (OSError, subprocess.SubprocessError):
        pasted = False
    finally:
        # If the user copied something during insertion, keep their newer copy.
        if changed and clipboard_still_contains(text, snapshot.wayland):
            try:
                restore_clipboard(snapshot)
            except (OSError, subprocess.SubprocessError):
                raise RuntimeError(
                    "Text was pasted, but the previous clipboard could not be restored."
                    if pasted else "Paste failed and the previous clipboard could not be restored."
                ) from None
    if pasted:
        return "Pasted into the active selection; previous clipboard preserved."
    return "Automatic paste failed; previous clipboard preserved. Transcript is available in the app."
