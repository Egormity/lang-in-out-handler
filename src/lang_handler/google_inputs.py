"""Validate the small public-web request formats used by the Google provider."""

import math
import re

from .errors import ServiceError
from .ink import InkSnapshot

GOOGLE_TRANSLATION_MAX_CHARS = 5000
MAX_INK_POINTS = 30_000
MAX_INK_STROKES = 1000

# These names are the application's language choices, not a claim of verified
# handwriting coverage. The service can reject a language it does not support.
_LANGUAGE_NAMES = {
    "japanese": "ja", "english": "en", "russian": "ru", "spanish": "es",
    "french": "fr", "german": "de", "chinese": "zh-CN", "korean": "ko",
    "arabic": "ar", "bengali": "bn", "bulgarian": "bg", "catalan": "ca",
    "croatian": "hr", "czech": "cs", "danish": "da", "dutch": "nl",
    "estonian": "et", "finnish": "fi", "greek": "el", "hebrew": "he",
    "hindi": "hi", "hungarian": "hu", "indonesian": "id", "italian": "it",
    "latvian": "lv", "lithuanian": "lt", "malay": "ms", "norwegian": "no",
    "persian": "fa", "polish": "pl", "portuguese": "pt", "romanian": "ro",
    "serbian": "sr", "slovak": "sk", "slovenian": "sl", "swedish": "sv",
    "tamil": "ta", "telugu": "te", "thai": "th", "turkish": "tr",
    "ukrainian": "uk", "urdu": "ur", "vietnamese": "vi",
    "simplified chinese": "zh-CN", "traditional chinese": "zh-TW",
    "русский": "ru", "日本語": "ja", "中文": "zh-CN",
}


def language_code(value: str, *, handwriting: bool = False) -> str:
    value = value.strip() if isinstance(value, str) else ""
    if not value or value.casefold() in {"auto", "auto detect"}:
        if handwriting:
            raise ServiceError("Choose a handwriting language. Google cannot auto-detect pen input.")
        raise ServiceError("Choose a translation language.")
    if value.casefold() in _LANGUAGE_NAMES:
        return _LANGUAGE_NAMES[value.casefold()]
    if not re.fullmatch(r"[A-Za-z]{2,3}(?:-[A-Za-z]{2,4})?", value):
        raise ServiceError("Google needs a language name from the list or a language code such as ja.")
    parts = value.split("-")
    code = parts[0].lower()
    if len(parts) > 1:
        code += "-" + (parts[1].upper() if len(parts[1]) == 2 else parts[1].title())
    return "zh-CN" if code == "zh" else code


def handwriting_payload(ink: InkSnapshot, language: str) -> dict:
    language = language_code(language, handwriting=True)
    if not isinstance(ink, InkSnapshot):
        raise ServiceError("Google handwriting needs pen strokes from the canvas, not an image.")
    if any(not math.isfinite(size) or not 0 < size <= 65535 for size in (ink.width, ink.height)):
        raise ServiceError("The handwriting canvas has invalid dimensions.")
    if not ink or len(ink.strokes) > MAX_INK_STROKES:
        raise ServiceError("Draw some text first, with fewer than 1,000 strokes per request.")
    if sum(len(stroke) for stroke in ink.strokes) > MAX_INK_POINTS:
        raise ServiceError("This drawing is too large for Google. Recognize a smaller section.")
    strokes = []
    for stroke in ink.strokes:
        if not stroke:
            raise ServiceError("The drawing contains an empty pen stroke.")
        xs, ys, times = [], [], []
        previous_time = -1
        for point in stroke:
            if len(point) != 3 or any(not math.isfinite(value) for value in point):
                raise ServiceError("The drawing contains invalid pen coordinates or timing.")
            x, y, timestamp = point
            if not (0 <= x <= ink.width and 0 <= y <= ink.height and 0 <= timestamp <= 1e12):
                raise ServiceError("The drawing contains pen data outside the canvas.")
            if timestamp < previous_time:
                raise ServiceError("The drawing contains pen points in an invalid time order.")
            previous_time = timestamp
            xs.append(round(x, 3))
            ys.append(round(y, 3))
            times.append(round(timestamp))
        strokes.append([xs, ys, times])
    return {
        "device": "Lang In/Out",
        "options": "enable_pre_space",
        "requests": [{
            "writing_guide": {"writing_area_width": ink.width, "writing_area_height": ink.height},
            "ink": strokes,
            "language": language,
        }],
    }
