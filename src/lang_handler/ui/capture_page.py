"""Minimal dictation and continuous-caption workspaces."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QSplitter, QVBoxLayout, QWidget

from .audio_activity import AudioActivity
from .common import button, label, language_combo, language_value
from .continuous_pane import ContinuousPane
from .icons import icon, icon_button
from .tool_settings import ToolSettings, ToolSettingsDialog


class CapturePage(QWidget):
    capture_requested = Signal(bool)
    stop_requested = Signal()
    file_requested = Signal(str, bool)
    overlay_requested = Signal()
    options_changed = Signal(object)
    settings_saved = Signal(object)
    speech_requested = Signal(str)

    def __init__(self, mode, settings):
        super().__init__()
        self.mode, self.settings = mode, settings
        self.recording = False
        is_input = mode == "input"
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(20)
        heading = QHBoxLayout()
        title = label("Dictate" if is_input else "Captions")
        title.setObjectName("title")
        heading.addWidget(title, 1)
        if not is_input:
            self.show_overlay = button("Float")
            self.show_overlay.setObjectName("quiet")
            self.show_overlay.setIcon(icon("float"))
            self.show_overlay.clicked.connect(self.overlay_requested)
            heading.addWidget(self.show_overlay)
        self.settings_button = icon_button("settings", "Dictation settings" if is_input else "Caption settings")
        heading.addWidget(self.settings_button)
        layout.addLayout(heading)
        self.tool_settings = ToolSettings(mode, settings)
        self.tool_settings.saved.connect(self.settings_saved)
        self.settings_dialog = ToolSettingsDialog(self.tool_settings, "Dictation" if is_input else "Captions", self)
        self.settings_button.clicked.connect(self.settings_dialog.show_settings)
        controls = QHBoxLayout()
        self.source_language = language_combo(getattr(settings, f"{mode}_language"))
        self.source_language.setFixedWidth(180)
        self.source_language.setAccessibleName("Spoken language")
        self.source_language.currentIndexChanged.connect(
            lambda: self.options_changed.emit({f"{mode}_language": language_value(self.source_language)})
        )
        controls.addWidget(self.source_language)
        controls.addStretch()
        self.level = AudioActivity()
        controls.addWidget(self.level)
        layout.addLayout(controls)
        self.results = ContinuousPane("Transcript", "Your words appear here.")
        self.results.speech_requested.connect(self.speech_requested)
        self.translations = None
        if is_input:
            layout.addWidget(self.results, 1)
        else:
            self.splitter = QSplitter()
            self.splitter.setChildrenCollapsible(False)
            self.splitter.addWidget(self.results)
            self.translations = ContinuousPane(settings.target_language, "Translation appears here.")
            self.translations.speech_requested.connect(self.speech_requested)
            self.splitter.addWidget(self.translations)
            self.splitter.setSizes([450, 450])
            layout.addWidget(self.splitter, 1)
        footer = QHBoxLayout()
        self.import_button = button("Open audio…")
        self.import_button.setObjectName("quiet")
        self.import_button.setIcon(icon("file"))
        self.import_button.clicked.connect(self._import)
        footer.addWidget(self.import_button)
        self.clear_button = icon_button("clear", "Clear transcript")
        self.clear_button.clicked.connect(self.clear)
        footer.addWidget(self.clear_button)
        footer.addStretch()
        self.start_button = button("Start dictation" if is_input else "Start captions", True)
        self.start_button.clicked.connect(lambda: self.capture_requested.emit(self.chunked()))
        self.stop_button = button("Stop dictation" if is_input else "Stop captions", True)
        self.stop_button.clicked.connect(self.stop_requested)
        self.stop_button.hide()
        self.stop_button.setEnabled(False)
        footer.addWidget(self.start_button)
        footer.addWidget(self.stop_button)
        layout.addLayout(footer)
        self.apply_settings(settings)

    def chunked(self):
        return getattr(self.settings, f"{self.mode}_chunked")

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Transcribe audio", "",
            "Audio / video (*.wav *.mp3 *.m4a *.ogg *.flac *.webm *.mp4 *.mpeg);;All files (*)",
        )
        if path:
            self.file_requested.emit(path, self.chunked())

    def set_recording(self, active):
        self.recording = active
        self.start_button.setVisible(not active)
        self.start_button.setEnabled(not active)
        self.stop_button.setVisible(active)
        self.stop_button.setEnabled(active)
        self.import_button.setEnabled(not active)
        self.source_language.setEnabled(not active)
        self.level.set_recording(active)

    def clear(self):
        self.results.clear()
        if self.translations:
            self.translations.clear()

    def apply_settings(self, settings):
        self.settings = settings
        self.tool_settings.update_settings(settings)
        self.source_language.blockSignals(True)
        self.source_language.setCurrentIndex(max(0, self.source_language.findData(getattr(settings, f"{self.mode}_language"))))
        self.source_language.blockSignals(False)
        self.results.heading.setText(self.source_language.currentText() if self.mode == "output" else "Transcript")
        if self.translations:
            self.results.setVisible(settings.transcript_visible)
            self.translations.setVisible(settings.translation_visible)
            self.translations.heading.setText(settings.target_language)
