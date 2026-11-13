"""Verified pinning must be idempotent, focus-scoped, and honest about failure."""

import json
import os
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QByteArray, QObject, QProcess

from lang_handler.gnome_pin import GnomeDesktop, PinError, apply_pin
from lang_handler.window_pin import WindowPin


class Desktop:
    def __init__(self, above=False, active=True, changes=True):
        self.above, self.active, self.changes = above, active, changes
        self.opened = self.activated = self.closed = 0

    def target_active(self):
        return self.active

    def open_menu(self):
        self.opened += 1
        return self

    def checked(self, item):
        return self.above

    def activate(self, item):
        self.activated += 1
        if self.changes:
            self.above = not self.above

    def close_menu(self):
        self.closed += 1


@pytest.mark.parametrize("enabled", [False, True])
def test_matching_compositor_state_is_not_toggled(enabled):
    desktop = Desktop(above=enabled)
    assert apply_pin(desktop, enabled) is enabled
    assert desktop.activated == 0
    assert desktop.opened == desktop.closed == 1


@pytest.mark.parametrize("enabled", [False, True])
def test_changed_state_is_reopened_and_verified(enabled):
    desktop = Desktop(above=not enabled)
    assert apply_pin(desktop, enabled) is enabled
    assert desktop.activated == 1
    assert desktop.opened == 2
    assert desktop.closed == 1


def test_unfocused_target_never_sends_keys_or_closes_other_menus():
    desktop = Desktop(active=False)
    with pytest.raises(PinError, match="Click this window"):
        apply_pin(desktop, True)
    assert desktop.opened == desktop.activated == desktop.closed == 0


def test_unsuccessful_toggle_is_reported_and_menu_is_closed():
    desktop = Desktop(changes=False)
    with pytest.raises(PinError, match="did not apply"):
        apply_pin(desktop, True)
    assert desktop.closed == 1


def test_desktop_launch_finds_user_ydotool_socket_without_environment(monkeypatch, tmp_path):
    monkeypatch.delenv("YDOTOOL_SOCKET", raising=False)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    calls = []
    monkeypatch.setattr("subprocess.run", lambda command, **kwargs: calls.append((command, kwargs)))
    desktop = GnomeDesktop.__new__(GnomeDesktop)
    desktop.ydotool = "/usr/bin/ydotool"
    desktop._keys("56:1", "57:1", "57:0", "56:0")
    assert calls[0][1]["env"]["YDOTOOL_SOCKET"] == str(tmp_path / ".ydotool_socket")
    assert calls[0][1]["timeout"] == 2
    assert "YDOTOOL_SOCKET" not in os.environ


class Window(QObject):
    def isVisible(self):
        return True

    def isActiveWindow(self):
        return False

    def activateWindow(self):
        pass


def test_wayland_pin_waits_for_target_focus_without_claiming_success(qapp, qtbot, monkeypatch):
    monkeypatch.setattr(WindowPin, "native_wayland", property(lambda self: True))
    window = Window()
    manager = WindowPin(window)
    messages, changes = [], []
    manager.message.connect(messages.append)
    manager.changed.connect(changes.append)
    manager.request(True)
    qtbot.wait(130)
    assert manager.process is None
    assert manager.auto_pending
    assert not manager.confirmed
    assert not manager.verified
    assert changes == [False]
    assert "Click this window" in messages[-1]


def test_helper_failure_keeps_checkbox_unconfirmed(qapp):
    window = Window()
    manager = WindowPin(window)
    changes, messages = [], []
    manager.changed.connect(changes.append)
    manager.message.connect(messages.append)
    result = {"ok": False, "message": "GNOME did not apply On top."}
    manager.process = SimpleNamespace(
        readAllStandardOutput=lambda: QByteArray(json.dumps(result).encode()),
        deleteLater=lambda: None,
    )
    manager._finished(1, QProcess.ExitStatus.NormalExit)
    assert not manager.verified
    assert changes == [False]
    assert messages == [result["message"]]
