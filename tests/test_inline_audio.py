"""Speech files remain reusable and independently controllable without new API calls."""

import wave

import pytest
from PySide6.QtCore import Qt
from PySide6.QtMultimedia import QMediaPlayer

from lang_handler.ui.inline_audio import InlineAudio, audio_is_active, stop_all_audio
from lang_handler.ui.theme import STYLE


@pytest.fixture
def speech_file(tmp_path):
    path = tmp_path / "speech.wav"
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\0\0" * 32000)
    return path


def load_muted(qtbot, path):
    control = InlineAudio()
    qtbot.addWidget(control)
    control.set_audio(path, autoplay=False)
    control.audio_output.setMuted(True)
    qtbot.waitUntil(lambda: control.progress.maximum() == 2000)
    return control


def test_speak_becomes_player_and_playback_never_requests_generation(qtbot, speech_file):
    control = InlineAudio()
    qtbot.addWidget(control)
    control.show()
    requests = []
    control.requested.connect(lambda: requests.append(True))
    qtbot.mouseClick(control.speak, Qt.MouseButton.LeftButton)
    control.set_generating(True)
    assert not control.speak.isEnabled()
    control.set_audio(speech_file, autoplay=False)
    control.audio_output.setMuted(True)
    qtbot.waitUntil(lambda: control.progress.maximum() == 2000)
    assert control.speak.isHidden()
    assert control.controls.isVisible()
    assert control.time.text() == "0:00 / 0:02"
    control.speed.setCurrentIndex(control.speed.findData(1.5))
    assert control.player.playbackRate() == 1.5
    control.play_button.click()
    qtbot.waitUntil(lambda: control.player.playbackState() == QMediaPlayer.PlayingState)
    control.play_button.click()
    assert control.player.playbackState() == QMediaPlayer.PausedState
    control.progress.setValue(1000)
    assert control.player.position() == 1000
    assert control.time.text() == "0:01 / 0:02"
    control.play_button.click()
    qtbot.waitUntil(lambda: control.player.playbackState() == QMediaPlayer.PlayingState)
    assert requests == [True]
    assert control.path == str(speech_file)
    control.stop()


def test_only_one_inline_player_is_active_and_global_stop_preserves_files(qtbot, speech_file):
    first = load_muted(qtbot, speech_file)
    second = load_muted(qtbot, speech_file)
    first.play()
    qtbot.waitUntil(audio_is_active)
    second.play()
    qtbot.waitUntil(lambda: second.player.playbackState() == QMediaPlayer.PlayingState)
    assert first.player.playbackState() == QMediaPlayer.StoppedState
    assert audio_is_active()
    second.toggle_playback()
    assert not audio_is_active()
    second.play()
    stop_all_audio()
    assert not audio_is_active()
    assert first.path == second.path == str(speech_file)
    assert second.player.position() == 0


def test_reset_invalidates_pending_generation_and_restores_speak(qtbot, speech_file):
    control = load_muted(qtbot, speech_file)
    revision = control.revision
    control.speak.setAccessibleName("Speak original")
    control.speak.setToolTip("Read selected text, or the whole pane.")
    control.set_generating(True)
    control.reset()
    assert control.revision == revision + 1
    assert control.path == ""
    assert control.player.source().isEmpty()
    assert not control.speak.isHidden()
    assert control.speak.isEnabled()
    assert control.speak.accessibleName() == "Speak original"
    assert control.speak.toolTip() == "Read selected text, or the whole pane."
    assert control.controls.isHidden()
    assert control.width() == 36


def test_missing_file_reports_error_and_returns_to_generation_button(qtbot, tmp_path):
    control = InlineAudio()
    qtbot.addWidget(control)
    with qtbot.waitSignal(control.error) as error:
        control.set_audio(tmp_path / "deleted.wav")
    assert "no longer available" in error.args[0]
    assert control.path == ""
    assert control.player is None
    assert not control.speak.isHidden()


def test_player_fits_narrow_pane_and_speed_choices_are_bounded(qtbot, qapp, speech_file):
    previous_style = qapp.styleSheet()
    qapp.setStyleSheet(STYLE)
    try:
        control = load_muted(qtbot, speech_file)
        control.resize(220, 36)
        control.show()
        qtbot.wait(10)
        assert control.width() == 220
        assert control.speed.mapTo(control, control.speed.rect().topRight()).x() < 220
        assert control.progress.width() >= 36
        assert not control.speed.isEditable()
        assert [control.speed.itemData(i) for i in range(control.speed.count())] == [
            0.5, 0.75, 1.0, 1.25, 1.5, 2.0
        ]
        control.speed.showPopup()
        assert control.speed.view().window().width() <= 100
        control.speed.hidePopup()
        control.resize(144, 36)
        qtbot.wait(10)
        assert control.width() == 144
        assert control.time.isHidden()
        assert control.progress.width() >= 36
        assert control.speed.mapTo(control, control.speed.rect().topRight()).x() < 144
    finally:
        qapp.setStyleSheet(previous_style)
