"""A simple translation workspace with pronunciation beside each passage."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QSplitter, QVBoxLayout, QWidget

from .common import TextPane, button, label
from .icons import icon_button
from .language_selectors import replace_pane_heading, select_language, target_language_selector
from .tool_settings import ToolSettings, ToolSettingsView
from .translation_suggestion import TranslationSuggestion


class TranslatePage(QWidget):
    requested = Signal(str)
    settings_saved = Signal(object)
    settings_requested = Signal()
    options_changed = Signal(object)
    speech_requested = Signal(str)
    audio_requested = Signal(str, object)
    stop_requested = Signal()
    replay_requested = Signal(str)

    def __init__(self, settings):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(20)
        heading = QHBoxLayout()
        title = label("Translate")
        title.setObjectName("title")
        heading.addWidget(title, 1)
        self.settings_button = icon_button("settings", "Translation settings")
        heading.addWidget(self.settings_button)
        layout.addLayout(heading)
        self.tool_settings = ToolSettings("translate", settings)
        self.tool_settings.saved.connect(self.settings_saved)
        self.settings_view = ToolSettingsView(self.tool_settings, "Translation", self)
        self.settings_button.clicked.connect(self.settings_requested)
        self.target = target_language_selector(settings.target_language)
        self.splitter = QSplitter()
        self.splitter.setChildrenCollapsible(False)
        self.source = TextPane("Original", "Type or paste text…", False)
        self.result = TextPane("Translation", "Your translation appears here.", False)
        self.suggestion = TranslationSuggestion()
        self.source.content_layout.insertWidget(2, self.suggestion)
        self.suggestion.applied.connect(self._apply_correction)
        self.source.text.textChanged.connect(self.suggestion.clear)
        self.target.currentTextChanged.connect(self.suggestion.clear)
        replace_pane_heading(self.result, self.target)
        self.speak_original, self.speak_translation = self.source.speak, self.result.speak
        self.source.speech_requested.connect(self.speech_requested)
        self.result.speech_requested.connect(self.speech_requested)
        self.source.audio_requested.connect(self.audio_requested)
        self.result.audio_requested.connect(self.audio_requested)
        self.splitter.addWidget(self.source)
        self.splitter.addWidget(self.result)
        self.splitter.setSizes([450, 450])
        layout.addWidget(self.splitter, 1)
        self.run = button("Translate", True)
        self.run.clicked.connect(lambda: self.requested.emit(self.source.text.toPlainText()))
        heading.insertWidget(1, self.run)
        self.apply_settings(settings)
        self.target.currentTextChanged.connect(lambda value: self.options_changed.emit({"target_language": value}))

    def set_result(self, result, source_text=None, target_language=None):
        if source_text is not None and self.source.text.toPlainText() != source_text:
            return False
        if target_language is not None and self.target.currentText() != target_language:
            return False
        self.result.text.setPlainText(result.translation)
        self.source.set_pronunciation(result.source_pronunciation)
        self.result.set_pronunciation(result.translation_pronunciation)
        self.suggestion.set_suggestion(result.source_correction, self.source.text.toPlainText())
        return True

    def apply_settings(self, settings):
        self.tool_settings.update_settings(settings)
        if self.target.currentText() != settings.target_language:
            self.suggestion.clear()
        select_language(self.target, settings.target_language)

    def set_busy(self, busy):
        self.run.setEnabled(not busy)
        self.suggestion.use_button.setEnabled(not busy)

    def _apply_correction(self, correction):
        self.source.text.setPlainText(correction)
        self.requested.emit(correction)
