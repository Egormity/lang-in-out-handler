"""Growing, non-overlapping audio blocks whose earlier source text can be revised."""

import array
import sys
from collections.abc import Callable
from dataclasses import dataclass

from .audio_windows import BYTES_PER_SECOND, SAMPLE_RATE, pcm_to_wav, read_pcm
from .errors import ServiceError
from .text_utils import flowing_text

MAX_AUDIO_SECONDS = 30
MAX_PRIOR_CONTEXT_CHARS = 1500
QUIET_SECONDS = 0.4
SHORT_TAIL_SECONDS = 0.2
_SHORT_TAIL_BYTES = round(SHORT_TAIL_SECONDS * BYTES_PER_SECOND)
_MAX_BUFFER_BYTES = MAX_AUDIO_SECONDS * BYTES_PER_SECOND + _SHORT_TAIL_BYTES
_FRAME_SAMPLES = SAMPLE_RATE // 50  # 20 ms energy frames; not a speech/VAD model.
_QUIET_POWER = (0.0008 * 32768) ** 2


def _samples(pcm: bytes):
    samples = array.array("h", pcm)
    if sys.byteorder != "little":
        samples.byteswap()
    return samples


def _quiet_frame(samples) -> bool:
    return bool(samples) and sum(value * value for value in samples) < len(samples) * _QUIET_POWER


def quiet_audio(pcm: bytes) -> bool:
    """Detect quiet-only input without averaging a short audible tail into silence."""
    samples = _samples(pcm)
    return not samples or all(
        _quiet_frame(samples[start:start + _FRAME_SAMPLES])
        for start in range(0, len(samples), _FRAME_SAMPLES)
    )


def has_quiet_tail(pcm: bytes) -> bool:
    count = round(QUIET_SECONDS * SAMPLE_RATE)
    if len(pcm) < count * 2:
        return False
    return quiet_audio(pcm[-count * 2:])


@dataclass(frozen=True, slots=True)
class RecognitionWindow:
    block_id: int
    audio: bytes
    prior_context: str
    revision: int
    new_block: bool
    final: bool
    generation: int


class GrowingCaptionWindow:
    """Prepare one request per accepted chunk; commit its response before the next.

    Successful prefixes can be replaced under one block ID. Quiet endings and the
    context limit mark a block ready to freeze, retaining PCM until the next chunk
    so a tiny final tail can still extend it. A confirmed 30-second block allows at
    most 200 ms of tail slack. Empty ASR never erases accepted text.
    """

    def __init__(self, allocate_id: Callable[[], int], limit_seconds: float = 20):
        if not 0 < limit_seconds <= MAX_AUDIO_SECONDS:
            raise ValueError("Caption context must be greater than 0 and at most 30 seconds.")
        self.allocate_id = allocate_id
        self.limit_seconds = float(limit_seconds)
        self._generation = 0
        self._prior_context = ""
        self._clear_block()

    @property
    def duration_seconds(self) -> float:
        return len(self._pcm) / BYTES_PER_SECOND

    @property
    def prior_context(self) -> str:
        return self._prior_context

    @property
    def current_block_id(self) -> int | None:
        return self._block_id

    @property
    def revision(self) -> int:
        return self._revision

    @property
    def accepted_text(self) -> str:
        return self._text

    def _clear_block(self):
        self._pcm = b""
        self._block_id = None
        self._revision = 0
        self._accepted_revision = 0
        self._text = ""
        self._sealed = False

    def reset(self):
        self._generation += 1
        self._prior_context = ""
        self._clear_block()

    def _seal(self):
        if self._text:
            self._prior_context = flowing_text((self._prior_context, self._text))[
                -MAX_PRIOR_CONTEXT_CHARS:
            ]
        self._clear_block()

    def accept(self, audio: bytes) -> RecognitionWindow | None:
        try:
            pcm = read_pcm(audio)
        except ValueError as error:
            raise ServiceError(str(error)) from None
        if not pcm:
            return None
        if len(pcm) > MAX_AUDIO_SECONDS * BYTES_PER_SECOND:
            raise ServiceError("A caption audio chunk cannot exceed 30 seconds.")
        quiet = quiet_audio(pcm)
        current_complete = self._accepted_revision == self._revision
        if quiet:
            if not self._pcm:
                return None
            if current_complete:
                self._seal()
                return None
            # An earlier empty ASR response must not discard its audible frames
            # merely because the following chunk is silent. Retry with quiet context.
            space = MAX_AUDIO_SECONDS * BYTES_PER_SECOND - len(self._pcm)
            if space <= 0:
                if not self._text:
                    self._seal()
                    return None
                self._empty_limit_error()
            pcm = pcm[:space]  # Only excess quiet frames may be omitted from this retry.
        elif self._pcm:
            combined = len(self._pcm) + len(pcm)
            short_tail = (current_complete and len(pcm) <= _SHORT_TAIL_BYTES
                          and combined <= _MAX_BUFFER_BYTES)
            at_boundary = self._sealed or combined > self.limit_seconds * BYTES_PER_SECOND
            if current_complete and at_boundary and not short_tail:
                self._seal()
            elif combined > MAX_AUDIO_SECONDS * BYTES_PER_SECOND and not short_tail:
                if self._text:
                    self._empty_limit_error()
                # Music or other continuously nonquiet input can legitimately
                # produce no words. Do not stop capture indefinitely for that.
                self._seal()
        if self._block_id is None:
            self._block_id = self.allocate_id()
        self._pcm += pcm
        self._revision += 1
        self._sealed = False
        # An initial tiny fragment has no previous block to extend. Pad only the
        # submitted WAV, leaving captured PCM unchanged for the next growing prefix.
        payload = self._pcm + b"\0" * max(0, _SHORT_TAIL_BYTES - len(self._pcm))
        return RecognitionWindow(
            block_id=self._block_id,
            audio=pcm_to_wav(payload),
            prior_context=self._prior_context,
            revision=self._revision,
            new_block=self._revision == 1,
            final=(quiet or has_quiet_tail(self._pcm)
                   or self.duration_seconds >= self.limit_seconds),
            generation=self._generation,
        )

    def commit(self, request: RecognitionWindow, text: str) -> bool:
        """Accept a nonempty newer result; never erase earlier words with an empty response."""
        if (request.generation != self._generation or request.block_id != self._block_id
                or request.revision <= self._accepted_revision
                or request.revision > self._revision or not text.strip()):
            return False
        self._text = text.strip()
        self._accepted_revision = request.revision
        if request.final and request.revision == self._revision:
            self._sealed = True
        return True

    @staticmethod
    def _empty_limit_error():
        raise ServiceError(
            "Caption recognition returned no text for the latest audio. "
            "Capture stopped at the 30-second context limit (plus at most a 200 ms tail); "
            "earlier recognized text is preserved. Try another transcription model."
        )
