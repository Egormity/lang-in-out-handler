import io
import struct
import threading
import wave

import pytest

from lang_handler.audio_windows import (
    BYTES_PER_SECOND,
    duration_seconds,
    pcm_to_wav,
    read_pcm,
    split_wav,
)
from lang_handler.errors import ServiceError
from lang_handler.file_transcription import transcribe_file_once


def audio(seconds):
    return pcm_to_wav(b"\x04\x01" * int(16_000 * seconds))


class Recognition:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def transcribe(self, audio, model, language, instructions, *, context):
        self.calls.append((audio, model, language, instructions, context))
        result = next(self.responses)
        if isinstance(result, Exception):
            raise result
        return result


def test_audio_windows_preserve_every_frame_without_header_concatenation():
    pcm = bytes(range(256)) * 7600
    windows = list(split_wav(pcm_to_wav(pcm)))
    assert b"".join(read_pcm(window) for window in windows) == pcm
    assert all(1 <= duration_seconds(window) <= 30 for window in windows)
    assert len(windows) == 3


def test_tiny_tail_is_rebalanced_without_losing_frames():
    original = audio(30.05)
    windows = list(split_wav(original))
    assert [duration_seconds(window) for window in windows] == pytest.approx([29.05, 1])
    assert b"".join(map(read_pcm, windows)) == read_pcm(original)


@pytest.mark.parametrize("seconds", [float("nan"), float("inf"), 0, -1, 31])
def test_invalid_window_duration_is_rejected(seconds):
    with pytest.raises(ValueError, match="between 1 and 30"):
        list(split_wav(audio(1), seconds))


@pytest.mark.parametrize("channels,width,rate", [(2, 2, 16000), (1, 1, 16000), (1, 2, 48000)])
def test_noncanonical_audio_is_rejected(channels, width, rate):
    target = io.BytesIO()
    with wave.open(target, "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(width)
        output.setframerate(rate)
        output.writeframes(b"\x00" * 16)
    with pytest.raises(ValueError, match="16 kHz mono PCM16"):
        read_pcm(target.getvalue())


def test_invalid_and_truncated_audio_is_rejected():
    with pytest.raises(ValueError, match="valid PCM WAV"):
        read_pcm(b"not audio")
    with pytest.raises(ValueError, match="incomplete"):
        read_pcm(audio(1)[:-2])
    with pytest.raises(ValueError, match="two-byte"):
        pcm_to_wav(b"\x00")


def test_short_file_remains_one_request_with_original_settings():
    service = Recognition(["Hello."])
    updates = []
    result = transcribe_file_once(
        service, audio(5), "gpt-transcribe", "en", "Names: Alice.",
        progress=lambda done, total: updates.append((done, total)),
    )
    assert result == "Hello."
    assert service.calls[0][1:] == ("gpt-transcribe", "en", "Names: Alice.", "")
    assert duration_seconds(service.calls[0][0]) == 5
    assert updates == [(1, 1)]


def test_long_file_has_one_final_text_bounded_context_and_no_lyric_deduplication():
    first = "A" * 1700
    service = Recognition([first, "Sing again.", "Sing again."])
    updates = []
    result = transcribe_file_once(
        service, audio(61), "gpt-transcribe", "en", "Keep names.",
        progress=lambda done, total: updates.append((done, total)),
    )
    assert [duration_seconds(call[0]) for call in service.calls] == [30, 30, 1]
    assert all(call[1:4] == ("gpt-transcribe", "en", "Keep names.") for call in service.calls)
    assert service.calls[1][4] == "A" * 1500
    assert len(service.calls[2][4]) == 1500
    assert service.calls[2][4].endswith("Sing again.")
    assert result == first + " Sing again. Sing again."
    assert updates == [(1, 3), (2, 3), (3, 3)]


def test_empty_middle_window_preserves_last_context_and_advances_progress():
    service = Recognition(["こんにちは。", "♪…", "今日は。"])
    updates = []
    result = transcribe_file_once(
        service, audio(61), "gpt-transcribe", "ja",
        progress=lambda done, total: updates.append((done, total)),
    )
    assert result == "こんにちは。今日は。"
    assert service.calls[2][4] == "こんにちは。"
    assert updates == [(1, 3), (2, 3), (3, 3)]


@pytest.mark.parametrize("response", ["", "   ", "♪♫。…", "---"])
def test_all_empty_output_is_never_success(response):
    with pytest.raises(ServiceError, match="No speech could be recognized"):
        transcribe_file_once(Recognition([response]), audio(5), "gpt-transcribe")


def test_empty_audio_has_clear_error_without_network():
    service = Recognition([])
    with pytest.raises(ServiceError, match="No speech could be recognized"):
        transcribe_file_once(service, pcm_to_wav(b""), "gpt-transcribe")
    assert not service.calls


def test_cancellation_before_work_does_not_decode_or_send():
    cancel = threading.Event()
    cancel.set()
    service = Recognition([])
    assert transcribe_file_once(service, b"", "gpt-transcribe", cancel=cancel) == ""
    assert not service.calls


def test_cancel_during_first_request_discards_partial_file():
    cancel = threading.Event()
    service = Recognition(["partial"])
    original = service.transcribe

    def cancel_in_request(*args, **kwargs):
        cancel.set()
        return original(*args, **kwargs)

    service.transcribe = cancel_in_request
    updates = []
    assert transcribe_file_once(
        service, audio(61), "gpt-transcribe", cancel=cancel,
        progress=lambda *args: updates.append(args),
    ) == ""
    assert len(service.calls) == 1
    assert not updates


def test_failed_later_window_never_returns_partial_success():
    service = Recognition(["partial", ServiceError("request failed")])
    with pytest.raises(ServiceError, match="request failed"):
        transcribe_file_once(service, audio(61), "gpt-transcribe")
    assert len(service.calls) == 2


def test_cancel_at_final_progress_still_discards_output():
    cancel = threading.Event()
    service = Recognition(["finished"])
    assert transcribe_file_once(
        service, audio(5), "gpt-transcribe", cancel=cancel,
        progress=lambda *_: cancel.set(),
    ) == ""


def test_sample_duration_is_exact():
    pcm = struct.pack("<hhh", 100, -100, 0)
    assert duration_seconds(pcm_to_wav(pcm)) == len(pcm) / BYTES_PER_SECOND
