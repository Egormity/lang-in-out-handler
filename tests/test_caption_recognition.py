"""Growing audio reuses source identity while retaining every audible PCM frame."""

from dataclasses import FrozenInstanceError
from itertools import count

import pytest

from lang_handler.audio_windows import BYTES_PER_SECOND, pcm_to_wav, read_pcm
from lang_handler.caption_recognition import GrowingCaptionWindow, quiet_audio
from lang_handler.errors import ServiceError


def pcm(seconds, value=1000):
    sample = value.to_bytes(2, "little", signed=True)
    return sample * round(seconds * BYTES_PER_SECOND / 2)


def growing(limit=20):
    identities = count(1)
    return GrowingCaptionWindow(lambda: next(identities), limit)


def test_prefix_windows_replace_one_identity_and_preserve_exact_audio():
    window = growing()
    chunks = [pcm(5, value) for value in (1000, 2000, 3000, 4000)]
    requests = []
    for index, chunk in enumerate(chunks, 1):
        request = window.accept(pcm_to_wav(chunk))
        requests.append(request)
        assert request.block_id == 1
        assert request.revision == index
        assert request.new_block is (index == 1)
        assert request.prior_context == ""
        assert read_pcm(request.audio) == b"".join(chunks[:index])
        assert request.final is (index == 4)
        assert window.commit(request, f"Revised whole passage {index}")
    with pytest.raises(FrozenInstanceError):
        requests[0].revision = 999
    next_request = window.accept(pcm_to_wav(pcm(5, 5000)))
    assert next_request.block_id == 2
    assert next_request.prior_context == "Revised whole passage 4"
    assert read_pcm(next_request.audio) == pcm(5, 5000)


def test_non_aligned_chunk_lengths_partition_without_overlap_or_dropped_frames():
    window = growing()
    chunks = [pcm(7, value) for value in (1000, 2000, 3000, 4000)]
    chunks.append(pcm(0.05, 5000))
    last_for_block = {}
    for index, chunk in enumerate(chunks):
        request = window.accept(pcm_to_wav(chunk))
        last_for_block[request.block_id] = request
        assert window.commit(request, f"block text {index}")
    reconstructed = b"".join(read_pcm(request.audio) for request in last_for_block.values())
    assert reconstructed == b"".join(chunks)
    assert all(len(read_pcm(request.audio)) <= 30 * BYTES_PER_SECOND
               for request in last_for_block.values())


def test_single_long_capture_chunk_is_not_truncated_to_shorter_context_limit():
    window = growing(20)
    chunk = pcm(30)
    request = window.accept(pcm_to_wav(chunk))
    assert read_pcm(request.audio) == chunk
    assert request.final
    assert window.commit(request, "Thirty seconds of speech")
    following = window.accept(pcm_to_wav(pcm(5)))
    assert following.block_id != request.block_id
    assert following.prior_context == "Thirty seconds of speech"


def test_quiet_input_seals_committed_source_without_another_asr_call():
    window = growing()
    assert window.accept(pcm_to_wav(pcm(5, 0))) is None
    request = window.accept(pcm_to_wav(pcm(5)))
    assert window.commit(request, "Finished sentence.")
    assert window.accept(pcm_to_wav(pcm(5, 0))) is None
    assert window.duration_seconds == 0
    following = window.accept(pcm_to_wav(pcm(1)))
    assert following.block_id != request.block_id
    assert following.prior_context == "Finished sentence."


def test_quiet_tail_preserves_audio_and_only_seals_after_successful_commit():
    window = growing()
    chunk = pcm(4.5) + pcm(0.5, 0)
    request = window.accept(pcm_to_wav(chunk))
    assert request.final
    assert read_pcm(request.audio) == chunk
    assert window.duration_seconds == 5
    assert window.commit(request, "Sentence with a quiet ending.")
    following = window.accept(pcm_to_wav(pcm(5)))
    assert following.block_id != request.block_id


def test_short_audible_tail_is_not_hidden_by_averaging_over_long_silence():
    window = growing()
    chunk = pcm(4.99, 0) + pcm(0.01, 1000)
    assert not quiet_audio(chunk)
    request = window.accept(pcm_to_wav(chunk))
    assert request is not None
    assert not request.final
    assert read_pcm(request.audio) == chunk


def test_empty_response_retains_prior_words_and_all_audio_for_next_context():
    window = growing()
    first = window.accept(pcm_to_wav(pcm(5, 1000)))
    assert window.commit(first, "Earlier incomplete sentence")
    second = window.accept(pcm_to_wav(pcm(5, 2000)))
    assert not window.commit(second, "  ")
    assert window.accepted_text == "Earlier incomplete sentence"
    assert window.duration_seconds == 10
    retry = window.accept(pcm_to_wav(pcm(5, 0)))
    assert retry.block_id == first.block_id
    assert read_pcm(retry.audio) == pcm(5, 1000) + pcm(5, 2000) + pcm(5, 0)
    assert window.commit(retry, "A corrected complete sentence")
    following = window.accept(pcm_to_wav(pcm(5)))
    assert following.block_id != first.block_id
    assert following.prior_context == "A corrected complete sentence"


