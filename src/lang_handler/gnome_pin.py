"""Bounded GNOME window-menu interaction, run with the system Python/AT-SPI."""

import argparse
import gettext
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

ALLOWED_TITLES = {"Lang In/Out · Captions", "Lang In/Out · Handwriting"}


class PinError(RuntimeError):
    pass


def apply_pin(desktop, enabled):
    """Never toggle an unknown state or a window that did not own focus."""
    if not desktop.target_active():
        raise PinError("Click this window to apply On top.")
    item = None
    try:
        item = desktop.open_menu()
        if desktop.checked(item) != enabled:
            desktop.activate(item)
            # Verify the compositor's own state instead of trusting the key event.
            item = desktop.open_menu()
        actual = desktop.checked(item)
        if actual != enabled:
            raise PinError("GNOME did not apply On top. Click the window and try again.")
        return actual
    finally:
        desktop.close_menu()


class GnomeDesktop:
    def __init__(self, pid, title):
        import gi

        gi.require_version("Atspi", "2.0")
        from gi.repository import Atspi

        self.atspi = Atspi
        Atspi.set_timeout(250, 250)
        self.desktop = Atspi.get_desktop(0)
        self.pid, self.title = pid, title
        self.opened_item = None
        self.ydotool = shutil.which("ydotool")
        if not self.ydotool:
            raise PinError("On top needs ydotool and the GNOME accessibility service.")
        self.label = gettext.translation("gnome-shell", fallback=True).gettext("Always on Top")

    def _walk(self, root, depth=10):
        pending = [(root, 0)]
        for _ in range(2500):
            if not pending:
                break
            node, level = pending.pop()
            if node is None:
                continue
            yield node
            if level < depth:
                pending.extend(
                    (node.get_child_at_index(i), level + 1) for i in range(node.get_child_count())
                )

    def target_active(self):
        for index in range(self.desktop.get_child_count()):
            app = self.desktop.get_child_at_index(index)
            if app is None or app.get_process_id() != self.pid:
                continue
            for node in self._walk(app, 2):
                if node.get_name() in {
                    self.title,
                    self.title + " — Lang In/Out",
                } and node.get_state_set().contains(self.atspi.StateType.ACTIVE):
                    return True
        return False

    def _item(self):
        shell = None
        for index in range(self.desktop.get_child_count()):
            app = self.desktop.get_child_at_index(index)
            if app is not None and app.get_name() == "gnome-shell":
                shell = app
                break
        if shell is None:
            return None
        for node in self._walk(shell):
            if node.get_name() != self.label:
                continue
            item = node.get_parent()
            if item is None or not item.get_state_set().contains(self.atspi.StateType.SHOWING):
                continue
            return item
        return None

    def _keys(self, *keys):
        environment = os.environ.copy()
        if not environment.get("YDOTOOL_SOCKET"):
            runtime = Path(environment.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
            environment["YDOTOOL_SOCKET"] = str(runtime / ".ydotool_socket")
        subprocess.run(
            [self.ydotool, "key", *keys],
            capture_output=True,
            check=True,
            timeout=2,
            env=environment,
        )

    def open_menu(self):
        if not self.target_active():
            raise PinError("Click this window to apply On top.")
        self._keys("56:1", "57:1", "57:0", "56:0")
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline:
            item = self._item()
            if item is not None:
                self.opened_item = item
                return item
            time.sleep(0.05)
        raise PinError(
            "GNOME's window menu was unavailable. Click the window and try On top again."
        )

    def checked(self, item):
        if not item.get_state_set().contains(self.atspi.StateType.SHOWING):
            raise PinError("The window menu closed before On top could be verified.")
        return item.get_state_set().contains(self.atspi.StateType.CHECKED)

    def activate(self, item):
        if not item.get_state_set().contains(self.atspi.StateType.SENSITIVE):
            raise PinError("GNOME does not allow On top for this window.")
        if not self.atspi.Component.grab_focus(item):
            raise PinError("Could not select GNOME's On top control.")
        self._keys("28:1", "28:0")
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            if self.target_active():
                self.opened_item = None
                return
            time.sleep(0.04)
        raise PinError("Window focus changed while setting On top. Try again.")

    def close_menu(self):
        # Do not dismiss a different menu if the user changed focus during the operation.
        if self.opened_item is not None and self.opened_item.get_state_set().contains(
            self.atspi.StateType.SHOWING
        ):
            self._keys("1:1", "1:0")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pid", type=int)
    parser.add_argument("title", choices=sorted(ALLOWED_TITLES))
    parser.add_argument("enabled", choices=["true", "false"])
    args = parser.parse_args()
    try:
        above = apply_pin(GnomeDesktop(args.pid, args.title), args.enabled == "true")
        print(json.dumps({"ok": True, "above": above}))
        return 0
    except Exception as error:  # noqa: BLE001 - process boundary reports safe diagnostic JSON
        message = (
            str(error)
            if isinstance(error, PinError)
            else ("Could not access GNOME's window controls. Check ydotool and python3-gi.")
        )
        print(json.dumps({"ok": False, "message": message}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
