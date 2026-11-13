"""Bounded source context and strict structured results for revisable captions."""

import json
from collections.abc import Sequence

from .errors import ServiceError
from .prompts import builtin_instructions
from .results import CaptionRevision, TranslationResult

MAX_CONTEXT_SEGMENTS = 6
MAX_CONTEXT_CHARS = 6000


def trim_context(segments: Sequence[tuple[int, str]]) -> list[tuple[int, str]]:
    """Keep recent context; a single long recording remains intact, never truncated."""
    result = list(segments[-MAX_CONTEXT_SEGMENTS:])
    while len(result) > 1 and sum(len(text) for _, text in result) > MAX_CONTEXT_CHARS:
        result.pop(0)
    return result


def validate_segments(segments: Sequence[tuple[int, str]]) -> list[tuple[int, str]]:
    result = list(segments)
    if not result or len(result) > MAX_CONTEXT_SEGMENTS:
        raise ServiceError("Caption context must contain between one and six audio segments.")
    ids = set()
    for row in result:
        if (not isinstance(row, (tuple, list)) or len(row) != 2
                or type(row[0]) is not int or not isinstance(row[1], str) or not row[1].strip()
                or row[0] in ids):
            raise ServiceError("Caption context contains invalid or duplicate segments.")
        ids.add(row[0])
    if len(result) > 1 and sum(len(text) for _, text in result) > MAX_CONTEXT_CHARS:
        raise ServiceError("Caption context exceeds the recent-text limit.")
    return [(segment_id, text.strip()) for segment_id, text in result]


def caption_options(segments, target_language, instructions):
    guidance = builtin_instructions("translation_instructions", captions=True)
    guidance += f"\n\nSelected target language: {target_language}."
    fields = ("translation", "source_pronunciation", "translation_pronunciation")
    item = {
        "type": "object",
        "properties": {
            "segment_id": {"type": "integer", "enum": [segment_id for segment_id, _ in segments]},
            **{field: {"type": "string"} for field in fields},
        },
        "required": ["segment_id", *fields],
        "additionalProperties": False,
    }
    return {
        "instructions": guidance,
        "input": json.dumps(
            {
                "segments": [{"segment_id": segment_id, "text": text} for segment_id, text in segments],
                "custom_instructions": instructions.strip(),
            },
            ensure_ascii=False,
        ),
        "store": False,
        "text": {"format": {
            "type": "json_schema", "name": "continuous_caption_revisions", "strict": True,
            "schema": {
                "type": "object",
                "properties": {"items": {
                    "type": "array", "items": item,
                    "minItems": len(segments), "maxItems": len(segments),
                }},
                "required": ["items"], "additionalProperties": False,
            },
        }},
    }


def parse_revisions(output_text, segments) -> list[CaptionRevision]:
    message = "The model returned invalid caption revisions. Try again or choose another model."
    try:
        payload = json.loads(output_text)
    except (ValueError, TypeError):
        raise ServiceError(message) from None
    if not isinstance(payload, dict) or set(payload) != {"items"}:
        raise ServiceError(message)
    items = payload["items"]
    if not isinstance(items, list) or len(items) != len(segments):
        raise ServiceError(message)
    expected = {segment_id: text for segment_id, text in segments}
    parsed = {}
    fields = ("translation", "source_pronunciation", "translation_pronunciation")
    for item in items:
        if (not isinstance(item, dict) or set(item) != {"segment_id", *fields}
                or type(item["segment_id"]) is not int
                or item["segment_id"] not in expected or item["segment_id"] in parsed
                or any(not isinstance(item[field], str) for field in fields)
                or (not item["translation"].strip() and item["translation_pronunciation"].strip())):
            raise ServiceError(message)
        segment_id = item["segment_id"]
        parsed[segment_id] = CaptionRevision(
            segment_id, expected[segment_id],
            TranslationResult(**{field: item[field].strip() for field in fields}),
        )
    if not any(item.result.translation for item in parsed.values()):
        raise ServiceError(message)
    return [parsed[segment_id] for segment_id, _ in segments]
