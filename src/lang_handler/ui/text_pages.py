"""A simple translation workspace with pronunciation beside each passage."""

from copy import deepcopy
from dataclasses import replace

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QSplitter, QVBoxLayout, QWidget

from .common import TextPane, button, label, language_value
from .icons import icon_button
from .language_selectors import (
    replace_pane_heading,
    select_language,
    source_language_selector,
    target_language_selector,
)
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
        self._swapping = False
        self._detected_source = ""
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
        self.source_language = source_language_selector(settings.translation_source_language)
        self.source_language.setAccessibleName("Input language")
        self.source_language.setToolTip("Choose the input language, or detect it automatically.")
        self.swap_button = icon_button("swap", "Swap languages and texts")
        self.swap_button.setFixedSize(30, 30)
        self.swap_button.clicked.connect(self.swap)
        source_header = QHBoxLayout()
        source_header.addWidget(self.source_language)
        source_header.addStretch()
        source_header.addWidget(self.swap_button)
        self.source.layout().removeWidget(self.source.heading)
        self.source.heading.hide()
        self.source.layout().insertLayout(0, source_header)
        self.suggestion = TranslationSuggestion()
        self.source.content_layout.insertWidget(2, self.suggestion)
        self.suggestion.applied.connect(self._apply_correction)
        self.source.text.textChanged.connect(self._source_changed)
        self.result.text.textChanged.connect(self._update_swap)
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
        self.source_language.currentIndexChanged.connect(self._language_changed)

    @staticmethod
    def _request_options(settings):
        values = (settings.translation_provider, settings.translation_source_language,
                  settings.target_language, settings.api_proxy_url)
        if settings.translation_provider == "openai":
            values += (settings.translation_model, settings.translation_reasoning,
                       settings.translation_instructions)
        return values

    def _source_changed(self):
        if not self._setting_source:
            self._automatic_eligible = True
        self._invalidate_result()
        if not self.source.text.toPlainText().strip():
            self.result.text.clear()
            self.result.set_pronunciation("")
        self._schedule()

    def _target_changed(self, value):
        self._change_language({"target_language": value})

    def _language_changed(self):
        self._change_language({"translation_source_language": language_value(self.source_language)})

    def _change_language(self, patch):
        self.settings = replace(self.settings, **patch)
        self._invalidate_result()
        self.options_changed.emit(patch)
        self._schedule()

    def _invalidate_result(self):
        self.timer.stop()
        self._detected_source = ""
        self.suggestion.clear()
        for pane in (self.source, self.result):
            pane.set_pronunciation("")
            pane.audio.reset()
            pane.speak.setEnabled(bool(pane.text.toPlainText().strip()))
        self.invalidated.emit()
        self._update_swap()

    def _swap_languages(self):
        source_code = language_value(self.source_language) or self._detected_source
        source_index = self.target.findData(source_code) if source_code else -1
        target_code = language_value(self.target)
        if source_index < 0 or not target_code:
            return None
        return {"translation_source_language": target_code,
                "target_language": self.target.itemText(source_index)}

    def _update_swap(self):
        has_result = bool(self.result.text.toPlainText().strip())
        languages = self._swap_languages()
        self.swap_button.setEnabled(has_result and languages is not None)
        self.swap_button.setToolTip(
            "Translate some text before swapping." if not has_result else
            "Choose an input and output language before swapping." if languages is None else
            "Swap languages and texts, then translate."
        )

    def swap(self):
        patch = self._swap_languages()
        source, translated = self.source.text.toPlainText(), self.result.text.toPlainText()
        if patch is None or not translated.strip():
            return
        previous = self._request_options(self.settings)
        detected = self._detected_source
        languages_changed = any(getattr(self.settings, key) != value for key, value in patch.items())
        self._swapping = True
        try:
            self.settings = replace(self.settings, **patch)
            self._invalidate_result()
            # Save both languages as one transaction. A failed save synchronously
            # restores committed settings, so leave the two texts untouched.
            if languages_changed:
                self.options_changed.emit(patch)
            if any(getattr(self.settings, key) != value for key, value in patch.items()):
                if (self._request_options(self.settings) == previous
                        and self.source.text.toPlainText() == source
                        and self.result.text.toPlainText() == translated):
                    self._detected_source = detected
                return
            select_language(self.source_language, patch["translation_source_language"], source=True)
            select_language(self.target, patch["target_language"])
            self.set_source_text(translated)
            self.result.text.setPlainText(source)
        finally:
            self._swapping = False
            self.timer.stop()
            self._update_swap()
        self.send()

    def _schedule(self):
        if (not self._swapping and self._automatic_eligible and self.settings.translation_auto_send
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

    def set_result(self, result, source_text=None, target_language=None, source_language=None):
        if source_text is not None and self.source.text.toPlainText() != source_text:
            return False
        if target_language is not None and self.target.currentText() != target_language:
            return False
        if (source_language is not None
                and language_value(self.source_language) != source_language):
            return False
        self.result.text.setPlainText(result.translation)
        self.source.set_pronunciation(result.source_pronunciation)
        self.result.set_pronunciation(result.translation_pronunciation)
        self.suggestion.set_suggestion(result.source_correction, self.source.text.toPlainText())
        self._detected_source = result.source_language
        self._update_swap()
        return True

    def apply_settings(self, settings):
        previous = self.settings
        changed = self._request_options(previous) != self._request_options(settings)
        pending = self.timer.isActive()
        self.settings = deepcopy(settings)
        self.tool_settings.update_settings(settings)
        select_language(self.target, settings.target_language)
        select_language(self.source_language, settings.translation_source_language, source=True)
        if changed:
            self._invalidate_result()
        elif previous.translation_auto_send and not settings.translation_auto_send:
            self.timer.stop()
            self.invalidated.emit()
        if changed or (not previous.translation_auto_send and settings.translation_auto_send):
            self._schedule()
        elif pending and previous.translation_debounce_ms != settings.translation_debounce_ms:
            self.timer.stop()
            self._schedule()
        self._update_swap()

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
