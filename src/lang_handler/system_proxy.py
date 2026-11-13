"""Resolve desktop networking without adding system GI libraries to the venv."""

import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

from .errors import ServiceError

# HTTPS lookup also applies to secure WebSocket's TLS/CONNECT transport.
OPENAI_PROXY_TARGET = "https://api.openai.com/v1"


def _lookup(url: str) -> dict:
    environment = {
        key: value for key, value in os.environ.items()
        if not key.lower().endswith("_proxy") and key not in {"PYTHONPATH", "PYTHONHOME"}
    }
    try:
        result = subprocess.run(
            ["/usr/bin/python3", str(Path(__file__).with_name("gnome_proxy.py")), url],
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=5,
            text=True,
        )
    except FileNotFoundError:
        return {"ok": False, "unavailable": True}
    except (OSError, subprocess.SubprocessError):
        raise ServiceError(
            "Could not resolve the system proxy. Check desktop network settings or set a proxy override."
        ) from None
    try:
        payload = json.loads(result.stdout)
        if result.returncode or not isinstance(payload, dict):
            raise ValueError
        return payload
    except (ValueError, TypeError):
        raise ServiceError("Could not read the system proxy settings. Try again.") from None


def desktop_proxy(target: str = OPENAI_PROXY_TARGET) -> str | None:
    if sys.platform != "linux":
        return None
    result = _lookup(target)
    if result.get("unavailable"):
        return None
    proxies = result.get("proxies")
    if not result.get("ok") or not isinstance(proxies, list) or not proxies:
        raise ServiceError("Could not resolve the system proxy. Check desktop network settings.")
    for value in proxies:
        if not isinstance(value, str):
            continue
        if value == "direct://":
            return None
        try:
            scheme = urlsplit(value).scheme
        except ValueError:
            continue
        if scheme in {"http", "https", "socks5", "socks5h"}:
            return value
    raise ServiceError(
        "The system returned an unsupported proxy type. Choose an HTTP or SOCKS5 proxy in desktop settings."
    )
