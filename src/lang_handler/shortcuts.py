"""GNOME global keyboard bindings, preserving all unrelated bindings."""

from __future__ import annotations

import ast
import json
import os
import re
import shlex
import shutil
import subprocess

SCHEMA = "org.gnome.settings-daemon.plugins.media-keys"
CUSTOM_SCHEMA = SCHEMA + ".custom-keybinding"
ROOT_PATH = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/"
ACTIONS = {
    "input": "Dictation",
    "output": "Live captions",
    "translate": "Translate clipboard",
    "tts": "Speak clipboard",
}


def accelerator(sequence: str) -> str:
    """Convert a portable Qt key sequence into one GTK accelerator."""
    if not sequence.strip():
        return ""
    if "," in sequence:
        raise ValueError("Global shortcuts must be a single key combination.")
    parts = sequence.split("+")
    modifiers = {"Meta": "Super", "Ctrl": "Control", "Alt": "Alt", "Shift": "Shift"}
    if len(parts) < 2 or any(part not in modifiers for part in parts[:-1]):
        raise ValueError(f"Use a modifier and a key for the shortcut: {sequence}")
    key = parts[-1]
    aliases = {
        "Space": "space",
        "Return": "Return",
        "Enter": "KP_Enter",
        "Esc": "Escape",
        "Backspace": "BackSpace",
        "Del": "Delete",
        "PgUp": "Page_Up",
        "PgDown": "Page_Down",
    }
    if not re.fullmatch(r"[A-Za-z0-9_]+", key):
        raise ValueError(f"Unsupported shortcut key: {key}")
    key = aliases.get(key, key.lower() if len(key) == 1 else key)
    return "".join(f"<{modifiers[part]}>" for part in parts[:-1]) + key


def _canonical(value: str) -> tuple:
    value = (
        value.lower()
        .replace("<primary>", "<control>")
        .replace("<ctrl>", "<control>")
        .replace("<meta>", "<super>")
    )
    modifiers = sorted(re.findall(r"<([^>]+)>", value))
    return tuple(modifiers), re.sub(r"<[^>]+>", "", value)


def _run(*arguments: str) -> str:
    try:
        return subprocess.run(
            ["gsettings", *arguments], capture_output=True, text=True, check=True, timeout=5
        ).stdout.strip()
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Could not configure desktop shortcuts: {exc.stderr.strip()}") from exc


def _strings(value: str) -> list[str]:
    value = value.removeprefix("@as ")
    parsed = ast.literal_eval(value)
    return [parsed] if isinstance(parsed, str) else list(parsed)


class GlobalShortcuts:
    def available(self) -> bool:
        return bool(
            shutil.which("gsettings")
            and "GNOME" in os.environ.get("XDG_CURRENT_DESKTOP", "").upper()
        )

    @staticmethod
    def _path(action: str) -> str:
        return ROOT_PATH + "lang-in-out-" + action + "/"

    def _existing(self) -> list[str]:
        return _strings(_run("get", SCHEMA, "custom-keybindings"))

    def _conflicts(self, existing: list[str]) -> dict[tuple, str]:
        conflicts = {}
        for path in existing:
            if path.startswith(ROOT_PATH + "lang-in-out-"):
                continue
            schema = CUSTOM_SCHEMA + ":" + path
            value = _strings(_run("get", schema, "binding"))[0]
            if value:
                conflicts[_canonical(value)] = _strings(_run("get", schema, "name"))[0]
        for schema in ("org.gnome.desktop.wm.keybindings", SCHEMA):
            for line in _run("list-recursively", schema).splitlines():
                parts = line.split(" ", 2)
                if len(parts) != 3 or parts[1] == "custom-keybindings":
                    continue
                try:
                    values = _strings(parts[2])
                except (ValueError, SyntaxError, TypeError):
                    continue
                for value in values:
                    if isinstance(value, str) and value:
                        conflicts[_canonical(value)] = parts[1]
        return conflicts

    def apply(self, shortcuts: dict[str, str], command: list[str] | str) -> str:
        if not self.available():
            return "Global shortcuts: configure your desktop to run lang-in-out --action input/output/translate/tts."
        converted = {action: accelerator(shortcuts.get(action, "")) for action in ACTIONS}
        used = [_canonical(value) for value in converted.values() if value]
        if len(set(used)) != len(used):
            raise ValueError("Each action needs a different global shortcut.")
        existing = self._existing()
        conflicts = self._conflicts(existing)
        for action, value in converted.items():
            if value and _canonical(value) in conflicts:
                raise ValueError(
                    f"{shortcuts[action]} is already assigned to {conflicts[_canonical(value)]}."
                )
        prefix = shlex.split(command) if isinstance(command, str) else list(command)
        if not prefix:
            raise ValueError("The shortcut launch command is empty.")
        paths = [path for path in existing if not path.startswith(ROOT_PATH + "lang-in-out-")]
        for action, value in converted.items():
            path = self._path(action)
            schema = CUSTOM_SCHEMA + ":" + path
            if not value:
                _run("reset-recursively", schema)
                continue
            _run("set", schema, "name", json.dumps("Lang In/Out — " + ACTIONS[action]))
            _run("set", schema, "command", json.dumps(shlex.join(prefix + ["--action", action])))
            _run("set", schema, "binding", json.dumps(value))
            paths.append(path)
        _run("set", SCHEMA, "custom-keybindings", repr(paths))
        return "Global shortcuts registered with GNOME."

    def unregister(self):
        if not self.available():
            return
        existing = self._existing()
        kept = [path for path in existing if not path.startswith(ROOT_PATH + "lang-in-out-")]
        _run("set", SCHEMA, "custom-keybindings", repr(kept))
        for action in ACTIONS:
            _run("reset-recursively", CUSTOM_SCHEMA + ":" + self._path(action))
