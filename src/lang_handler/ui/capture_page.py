"""Minimal dictation and continuous-caption workspaces."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QSplitter, QVBoxLayout, QWidget

from .audio_activity import AudioActivity
from .common import button, label, language_value
from .continuous_pane import ContinuousPane
from .dictation_entries import DictationEntries
from .icons import icon, icon_button
from .language_selectors import (
    replace_pane_heading,
    select_language,
    source_language_selector,
    target_language_selector,
)
from .tool_settings import ToolSettings, ToolSettingsView


class CapturePage(QWidget):
    capture_requested = Signal(bool)
    stop_requested = Signal()
    file_requested = Signal(str, bool)
    overlay_requested = Signal()
    options_changed = Signal(object)
    settings_saved = Signal(object)
    settings_requested = Signal()
    speech_requested = Signal(str)
    audio_requested = Signal(str, object)

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
        self.settings_view = ToolSettingsView(self.tool_settings, "Dictation" if is_input else "Captions", self)
        self.settings_button.clicked.connect(self.settings_requested)
        self.source_language = source_language_selector(getattr(settings, f"{mode}_language"))
        self.source_language.currentIndexChanged.connect(
            lambda: self.options_changed.emit({f"{mode}_language": language_value(self.source_language)})
        )
        self.level = AudioActivity()
        result_view = DictationEntries if is_input else ContinuousPane
        self.results = result_view("Transcript", "Your words appear here.")
        replace_pane_heading(self.results, self.source_language)
        self.results.speech_requested.connect(self.speech_requested)
        self.results.audio_requested.connect(self.audio_requested)
        self.translations = None
        self.target = None
        if is_input:
            layout.addWidget(self.results, 1)
        else:
            self.splitter = QSplitter()
            self.splitter.setChildrenCollapsible(False)
            self.splitter.addWidget(self.results)
            self.translations = ContinuousPane(settings.target_language, "Translation appears here.")
            self.target = target_language_selector(settings.target_language)
            self.target.currentTextChanged.connect(
                lambda value: self.options_changed.emit({"target_language": value})
            )
            replace_pane_heading(self.translations, self.target)
            self.translations.speech_requested.connect(self.speech_requested)
            self.translations.audio_requested.connect(self.audio_requested)
            self.splitter.addWidget(self.translations)
            self.splitter.setSizes([450, 450])
            layout.addWidget(self.splitter, 1)
        actions = QHBoxLayout()
        self.import_button = button("Open audio…")
        self.import_button.setObjectName("quiet")
        self.import_button.setIcon(icon("file"))
        self.import_button.clicked.connect(self._import)
        actions.addWidget(self.import_button)
        self.clear_button = icon_button("clear", "Clear transcript")
        self.clear_button.clicked.connect(self.clear)
        actions.addWidget(self.clear_button)
        actions.addStretch()
        actions.addWidget(self.level)
        self.start_button = button("Start dictation" if is_input else "Start captions", True)
        self.start_button.clicked.connect(lambda: self.capture_requested.emit(self.chunked()))
        self.stop_button = button("Stop dictation" if is_input else "Stop captions", True)
        self.stop_button.clicked.connect(self.stop_requested)
        self.stop_button.hide()
        self.stop_button.setEnabled(False)
        heading.insertWidget(1, self.start_button)
        heading.insertWidget(2, self.stop_button)
        layout.insertLayout(1, actions)
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
        select_language(self.source_language, getattr(settings, f"{self.mode}_language"), source=True)
        if self.translations:
            self.results.setVisible(settings.transcript_visible)
            self.translations.setVisible(settings.translation_visible)
            select_language(self.target, settings.target_language)
