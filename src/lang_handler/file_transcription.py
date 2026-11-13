"""One visible file transcript, recognized in bounded requests with context."""

from __future__ import annotations

import logging
from collections.abc import Callable
from threading import Event

from .audio_windows import split_wav
from .errors import ServiceError
from .text_utils import flowing_text
from .transcription_context import MAX_CONTEXT_CHARS, recognized_text

_LOG = logging.getLogger(__name__)


def transcribe_file_once(
    service,
    audio: bytes,
    model: str,
    language: str = "",
    instructions: str = "",
    *,
    cancel: Event | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> str:
    """Recognize one file without trusting a single long-audio model response.

    Progress receives completed and total request counts, including windows
    without recognized words. Cancellation discards all partial output; API
    failures propagate rather than presenting an incomplete file as complete.
    """
    if cancel is not None and cancel.is_set():
        return ""
    try:
        windows = list(split_wav(audio))
    except ValueError as error:
        raise ServiceError(str(error)) from error
    parts: list[str] = []
    previous = ""
    for index, window in enumerate(windows, 1):
        if cancel is not None and cancel.is_set():
            return ""
        text = recognized_text(
            service.transcribe(window, model, language, instructions, context=previous)
        )
        if cancel is not None and cancel.is_set():
            return ""
        if text:
            parts.append(text)
            previous = flowing_text((previous, text))[-MAX_CONTEXT_CHARS:]
        else:
            _LOG.info("No speech recognized in file window %d of %d.", index, len(windows))
        if progress is not None:
            progress(index, len(windows))
    if cancel is not None and cancel.is_set():
        return ""
    if not parts:
        raise ServiceError(
            "No speech could be recognized in this recording. Check the audio and selected "
            "language; music or unclear vocals may not produce a transcript."
        )
    return flowing_text(parts)
