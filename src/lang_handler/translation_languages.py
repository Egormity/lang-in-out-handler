"""Normalize translation source metadata to the application's base ISO codes."""

import re

from .errors import ServiceError

_ALIASES = {"iw": "he", "in": "id", "jw": "jv"}
_UNKNOWN = {"und", "mul", "zxx"}


def resolved_source_language(value: object) -> str:
    """Unusable optional detection metadata must not invent a source language."""
    if not isinstance(value, str):
        return ""
    value = value.strip()
    if not re.fullmatch(r"[A-Za-z]{2,3}(?:-[A-Za-z]{2,4})?", value):
        return ""
    base = value.split("-", 1)[0].lower()
    return "" if base in _UNKNOWN else _ALIASES.get(base, base)


def selected_source_language(value: str) -> str:
    if isinstance(value, str) and value.strip().casefold() in {"", "auto", "auto detect"}:
        return ""
    code = resolved_source_language(value)
    if not code:
        raise ServiceError("Choose a source language from the language list.")
    return code
