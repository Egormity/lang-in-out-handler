"""A simple translation workspace with pronunciation beside each passage."""

from copy import deepcopy
from dataclasses import replace

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QSplitter, QVBoxLayout, QWidget

from .common import TextPane, button, label
from .icons import icon_button
from .language_selectors import replace_pane_heading, select_language, target_language_selector
from .tool_settings import ToolSettings, ToolSettingsView
from .translation_suggestion import TranslationSuggestion


class TranslatePage(QWidget):
    requested = Signal(str)
    automatic_requested = Signal(str)
    invalidated = Signal()
    settings_saved = Signal(object)
    settings_requested = Signal()
    options_changed = Signal(object)
    speech_requested = Signal(str)
    audio_requested = Signal(str, object)
    stop_requested = Signal()
    replay_requested = Signal(str)

    def __init__(self, settings):
        super().__init__()
        self.settings = deepcopy(settings)
        self._automatic_eligible = True
        self._setting_source = False
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._send_automatic)
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
        self.source.text.textChanged.connect(self._source_changed)
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
        self.run.clicked.connect(self.send)
        heading.insertWidget(1, self.run)
        self.apply_settings(settings)
        self.target.currentTextChanged.connect(self._target_changed)

    @staticmethod
    def _request_options(settings):
        values = (settings.translation_provider, settings.target_language, settings.api_proxy_url)
        if settings.translation_provider == "openai":
            values += (settings.translation_model, settings.translation_reasoning,
                       settings.translation_instructions)
        return values

    def _source_changed(self):
        if not self._setting_source:
            self._automatic_eligible = True
        self.timer.stop()
        self.suggestion.clear()
        self.invalidated.emit()
        if not self.source.text.toPlainText().strip():
            self.result.text.clear()
            self.result.set_pronunciation("")
        self._schedule()

    def _target_changed(self, value):
        self.settings = replace(self.settings, target_language=value)
        self.timer.stop()
        self.suggestion.clear()
        self.invalidated.emit()
        self.options_changed.emit({"target_language": value})
        self._schedule()

    def _schedule(self):
        if (self._automatic_eligible and self.settings.translation_auto_send
                and self.source.text.toPlainText().strip()):
            self.timer.start(self.settings.translation_debounce_ms)

    def _send_automatic(self):
        text = self.source.text.toPlainText()
        if self._automatic_eligible and self.settings.translation_auto_send and text.strip():
            self.automatic_requested.emit(text)

    def send(self):
        self._automatic_eligible = True
        self.timer.stop()
        self.requested.emit(self.source.text.toPlainText())

    def request_started(self, text):
        """Manual shortcuts and controller calls supersede this edit's pending timer."""
        if text == self.source.text.toPlainText():
            self._automatic_eligible = True
            self.timer.stop()

    def set_source_text(self, text, *, automatic=True):
        """Reading clipboard text aloud must not also send it for translation."""
        self.timer.stop()
        self._automatic_eligible = automatic
        self._setting_source = True
        try:
            self.source.text.setPlainText(text)
        finally:
            self._setting_source = False

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
        previous = self.settings
        changed = self._request_options(previous) != self._request_options(settings)
        pending = self.timer.isActive()
        self.settings = deepcopy(settings)
        self.tool_settings.update_settings(settings)
        if self.target.currentText() != settings.target_language:
            self.suggestion.clear()
        select_language(self.target, settings.target_language)
        if changed or (previous.translation_auto_send and not settings.translation_auto_send):
            self.timer.stop()
            self.invalidated.emit()
        if changed or (not previous.translation_auto_send and settings.translation_auto_send):
            self._schedule()
        elif pending and previous.translation_debounce_ms != settings.translation_debounce_ms:
            self.timer.stop()
            self._schedule()

    def set_busy(self, busy):
        self.run.setText("Translating…" if busy else "Translate")
        # A manual request for newer text can replace the waiting automatic request.
        self.run.setEnabled(True)
        self.suggestion.use_button.setEnabled(not busy)

    def _apply_correction(self, correction):
        self.source.text.setPlainText(correction)
        self.send()

    def shutdown(self):
        self.timer.stop()
        self.invalidated.emit()
