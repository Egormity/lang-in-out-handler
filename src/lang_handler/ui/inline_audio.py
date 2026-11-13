"""Local, reusable speech playback beside the text that produced it."""

from pathlib import Path
from weakref import WeakSet

from PySide6.QtCore import QSignalBlocker, QSize, Qt, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QSlider, QWidget
from shiboken6 import isValid

from .dropdown import CompactComboBox
from .icons import icon, icon_button

_CONTROLS: WeakSet = WeakSet()


def audio_is_active() -> bool:
    return any(
        isValid(control)
        and control.player is not None
        and control.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        for control in list(_CONTROLS)
    )


def stop_all_audio(except_control=None):
    """Stop every live inline player, including players in floating windows."""
    for control in list(_CONTROLS):
        if control is not except_control and isValid(control):
            control.stop()


def _clock(milliseconds: int) -> str:
    seconds = max(0, milliseconds // 1000)
    return f"{seconds // 60}:{seconds % 60:02d}"


class _SpeedCombo(CompactComboBox):
    MAX_POPUP_WIDTH = 100


class InlineAudio(QWidget):
    """A speak button that becomes a seekable player when its WAV is ready.

    The owner handles generation and supplies the local file through set_audio.
    Playback controls never request generation or contact the API.
    """

    requested = Signal()
    active_changed = Signal(bool)
    error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.path = ""
        self.revision = 0
        self.player: QMediaPlayer | None = None
        self.audio_output: QAudioOutput | None = None
        self._generating = False
        self.setObjectName("inlineAudio")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(36)
        self.setFixedWidth(36)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.speak = icon_button("speak", "Speak")
        self.speak.clicked.connect(self.requested)
        layout.addWidget(self.speak)

        self.controls = QWidget(self)
        self.controls.setObjectName("inlineAudioControls")
        row = QHBoxLayout(self.controls)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        self.play_button = icon_button("play", "Play audio")
        self.play_button.setFixedSize(30, 32)
        self.play_button.clicked.connect(self.toggle_playback)
        row.addWidget(self.play_button)
        self.progress = QSlider(Qt.Orientation.Horizontal)
        self.progress.setObjectName("audioProgress")
        self.progress.setAccessibleName("Audio position")
        self.progress.setMinimumWidth(36)
        self.progress.setRange(0, 0)
        self.progress.setEnabled(False)
        self.progress.valueChanged.connect(self._seek)
        row.addWidget(self.progress, 1)
        self.time = QLabel("0:00 / 0:00")
        self.time.setObjectName("audioTime")
        self.time.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(self.time)
        self.speed = _SpeedCombo()
        self.speed.setObjectName("audioSpeed")
        self.speed.setAccessibleName("Playback speed")
        self.speed.setToolTip("Playback speed")
        self.speed.setMinimumContentsLength(0)
        self.speed.setFixedWidth(64)
        for rate in (0.5, 0.75, 1.0, 1.25, 1.5, 2.0):
            self.speed.addItem(f"{rate:g}×", rate)
        self.speed.setCurrentIndex(2)
        self.speed.currentIndexChanged.connect(self._change_speed)
        row.addWidget(self.speed)
        layout.addWidget(self.controls)
        self.controls.hide()
        _CONTROLS.add(self)

    def sizeHint(self):
        return QSize(270 if self.path else 36, 36)

    def minimumSizeHint(self):
        return QSize(144 if self.path else 36, 36)

    def resizeEvent(self, event):
        self.time.setVisible(bool(self.path) and event.size().width() >= 220)
        super().resizeEvent(event)

    def set_generating(self, generating: bool):
        was_generating = self._generating
        self._generating = generating
        self.speak.setEnabled(not generating)
        if generating and not was_generating:
            self._idle_tooltip = self.speak.toolTip()
            self._idle_accessible_name = self.speak.accessibleName()
            self.speak.setToolTip("Generating speech…")
            self.speak.setAccessibleName("Generating speech")
        elif was_generating and not generating:
            self.speak.setToolTip(self._idle_tooltip)
            self.speak.setAccessibleName(self._idle_accessible_name)

    def set_audio(self, path: str | Path, *, autoplay: bool = True):
        source = Path(path)
        self.set_generating(False)
        if not source.is_file():
            self.reset()
            self.error.emit("The generated audio file is no longer available. Generate it again.")
            return
        self.stop()
        self._ensure_player()
        self.path = str(source.resolve())
        self.speak.hide()
        self.controls.show()
        self.setMinimumWidth(144)
        self.setMaximumWidth(300)
        self.updateGeometry()
        self.player.setSource(QUrl.fromLocalFile(self.path))
        self.player.setPlaybackRate(float(self.speed.currentData()))
        if autoplay:
            self.play()

    def _ensure_player(self):
        if self.player is not None:
            return
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.player.durationChanged.connect(self._duration_changed)
        self.player.positionChanged.connect(self._position_changed)
        self.player.playbackStateChanged.connect(self._playback_changed)
        self.player.errorOccurred.connect(self._playback_error)
        # Qt 6.10+ keeps speech natural while changing speed on supported backends.
        if hasattr(self.player, "setPitchCompensation"):
            self.player.setPitchCompensation(True)

    def play(self):
        if not self.path or self.player is None:
            return
        stop_all_audio(except_control=self)
        if self.player.mediaStatus() == QMediaPlayer.MediaStatus.EndOfMedia:
            self.player.setPosition(0)
        self.player.play()

    def toggle_playback(self):
        if self.player is None:
            return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.play()

    def stop(self):
        if self.player is not None:
            self.player.stop()

    def reset(self):
        self.revision += 1
        self.stop()
        if self.player is not None:
            self.player.setSource(QUrl())
        self.path = ""
        self.set_generating(False)
        self.controls.hide()
        self.speak.show()
        self.setFixedWidth(36)
        self._duration_changed(0)
        self._position_changed(0)
        self.updateGeometry()

    def _change_speed(self):
        if self.player is not None:
            self.player.setPlaybackRate(float(self.speed.currentData()))

    def _duration_changed(self, duration: int):
        with QSignalBlocker(self.progress):
            self.progress.setRange(0, duration)
        self.progress.setEnabled(duration > 0)
        self._update_time()

    def _position_changed(self, position: int):
        if not self.progress.isSliderDown():
            with QSignalBlocker(self.progress):
                self.progress.setValue(position)
        self._update_time(position)

    def _seek(self, position: int):
        if self.player is not None:
            self.player.setPosition(position)
            self._update_time(position)

    def _update_time(self, position: int | None = None):
        if position is None:
            position = self.progress.value()
        self.time.setText(f"{_clock(position)} / {_clock(self.progress.maximum())}")
        self.progress.setToolTip(self.time.text())

    def _playback_changed(self, state):
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        title = "Pause audio" if playing else "Play audio"
        self.play_button.setIcon(icon("pause" if playing else "play"))
        self.play_button.setAccessibleName(title)
        self.play_button.setToolTip(title)
        self.active_changed.emit(playing)

    def _playback_error(self, error, message):
        if error == QMediaPlayer.Error.NoError:
            return
        self.reset()
        self.error.emit(f"Audio playback failed: {message or 'The audio could not be opened.'}")
