"""Defensive parsing for Google's undocumented web-service responses."""

import html

from .errors import ServiceError
from .results import TranslationResult
from .translation_languages import resolved_source_language


def handwriting_candidates(payload) -> list[str]:
    message = "Google returned an unsupported handwriting response. Try again later."
    if not isinstance(payload, list) or not payload:
        raise ServiceError(message)
    if payload[0] != "SUCCESS":
        raise ServiceError("Google rejected this handwriting request. Check the selected language.")
    try:
        candidates = payload[1][0][1]
    except (IndexError, KeyError, TypeError):
        raise ServiceError(message) from None
    if not isinstance(candidates, list) or any(not isinstance(value, str) for value in candidates):
        raise ServiceError(message)
    row = payload[1][0]
    metadata = row[3] if len(row) > 3 and isinstance(row[3], dict) else {}
    if metadata.get("is_html_escaped") is True:
        candidates = [html.unescape(text) for text in candidates]
    return list(dict.fromkeys(text.strip() for text in candidates if text.strip()))[:20]


def translation_result(payload, *, source_language: str = "") -> TranslationResult:
    message = "Google returned an unsupported translation response. Try again later."
    if not isinstance(payload, dict) or not isinstance(payload.get("sentences"), list):
        raise ServiceError(message)
    translated, source_readings, translated_readings = [], [], []
    for sentence in payload["sentences"]:
        if not isinstance(sentence, dict):
            raise ServiceError(message)
        for name, destination in (
            ("trans", translated), ("src_translit", source_readings), ("translit", translated_readings)
        ):
            value = sentence.get(name)
            if value is None:
                continue
            if not isinstance(value, str):
                raise ServiceError(message)
            destination.append(value)
    translation = "".join(translated).strip()
    if not translation:
        raise ServiceError("Google returned no translated text. Try a shorter passage.")
    # Tested responses provide romanization but no reliable explicit correction.
    # Never infer a correction from a translation or rewrite the original input.
    return TranslationResult(
        translation=translation,
        source_pronunciation=" ".join(value.strip() for value in source_readings if value.strip()),
        translation_pronunciation=" ".join(value.strip() for value in translated_readings if value.strip()),
        source_language=source_language or resolved_source_language(payload.get("src")),
    )

