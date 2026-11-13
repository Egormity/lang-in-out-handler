"""A compact, pinnable pair of continuous caption documents."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSplitter, QVBoxLayout, QWidget

from ..results import TranslationResult
from ..window_pin import WindowPin
from .common import button, label
from .continuous_pane import ContinuousPane
from .icons import icon_button
from .theme import STYLE


class CaptionOverlay(QWidget):
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
        self.resize(850, 310)
        self.setMinimumSize(460, 230)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 8)
        layout.setSpacing(4)
        toolbar = QHBoxLayout()
        toolbar.addWidget(label("Captions", True), 1)
        self.stop_audio_button = icon_button("stop", "Stop audio")
        self.stop_audio_button.clicked.connect(self.speech_stop_requested)
        self.stop_audio_button.hide()
        self.clear_button = icon_button("clear", "Clear captions")
        self.clear_button.clicked.connect(self.clear)
        self.hide_button = icon_button("close", "Hide captions")
        self.hide_button.clicked.connect(self.hide)
        self.stop_button = button("Stop")
        self.stop_button.setObjectName("quiet")
        self.stop_button.setAccessibleName("Stop captions")
        self.stop_button.clicked.connect(self.stop_requested)
        for control in (self.stop_audio_button, self.clear_button, self.stop_button, self.hide_button):
            toolbar.addWidget(control)
        layout.addLayout(toolbar)
        self.pin_status = label("", True)
        self.pin_status.hide()
        layout.addWidget(self.pin_status)
        self.splitter = QSplitter()
        self.splitter.setChildrenCollapsible(False)
        self.transcript = ContinuousPane("Transcript", "Listening…", compact=True)
        self.translation = ContinuousPane("Translation", "", compact=True)
        for pane in (self.transcript, self.translation):
            pane.speech_requested.connect(self.speech_requested)
            self.splitter.addWidget(pane)
        self.splitter.setSizes([420, 420])
        layout.addWidget(self.splitter, 1)
        self.empty = label("Choose a visible pane in Caption settings.", True)
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
        self.transcript.heading.setText({"ja": "Japanese", "en": "English", "ru": "Russian"}.get(settings.output_language, "Transcript"))
        self.translation.heading.setText(settings.target_language)
        visible = settings.transcript_visible or settings.translation_visible
        self.splitter.setVisible(visible)
        self.empty.setVisible(not visible)
        self.setWindowOpacity(settings.overlay_opacity)
        for pane in (self.transcript, self.translation):
            pane.set_text_size(settings.font_size)
        if not self.pin_control.verified or self.pin_control.desired != settings.overlay_on_top:
            self.pin_control.request(settings.overlay_on_top)

    def append_caption(self, text, translation="", *, segment_id=None):
        result = translation if isinstance(translation, TranslationResult) else TranslationResult(translation)
        self.transcript.append(text, result.source_pronunciation, segment_id=segment_id)
        self.translation.append(result.translation, result.translation_pronunciation, segment_id=segment_id)

    def annotate_translation(self, segment_id, result):
        if self.transcript.revise(segment_id, pronunciation=result.source_pronunciation):
            self.translation.upsert(segment_id, result.translation, result.translation_pronunciation)

    def set_status(self, text):
        self.status.setText(text)
        self.status.setVisible(text not in ("", "Ready", "Listening…", "Listening to system audio…"))

    def set_speech_active(self, active):
        self.stop_audio_button.setVisible(active)

    def clear(self):
        self.transcript.clear()
        self.translation.clear()

    def closeEvent(self, event):
        self.pin_control.stop()
        self.hide()
        event.ignore()
