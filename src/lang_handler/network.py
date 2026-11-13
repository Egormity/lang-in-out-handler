"""Resolve an optional override, environment, or desktop proxy for every transport."""

import os
from urllib.parse import unquote, urlsplit
from urllib.request import proxy_bypass_environment

from .errors import ServiceError
from .system_proxy import OPENAI_PROXY_TARGET, desktop_proxy


def proxy_url(explicit: str | None = None) -> str | None:
    value = explicit.strip() if explicit else ""
    if not value:
        value = next((os.environ[name].strip() for name in (
            "https_proxy", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"
        ) if os.environ.get(name, "").strip()), "")
        if value:
            bypass = os.environ.get("no_proxy", os.environ.get("NO_PROXY", ""))
            if proxy_bypass_environment(urlsplit(OPENAI_PROXY_TARGET).netloc, {"no": bypass}):
                return None
        else:
            value = desktop_proxy()
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
        # Routing was already resolved above. Do not let websocket-client apply
        # inherited NO_PROXY again and silently disagree with the HTTP client.
        "http_no_proxy": ["__lang_handler_no_bypass__"],
    }
    if parsed.username is not None:
        options["http_proxy_auth"] = (unquote(parsed.username), unquote(parsed.password or ""))
    return options
