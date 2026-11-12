"""Use the existing HTTPS proxy without mutating the desktop environment."""

import os
from urllib.parse import unquote, urlsplit


def proxy_url() -> str | None:
    value = (
        os.environ.get("https_proxy")
        or os.environ.get("HTTPS_PROXY")
        or os.environ.get("all_proxy")
        or os.environ.get("ALL_PROXY")
    )
    if value and value.startswith("socks://"):
        value = "socks5://" + value[len("socks://") :]
    return value or None


def websocket_proxy() -> dict:
    value = proxy_url()
    if not value:
        return {"http_no_proxy": ["*"]}
    parsed = urlsplit(value)
    kind = "http" if parsed.scheme in {"http", "https"} else parsed.scheme
    options = {
        "http_proxy_host": parsed.hostname,
        "http_proxy_port": parsed.port or (443 if parsed.scheme == "https" else 80),
        "proxy_type": kind,
    }
    if parsed.username is not None:
        options["http_proxy_auth"] = (unquote(parsed.username), unquote(parsed.password or ""))
    return options
