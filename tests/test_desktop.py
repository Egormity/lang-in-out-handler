import json
from types import SimpleNamespace

import pytest

from lang_handler import desktop, shortcuts


def test_shortcut_conversion_and_invalid_sequences():
    assert shortcuts.accelerator("Meta+Alt+I") == "<Super><Alt>i"
    assert shortcuts.accelerator("") == ""
    with pytest.raises(ValueError):
        shortcuts.accelerator("Ctrl+K, Ctrl+T")
    with pytest.raises(ValueError):
        shortcuts.accelerator("Q")


def test_registering_preserves_unrelated_global_shortcuts(monkeypatch):
    calls = []
    other = shortcuts.ROOT_PATH + "handy-transcribe/"

    def run(*args):
        calls.append(args)
        if args == ("get", shortcuts.SCHEMA, "custom-keybindings"):
            return repr([other])
        if args[0] == "get" and args[-1] == "binding":
            return repr("<Super><Shift>d")
        if args[0] == "get" and args[-1] == "name":
            return repr("Handy")
        return ""

    monkeypatch.setattr(shortcuts, "_run", run)
    monkeypatch.setattr(shortcuts.GlobalShortcuts, "available", lambda self: True)
    registry = shortcuts.GlobalShortcuts()
    registry.apply({"input": "Meta+Alt+I"}, ["/path with spaces/lang-in-out"])
    paths_call = calls[-1]
    assert other in paths_call[-1]
    assert not any(
        other in arg
        for call in calls
        if call[0] in ("set", "reset-recursively")
        for arg in call[1:-1]
    )
    command_call = next(call for call in calls if call[0] == "set" and call[2] == "command")
    assert json.loads(command_call[3]) == "'/path with spaces/lang-in-out' --action input"


def test_conflicting_shortcut_does_not_mutate_settings(monkeypatch):
    mutations = []
    monkeypatch.setattr(shortcuts.GlobalShortcuts, "available", lambda self: True)
    monkeypatch.setattr(shortcuts.GlobalShortcuts, "_existing", lambda self: [])
    monkeypatch.setattr(
        shortcuts.GlobalShortcuts,
        "_conflicts",
        lambda self, existing: {
            shortcuts._canonical("<Super><Alt>i"): "Another app",
        },
    )
    monkeypatch.setattr(shortcuts, "_run", lambda *args: mutations.append(args))
    with pytest.raises(ValueError, match="Another app"):
        shortcuts.GlobalShortcuts().apply({"input": "Meta+Alt+I"}, ["lang-in-out"])
    assert mutations == []


def test_clipboard_only_does_not_send_keys(monkeypatch):
    copied = []
    monkeypatch.setattr(desktop, "copy_text", copied.append)
    monkeypatch.setattr(desktop, "_run", lambda *args, **kwargs: pytest.fail("unexpected paste"))
    assert desktop.copy_and_paste("こんにちは", auto_paste=False) == "Copied to clipboard."
    assert copied == ["こんにちは"]


def test_qt_clipboard_roundtrip_does_not_block_on_external_helper(qtbot, monkeypatch):
    monkeypatch.setattr(desktop, "_run", lambda *args, **kwargs: pytest.fail("external helper"))
    desktop.copy_text("日本語のテスト")
    assert desktop.clipboard_text() == "日本語のテスト"


def test_wayland_paste_uses_clipboard_and_key_events(monkeypatch):
    copied, calls = [], []
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    monkeypatch.setattr(desktop, "copy_text", copied.append)
    monkeypatch.setattr(
        desktop.shutil, "which", lambda name: "/usr/bin/ydotool" if name == "ydotool" else None
    )
    monkeypatch.setattr(desktop, "_run", lambda command, **kwargs: calls.append(command))
    assert "Pasted" in desktop.copy_and_paste("日本語")
    assert copied == ["日本語"]
    assert calls[0][-4:] == ["29:1", "47:1", "47:0", "29:0"]


def test_paste_failure_keeps_clipboard(monkeypatch):
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    monkeypatch.setattr(desktop, "copy_text", lambda text: None)
    monkeypatch.setattr(desktop.shutil, "which", lambda name: name)

    def failed(*args, **kwargs):
        raise OSError("daemon unavailable")

    monkeypatch.setattr(desktop, "_run", failed)
    assert "press Ctrl+V" in desktop.copy_and_paste("text")


def test_platform_setup_preserves_offscreen_override(monkeypatch):
    from lang_handler import qt_platform

    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setattr(
        qt_platform.ctypes, "CDLL", lambda *args, **kwargs: pytest.fail("library load")
    )
    assert qt_platform.configure_platform() == "offscreen"


def native_background(monkeypatch, owns=False):
    clipboard = SimpleNamespace(
        ownsClipboard=lambda: owns,
        text=lambda: "owned clipboard text",
        setText=lambda text: pytest.fail("background Qt clipboard write"),
    )
    app = SimpleNamespace(
        platformName=lambda: "wayland",
        activeWindow=lambda: None,
        clipboard=lambda: clipboard,
    )
    monkeypatch.setattr(desktop, "_qt_application", lambda: app)
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    monkeypatch.setattr(desktop.shutil, "which", lambda name: name)


def test_background_wayland_copy_uses_nonpiped_helper_even_for_owned_clipboard(monkeypatch):
    native_background(monkeypatch, owns=True)
    calls = []
    monkeypatch.setattr(
        desktop.subprocess, "run", lambda command, **kwargs: calls.append((command, kwargs))
    )
    desktop.copy_text("日本語")
    command, options = calls[0]
    assert command[0] == "wl-copy"
    assert options["input"] == "日本語".encode()
    assert options["stdout"] == desktop.subprocess.DEVNULL
    assert options["stderr"] == desktop.subprocess.DEVNULL
    assert options["check"]


def test_background_wayland_reads_other_app_through_helper(monkeypatch):
    native_background(monkeypatch)
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(stdout="external clipboard text")

    monkeypatch.setattr(desktop, "_run", run)
    assert desktop.clipboard_text() == "external clipboard text"
    assert calls == [["wl-paste", "--no-newline"]]


def test_background_wayland_owned_clipboard_avoids_blocking_helper(monkeypatch):
    native_background(monkeypatch, owns=True)
    monkeypatch.setattr(desktop, "_run", lambda *args, **kwargs: pytest.fail("GUI deadlock"))
    assert desktop.clipboard_text() == "owned clipboard text"
