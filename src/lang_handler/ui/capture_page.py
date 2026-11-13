"""Focused microphone and desktop-audio controls."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QSplitter,
    QWidget,
)

from .audio_activity import AudioActivity
from .common import button, label, title_block
from .entries import EntryList
from .sections import ExpandableSection, tool_layout
from .tool_settings import ToolSettings


class CapturePage(QWidget):
    capture_requested = Signal(bool)
    stop_requested = Signal()
    file_requested = Signal(str, bool)
    overlay_requested = Signal()
    options_changed = Signal(object)
    settings_saved = Signal(object)
    speech_requested = Signal(str)

    def __init__(self, mode: str, settings):
        super().__init__()
        self.mode = mode
        is_input = mode == "input"
        layout = tool_layout(self)
        header = QHBoxLayout()
        header.addWidget(
            title_block(
                "Voice input" if is_input else "Live captions",
                "Turn your voice into text, wherever you work."
                if is_input
                else "Follow the audio playing on your computer.",
            ),
            1,
        )
        if not is_input:
            self.show_overlay = button("Floating window")
            self.show_overlay.clicked.connect(self.overlay_requested)
            header.addWidget(self.show_overlay)
        layout.addLayout(header)
        actions = QHBoxLayout()
        self.start_button = button("Start recording" if is_input else "Start captions", True)
        self.stop_button = button("Stop")
        self.stop_button.setEnabled(False)
        actions.addWidget(self.start_button)
        actions.addWidget(self.stop_button)
        actions.addStretch()
        self.capture_type = QComboBox()
        self.capture_type.addItem("One recording", False)
        self.capture_type.addItem("Continuous chunks", True)
        self.capture_type.setToolTip(
            "One recording transcribes when you stop. Continuous mode transcribes each audio chunk."
        )
        self.capture_type.setCurrentIndex(int(getattr(settings, f"{mode}_chunked")))
        actions.addWidget(self.capture_type)
        self.import_button = button("Open audio…")
        actions.addWidget(self.import_button)
        layout.addLayout(actions)
        options = QHBoxLayout()
        self.option = None
        if not is_input:
            self.option = QCheckBox("Show translation")
            self.option.setChecked(settings.translation_visible)
            options.addWidget(self.option)
        options.addStretch()
        self.level = AudioActivity()
        options.addWidget(self.level)
        self.model_label = label(getattr(settings, f"{mode}_model"), True)
        options.addWidget(self.model_label)
        layout.addLayout(options)
        self.advanced = ExpandableSection("Settings")
        self.tool_settings = ToolSettings(mode, settings)
        self.tool_settings.saved.connect(self.settings_saved)
        self.advanced.body_layout.addWidget(self.tool_settings)
        layout.addWidget(self.advanced)
        self.results = EntryList("Transcript", "Your transcript appears here.")
        self.results.speech_requested.connect(self.speech_requested)
        self.translations = None
        if is_input:
            layout.addWidget(self.results, 1)
        else:
            self.splitter = QSplitter()
            self.splitter.setHandleWidth(12)
            self.splitter.addWidget(self.results)
            self.translations = EntryList("Translation", "Translated captions appear here.")
            self.translations.speech_requested.connect(self.speech_requested)
            self.splitter.addWidget(self.translations)
            self.splitter.setSizes([450, 450])
            self.translations.setVisible(settings.translation_visible)
            layout.addWidget(self.splitter, 1)
        footer = QHBoxLayout()
        footer.addWidget(label("Audio is processed by OpenAI.", True), 1)
        self.clear_button = button("Clear view")
        self.clear_button.clicked.connect(self.clear)
        footer.addWidget(self.clear_button)
        layout.addLayout(footer)
        self.start_button.clicked.connect(lambda: self.capture_requested.emit(self.chunked()))
        self.stop_button.clicked.connect(self.stop_requested)
        self.import_button.clicked.connect(self._import)
        if self.option:
            self.option.toggled.connect(self._option_changed)
        self.capture_type.currentIndexChanged.connect(
            lambda: self.options_changed.emit({f"{mode}_chunked": self.chunked()})
        )
        self.apply_settings(settings)

    def _option_changed(self, checked):
        if self.translations:
            self.translations.setVisible(checked)
        self.options_changed.emit({"translation_visible": checked, "translation_enabled": checked})

    def chunked(self) -> bool:
        return bool(self.capture_type.currentData())

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Transcribe audio",
            "",
            "Audio / video (*.wav *.mp3 *.m4a *.ogg *.flac *.webm *.mp4 *.mpeg);;All files (*)",
        )
        if path:
            self.file_requested.emit(path, self.chunked())

    def set_recording(self, active: bool):
        self.start_button.setEnabled(not active)
        self.import_button.setEnabled(not active)
        self.stop_button.setEnabled(active)
        self.capture_type.setEnabled(not active)
        self.level.set_recording(active)

    def clear(self):
        self.results.clear()
        if self.translations:
            self.translations.clear()

    def apply_settings(self, settings):
        self.capture_type.blockSignals(True)
        self.capture_type.setCurrentIndex(int(getattr(settings, f"{self.mode}_chunked")))
        self.capture_type.blockSignals(False)
        self.tool_settings.update_settings(settings)
        if self.option:
            self.option.blockSignals(True)
            self.option.setChecked(settings.translation_visible)
            self.option.blockSignals(False)
        self.model_label.setText(getattr(settings, f"{self.mode}_model"))
        if self.translations:
            self.translations.setVisible(settings.translation_visible)
            self.results.setVisible(settings.transcript_visible)
