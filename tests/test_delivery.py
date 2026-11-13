"""Delivery modes preserve clipboard data and never paste into our own controls."""

import subprocess
from types import SimpleNamespace

import pytest

from lang_handler import clipboard_snapshot, delivery, desktop
from lang_handler.clipboard_snapshot import ClipboardSnapshot


def clipboard_stubs(monkeypatch):
    events = []
    snapshot = ClipboardSnapshot("text/html", b"<b>previous</b>")
    monkeypatch.setattr(delivery, "snapshot_clipboard", lambda: snapshot)
    monkeypatch.setattr(desktop, "copy_text", lambda text: events.append(("copy", text)))
    monkeypatch.setattr(desktop, "paste_supported", lambda: True)
    monkeypatch.setattr(desktop, "paste_keys", lambda: events.append(("paste",)) or True)
    monkeypatch.setattr(delivery, "clipboard_still_contains", lambda *args: True)
    monkeypatch.setattr(delivery, "restore_clipboard", lambda saved: events.append(("restore", saved)))
    monkeypatch.setattr(delivery.time, "sleep", lambda duration: events.append(("wait", duration)))
    return events, snapshot


def test_copy_only_never_reads_clipboard_or_pastes(monkeypatch):
    events, _ = clipboard_stubs(monkeypatch)
    monkeypatch.setattr(delivery, "snapshot_clipboard", lambda: pytest.fail("unexpected snapshot"))
    assert desktop.deliver_transcript("日本語", "copy") == "Copied to clipboard."
    assert events == [("copy", "日本語")]


def test_paste_only_restores_exact_original_mime_bytes_after_paste(monkeypatch):
    events, snapshot = clipboard_stubs(monkeypatch)
    assert "preserved" in desktop.deliver_transcript("日本語", "paste")
    assert events == [("copy", "日本語"), ("paste",), ("wait", 0.35), ("restore", snapshot)]


def test_copy_and_paste_leaves_new_text_on_clipboard(monkeypatch):
    events, _ = clipboard_stubs(monkeypatch)
    assert "also copied" in desktop.deliver_transcript("日本語", "copy_and_paste")
    assert events == [("copy", "日本語"), ("paste",)]


def test_paste_only_preserves_clipboard_when_app_has_focus(monkeypatch):
    events, _ = clipboard_stubs(monkeypatch)
    assert "clipboard unchanged" in desktop.deliver_transcript("text", "paste", allow_paste=False)
    assert events == []
    assert "Focus another app" in desktop.deliver_transcript("text", "copy_and_paste", allow_paste=False)
    assert events == [("copy", "text")]


def test_paste_only_preserves_newer_copy_by_user(monkeypatch):
    events, _ = clipboard_stubs(monkeypatch)
    monkeypatch.setattr(delivery, "clipboard_still_contains", lambda *args: False)
    desktop.deliver_transcript("text", "paste")
    assert not any(event[0] == "restore" for event in events)


def test_failed_paste_restores_previous_clipboard(monkeypatch):
    events, snapshot = clipboard_stubs(monkeypatch)

    def failed():
        raise OSError("input service unavailable")

    monkeypatch.setattr(desktop, "paste_keys", failed)
    assert "paste failed" in desktop.deliver_transcript("text", "paste")
    assert events == [("copy", "text"), ("restore", snapshot)]


def test_missing_tool_or_failed_snapshot_cannot_replace_clipboard(monkeypatch):
    events, _ = clipboard_stubs(monkeypatch)
    monkeypatch.setattr(desktop, "paste_supported", lambda: False)
    assert "clipboard unchanged" in desktop.deliver_transcript("text", "paste")
    assert events == []
    monkeypatch.setattr(desktop, "paste_supported", lambda: True)

    def failed():
        raise RuntimeError("Could not preserve clipboard")

    monkeypatch.setattr(delivery, "snapshot_clipboard", failed)
    with pytest.raises(RuntimeError, match="preserve"):
        desktop.deliver_transcript("text", "paste")
    assert events == []


def test_restoration_failure_is_reported(monkeypatch):
    clipboard_stubs(monkeypatch)

    def failed(snapshot):
        raise OSError("selection owner unavailable")

    monkeypatch.setattr(delivery, "restore_clipboard", failed)
    with pytest.raises(RuntimeError, match="could not be restored"):
        desktop.deliver_transcript("text", "paste")


def test_snapshot_keeps_rich_type_and_binary_bytes(monkeypatch):
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    monkeypatch.setattr(clipboard_snapshot.shutil, "which", lambda name: name)
    calls = []

    def run(command):
        calls.append(command)
        if "--list-types" in command:
            return SimpleNamespace(stdout=b"text/plain\ntext/html\n")
        return SimpleNamespace(stdout=b"<b>\xe6\x97\xa5\xe6\x9c\xac</b>")

    monkeypatch.setattr(clipboard_snapshot, "_run", run)
    snapshot = clipboard_snapshot.snapshot_clipboard()
    assert snapshot.mime_type == "text/html"
    assert snapshot.content == b"<b>\xe6\x97\xa5\xe6\x9c\xac</b>"
    assert calls[-1] == ["wl-paste", "--no-newline", "--type", "text/html"]
    saved = []
    monkeypatch.setattr(
        clipboard_snapshot.subprocess, "run", lambda command, **kwargs: saved.append((command, kwargs))
    )
    clipboard_snapshot.restore_clipboard(snapshot)
    assert saved[0][0] == ["wl-copy", "--type", "text/html"]
    assert saved[0][1]["input"] == snapshot.content
    assert saved[0][1]["stdout"] == subprocess.DEVNULL


def test_empty_clipboard_restores_empty_selection(monkeypatch):
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    monkeypatch.setattr(clipboard_snapshot.shutil, "which", lambda name: name)

    def empty(command):
        raise subprocess.CalledProcessError(1, command, stderr=b"Nothing is copied")

    monkeypatch.setattr(clipboard_snapshot, "_run", empty)
    snapshot = clipboard_snapshot.snapshot_clipboard()
    assert snapshot.mime_type is None
    saved = []
    monkeypatch.setattr(
        clipboard_snapshot.subprocess, "run", lambda command, **kwargs: saved.append((command, kwargs))
    )
    clipboard_snapshot.restore_clipboard(snapshot)
    assert saved[0][0] == ["wl-copy", "--clear"]


def test_snapshot_failures_are_sanitized_and_do_not_count_as_empty(monkeypatch):
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    monkeypatch.setattr(clipboard_snapshot.shutil, "which", lambda name: name)

    def failed(command):
        raise subprocess.CalledProcessError(1, command, stderr=b"failed to connect")

    monkeypatch.setattr(clipboard_snapshot, "_run", failed)
    with pytest.raises(RuntimeError, match="Nothing was pasted"):
        clipboard_snapshot.snapshot_clipboard()