@pytest.mark.parametrize("next_value", [0, 1000])
def test_partly_recognized_audio_is_not_silently_discarded_at_hard_limit(next_value):
    window = growing()
    for index in range(6):
        request = window.accept(pcm_to_wav(pcm(5)))
        assert request.block_id == 1
        if index == 0:
            assert window.commit(request, "Earlier recognized words")
        else:
            assert not window.commit(request, "")
    assert window.duration_seconds == 30
    with pytest.raises(ServiceError, match="30-second context limit"):
        window.accept(pcm_to_wav(pcm(5, next_value)))
    assert window.duration_seconds == 30
    assert window.current_block_id == 1


def test_context_is_bounded_and_reset_cannot_commit_old_requests():
    window = growing(5)
    first = window.accept(pcm_to_wav(pcm(5)))
    assert window.commit(first, "あ" * 2000)
    assert window.prior_context == ""  # Current block remains reopenable for its final tail.
    second = window.accept(pcm_to_wav(pcm(1)))
    assert len(window.prior_context) == 1500
    assert second.prior_context == "あ" * 1500
    window.reset()
    assert window.prior_context == ""
    assert window.duration_seconds == 0
    assert not window.commit(second, "must not return")
    third = window.accept(pcm_to_wav(pcm(1)))
    assert third.block_id != second.block_id
    assert third.prior_context == ""


def test_invalid_audio_and_oversize_chunks_fail_without_mutating_window():
    window = growing()
    with pytest.raises(ServiceError, match="valid PCM WAV"):
        window.accept(b"not a WAV")
    with pytest.raises(ServiceError, match="cannot exceed 30"):
        window.accept(pcm_to_wav(pcm(31)))
    assert window.duration_seconds == 0


def test_final_short_tail_extends_completed_block_instead_of_tiny_asr_request():
    window = growing()
    for _ in range(4):
        prefix = window.accept(pcm_to_wav(pcm(5, 1000)))
        assert window.commit(prefix, "The earlier incomplete ending")
    assert prefix.final
    assert window.duration_seconds == 20
    assert window.prior_context == ""
    tail = window.accept(pcm_to_wav(pcm(0.08, 2000)))
    assert tail.block_id == prefix.block_id
    assert tail.revision == prefix.revision + 1
    assert tail.final
    assert read_pcm(tail.audio) == pcm(20, 1000) + pcm(0.08, 2000)
    assert tail.prior_context == ""
    assert window.commit(tail, "The corrected complete ending")
    following = window.accept(pcm_to_wav(pcm(5, 3000)))
    assert following.block_id != tail.block_id
    assert following.prior_context == "The corrected complete ending"
    assert read_pcm(following.audio) == pcm(5, 3000)


def test_confirmed_thirty_second_block_uses_bounded_slack_for_eighty_ms_tail():
    window = growing(30)
    first = window.accept(pcm_to_wav(pcm(30, 1000)))
    assert window.commit(first, "Earlier incomplete ending")
    tail = window.accept(pcm_to_wav(pcm(0.08, 2000)))
    assert tail.block_id == first.block_id
    assert read_pcm(tail.audio) == pcm(30, 1000) + pcm(0.08, 2000)
    assert window.duration_seconds == pytest.approx(30.08)
    assert window.commit(tail, "Corrected ending")
    following = window.accept(pcm_to_wav(pcm(5, 3000)))
    assert following.block_id != first.block_id
    assert following.prior_context == "Corrected ending"


def test_tail_slack_is_bounded_across_repeated_tiny_fragments():
    window = growing(30)
    first = window.accept(pcm_to_wav(pcm(30)))
    assert window.commit(first, "Initial words")
    tail = window.accept(pcm_to_wav(pcm(0.2, 2000)))
    assert tail.block_id == first.block_id
    assert window.duration_seconds == pytest.approx(30.2)
    assert window.commit(tail, "Completed words")
    following = window.accept(pcm_to_wav(pcm(0.08, 3000)))
    assert following.block_id != first.block_id
    assert window.duration_seconds == pytest.approx(0.08)
    assert read_pcm(following.audio) == pcm(0.08, 3000) + pcm(0.12, 0)


def test_standalone_tiny_input_pads_api_payload_without_changing_captured_frames():
    window = growing()
    first = window.accept(pcm_to_wav(pcm(0.08, 1000)))
    assert window.duration_seconds == pytest.approx(0.08)
    assert read_pcm(first.audio) == pcm(0.08, 1000) + pcm(0.12, 0)
    assert window.commit(first, "Beginning")
    following = window.accept(pcm_to_wav(pcm(1, 2000)))
    assert following.block_id == first.block_id
    assert read_pcm(following.audio) == pcm(0.08, 1000) + pcm(1, 2000)


@pytest.mark.parametrize("next_value", [0, 1000])
def test_all_empty_thirty_second_block_does_not_stop_music_or_waiting_input(next_value):
    window = growing()
    for _ in range(6):
        request = window.accept(pcm_to_wav(pcm(5)))
        assert not window.commit(request, "")
    assert window.duration_seconds == 30
    following = window.accept(pcm_to_wav(pcm(5, next_value)))
    assert window.prior_context == ""
    if next_value:
        assert following.block_id != request.block_id
        assert read_pcm(following.audio) == pcm(5, next_value)
        assert window.duration_seconds == 5
    else:
        assert following is None
        assert window.duration_seconds == 0


@pytest.mark.parametrize("limit", [1, 2, 3, 4])
def test_positive_context_shorter_than_one_capture_chunk_preserves_whole_chunk(limit):
    window = growing(limit)
    request = window.accept(pcm_to_wav(pcm(5)))
    assert request.final
    assert read_pcm(request.audio) == pcm(5)
    assert window.commit(request, "Complete capture chunk")
