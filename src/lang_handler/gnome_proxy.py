"""Read the desktop proxy using system Python's GIO integration."""

import json
import sys


def lookup(url):
    try:
        import gi

        gi.require_version("Gio", "2.0")
        from gi.repository import Gio
    except (ImportError, ValueError):
        return {"ok": False, "unavailable": True}
    try:
        resolver = Gio.ProxyResolver.get_default()
        if not resolver or not resolver.is_supported():
            return {"ok": False, "unavailable": True}
        return {"ok": True, "proxies": list(resolver.lookup(url, None))}
    except Exception:  # noqa: BLE001 - process boundary must never leak authenticated URLs
        # Resolver errors can contain authenticated proxy URLs. Never echo them.
        return {"ok": False}


if __name__ == "__main__":
    print(json.dumps(lookup(sys.argv[1]), ensure_ascii=True))
