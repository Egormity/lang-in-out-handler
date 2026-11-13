"""Present individually revisable chunks as one saved recording or imported file."""

from .text_utils import flowing_text

_TEXT_FIELDS = (
    "source_text", "translated_text", "source_pronunciation", "translation_pronunciation"
)


def combine_sessions(rows) -> list[dict]:
    """Rows are ordered by newest group, then oldest segment within that group."""
    groups = {}
    for row in rows:
        item = dict(row)
        key = (item["mode"], item["session_id"] or item["id"])
        groups.setdefault(key, []).append(item)
    combined = []
    for segments in groups.values():
        entry = dict(segments[0])
        entry["segment_count"] = len(segments)
        if len(segments) > 1:
            for field in _TEXT_FIELDS:
                entry[field] = flowing_text(part[field] for part in segments)
        # The first chunk provides the stable ID and recording start timestamp.
        combined.append(entry)
    return combined
