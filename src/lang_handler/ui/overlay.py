"""Minimal floating captions; appearance and visibility live on the captions page."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSplitter, QVBoxLayout, QWidget

from ..results import TranslationResult
from ..window_pin import WindowPin
from .common import button, label
from .entries import EntryList
from .theme import STYLE


class CaptionOverlay(QWidget):
    settings_changed = Signal(object)
    stop_requested = Signal()
    speech_requested = Signal(str)
    speech_stop_requested = Signal()

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.setWindowTitle("Lang In/Out · Captions")
        self.setWindowFlags(Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setStyleSheet(STYLE)
        self.resize(900, 330)
        self.setMinimumSize(460, 200)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 8)
        layout.setSpacing(5)
        toolbar = QHBoxLayout()
        toolbar.addWidget(label("Live captions", True))
        toolbar.addStretch()
        self.stop_audio_button = button("Stop audio")
        self.stop_audio_button.clicked.connect(self.speech_stop_requested)
        self.stop_audio_button.hide()
        self.clear_button = button("Clear")
        self.clear_button.setToolTip("Clear visible captions. Recording and saved history continue.")
        self.clear_button.clicked.connect(self.clear)
        self.hide_button = button("Hide")
        self.hide_button.clicked.connect(self.hide)
        self.stop_button = button("Stop")
        self.stop_button.setToolTip("Stop capturing system audio.")
        self.stop_button.clicked.connect(self.stop_requested)
        for control in (
            self.stop_audio_button, self.clear_button, self.hide_button, self.stop_button
        ):
            control.setObjectName("quiet")
            control.setFocusPolicy(Qt.FocusPolicy.TabFocus)
            toolbar.addWidget(control)
        layout.addLayout(toolbar)
        self.pin_status = QLabel()
        self.pin_status.setObjectName("muted")
        self.pin_status.setWordWrap(True)
        self.pin_status.hide()
        layout.addWidget(self.pin_status)
        self.splitter = QSplitter()
        self.transcript = EntryList("Transcript", "Listening for speech…", compact=True)
        self.translation = EntryList("Translation", "Translated captions appear here.", compact=True)
        for pane in (self.transcript, self.translation):
            pane.speech_requested.connect(self.speech_requested)
            self.splitter.addWidget(pane)
        self.splitter.setSizes([450, 450])
        layout.addWidget(self.splitter, 1)
        self.empty = label("Choose a caption pane in Live captions → Settings.", True)
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty, 1)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setObjectName("muted")
        self.status.hide()
        layout.addWidget(self.status)
        self.pin_control = WindowPin(self)
        self.pin_control.message.connect(self._pin_message)
        self.update_settings(settings)

    def _pin_message(self, message):
        self.pin_status.setText(message)
        self.pin_status.setVisible(bool(message))

    def showEvent(self, event):
        super().showEvent(event)
        self.pin_control.on_show()

    def update_settings(self, settings):
        self.settings = settings
        self.transcript.setVisible(settings.transcript_visible)
        self.translation.setVisible(settings.translation_visible)
        any_visible = settings.transcript_visible or settings.translation_visible
        self.splitter.setVisible(any_visible)
        self.empty.setVisible(not any_visible)
        self.setWindowOpacity(settings.overlay_opacity)
        for pane in (self.transcript, self.translation):
            pane.set_text_size(settings.font_size)
        enabled = getattr(settings, "overlay_on_top", True)
        if not self.pin_control.verified or self.pin_control.desired != enabled:
            self.pin_control.request(enabled)

    def append_caption(self, text: str, translation="", *, segment_id=None):
        result = translation if isinstance(translation, TranslationResult) else TranslationResult(translation)
        self.transcript.append(text, result.source_pronunciation, segment_id=segment_id)
        self.translation.append(result.translation, result.translation_pronunciation)

    def annotate_translation(self, segment_id, result):
        if self.transcript.set_pronunciation_for(segment_id, result.source_pronunciation):
            self.translation.append(result.translation, result.translation_pronunciation)

    def set_status(self, text: str):
        self.status.setText(text)
        self.status.setVisible(text not in ("", "Ready", "Listening…", "Listening to system audio…"))

    def set_speech_active(self, active: bool):
        self.stop_audio_button.setVisible(active)

    def clear(self):
        self.transcript.clear()
        self.translation.clear()

    def closeEvent(self, event):
        # Closing hides the overlay; the running session is controlled by Stop.
        self.pin_control.stop()
        self.hide()
        event.ignore()
