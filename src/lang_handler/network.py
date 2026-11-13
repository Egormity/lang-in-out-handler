"""Use a saved or environment proxy without mutating the desktop environment."""

import os
from urllib.parse import unquote, urlsplit

from .errors import ServiceError


def proxy_url(explicit: str | None = None) -> str | None:
    value = (
        (explicit.strip() if explicit else "")
        or os.environ.get("https_proxy")
        or os.environ.get("HTTPS_PROXY")
        or os.environ.get("all_proxy")
        or os.environ.get("ALL_PROXY")
    )
    if value:
        value = value.strip()
    if value and value.lower().startswith("socks://"):
        value = "socks5://" + value[len("socks://") :]
    if value:
        try:
            parsed = urlsplit(value)
            valid = (
                parsed.scheme in {"http", "https", "socks5", "socks5h"}
                and bool(parsed.hostname)
                and (parsed.port is None or 1 <= parsed.port <= 65535)
                and parsed.path in {"", "/"}
                and not parsed.query
                and not parsed.fragment
            )
        except ValueError:
            valid = False
        if not valid:
            raise ServiceError("Enter a valid HTTP, HTTPS, or SOCKS5 proxy URL in Preferences.")
    return value or None


def websocket_proxy(explicit: str | None = None) -> dict:
    value = proxy_url(explicit)
    if not value:
        return {"http_no_proxy": ["*"]}
    parsed = urlsplit(value)
    kind = "http" if parsed.scheme in {"http", "https"} else parsed.scheme
    options = {
        "http_proxy_host": parsed.hostname,
        "http_proxy_port": parsed.port
        or (1080 if parsed.scheme.startswith("socks") else 443 if parsed.scheme == "https" else 80),
        "proxy_type": kind,
    }
    if parsed.username is not None:
        options["http_proxy_auth"] = (unquote(parsed.username), unquote(parsed.password or ""))
    return options
