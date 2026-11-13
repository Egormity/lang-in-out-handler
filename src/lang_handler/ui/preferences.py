"""Connection and task settings, organized into focused tabs."""

from dataclasses import replace

from PySide6.QtCore import Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QTabWidget, QVBoxLayout, QWidget

from . import preference_sections
from .common import button, label, language_value, title_block
from .sections import scrollable_body


class PreferencesPage(QWidget):
    saved = Signal(object)
    key_saved = Signal(str)
    key_test_requested = Signal(str)
    models_requested = Signal(str)

    def __init__(self, settings, api_key_present=False):
        super().__init__()
        self.settings = settings
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 20)
        outer.setSpacing(16)
        outer.addWidget(title_block("Preferences", "Connect OpenAI and make each tool your own."))
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().setDrawBase(False)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.addTab(self._connection(settings, api_key_present), "Connection")
        self.models = {}
        for builder, title in [
            (preference_sections.recognition, "Recognition"),
            (preference_sections.translation, "Translation / speech"),
            (preference_sections.handwriting, "Handwriting"),
            (preference_sections.shortcuts, "Shortcuts"),
        ]:
            self.tabs.addTab(builder(self, settings), title)
        outer.addWidget(self.tabs, 1)
        row = QHBoxLayout()
        row.addWidget(label("Preferences are stored on this computer.", True), 1)
        self.save_preferences = button("Save preferences", True)
        self.save_preferences.clicked.connect(lambda: self.saved.emit(self.collect()))
        row.addWidget(self.save_preferences)
        outer.addLayout(row)
        self.update_settings(settings)

    def _connection(self, settings, api_key_present):
        scroll, layout = scrollable_body()
        layout.addWidget(label("Your API key connects every tool to your OpenAI account.", True))
        form = preference_sections.group("OpenAI API key", layout)
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("Paste a new API key")
        form.addRow("API key", self.api_key)
        actions = QHBoxLayout()
        actions.setSpacing(8)
        save_key = button("Save key")
        self.test_key_button = button("Test connection", True)
        self.refresh_models_button = button("Refresh models")
        self.remove_key_button = button("Remove key")
        self.remove_key_button.setObjectName("quiet")
        self.remove_key_button.setEnabled(api_key_present)
        self.remove_key_button.clicked.connect(self._remove_key)
        for item in (save_key, self.test_key_button, self.refresh_models_button):
            actions.addWidget(item)
        form.addRow(actions)
        self.key_status = label("API key saved." if api_key_present else "No API key saved.", True)
        form.addRow(self.key_status)
        remove_row = QHBoxLayout()
        remove_row.addStretch()
        remove_row.addWidget(self.remove_key_button)
        form.addRow(remove_row)
        save_key.clicked.connect(self._save_key)
        self.test_key_button.clicked.connect(
            lambda: self.key_test_requested.emit(self.api_key.text().strip())
        )
        self.refresh_models_button.clicked.connect(
            lambda: self.models_requested.emit(self.api_key.text().strip())
        )
        self.api_key.textChanged.connect(self._update_key_actions)
        form = preference_sections.group("Network", layout)
        self.api_proxy_url = QLineEdit(settings.api_proxy_url)
        self.api_proxy_url.setPlaceholderText("Use environment proxy (or direct if unset)")
        self.api_proxy_url.setToolTip(
            "Supports HTTP, HTTPS, and SOCKS proxy URLs. Leave empty to use the environment proxy, or connect directly when none is configured."
        )
        form.addRow("Proxy URL", self.api_proxy_url)
        form.addRow(
            label(
                "Test connection checks the key and proxy entered here. API usage is billed to your OpenAI account.",
                True,
            )
        )
        layout.addStretch()
        return scroll

    def _save_key(self):
        value = self.api_key.text().strip()
        if value:
            self.key_saved.emit(value)

    def _update_key_actions(self):
        pending = bool(self.api_key.text().strip())
        self.test_key_button.setText("Save and test" if pending else "Test connection")
        self.refresh_models_button.setText("Save and refresh" if pending else "Refresh models")
        hint = "Save and use the key entered above." if pending else "Use the saved API key."
        self.test_key_button.setToolTip(hint)
        self.refresh_models_button.setToolTip(hint)

    def _remove_key(self):
        self.key_saved.emit("")

    def collect(self):
        values = {key: widget.currentText().strip() for key, widget in self.models.items()}
        values.update(
            api_proxy_url=self.api_proxy_url.text().strip(),
            input_language=language_value(self.input_language),
            output_language=language_value(self.output_language),
            target_language=self.target_language.currentText().strip() or "English",
            voice=self.voice.currentText().strip() or "coral",
            chunk_seconds=self.chunk_seconds.value(),
            microphone_source=self.microphone_source.source_name(),
            output_source=self.output_source.source_name(),
            font_size=self.font_size.value(),
            overlay_opacity=self.opacity.value(),
            drawing_auto_send=self.drawing_auto_send.isChecked(),
            drawing_debounce_ms=round(self.drawing_delay.value() * 1000),
            shortcuts={
                mode: widget.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
                for mode, widget in self.shortcuts.items()
            },
        )
        return replace(self.settings, **values)

    def set_models(self, model_ids):
        for key, widget in self.models.items():
            selected = widget.currentText()
            if key in ("input_model", "output_model"):
                filtered = [m for m in model_ids if "transcribe" in m or "whisper" in m]
                filtered = [m for m in filtered if "realtime" not in m and "live" not in m]
            elif key == "tts_model":
                filtered = [m for m in model_ids if "tts" in m or "realtime" in m]
                filtered = [
                    m
                    for m in filtered
                    if not any(part in m for part in ("translate", "whisper", "transcribe"))
                ]
            else:
                excluded = (
                    "audio",
                    "realtime",
                    "transcribe",
                    "tts",
                    "image",
                    "embedding",
                    "search",
                    "live",
                )
                filtered = [
                    m
                    for m in model_ids
                    if m.startswith(("gpt-", "o1", "o3", "o4"))
                    and not any(x in m for x in excluded)
                ]
            widget.clear()
            widget.addItems(sorted({*filtered, selected}))
            widget.setCurrentText(selected)

    def update_settings(self, settings):
        self.settings = settings
        self.api_proxy_url.setText(settings.api_proxy_url)
        for key, widget in self.models.items():
            widget.setCurrentText(getattr(settings, key))
        for widget, value in [
            (self.input_language, settings.input_language),
            (self.output_language, settings.output_language),
        ]:
            index = widget.findData(value)
            if index >= 0:
                widget.setCurrentIndex(index)
            else:
                widget.setCurrentText(value)
        self.target_language.setCurrentText(settings.target_language)
        self.voice.setCurrentText(settings.voice)
        self.chunk_seconds.setValue(settings.chunk_seconds)
        self.microphone_source.set_value(settings.microphone_source)
        self.output_source.set_value(settings.output_source)
        self.font_size.setValue(settings.font_size)
        self.opacity.setValue(settings.overlay_opacity)
        self.drawing_auto_send.setChecked(settings.drawing_auto_send)
        self.drawing_delay.setValue(settings.drawing_debounce_ms / 1000)
        self.drawing_delay.setEnabled(settings.drawing_auto_send)
        for mode, widget in self.shortcuts.items():
            widget.setKeySequence(QKeySequence(settings.shortcuts.get(mode, "")))

    def set_sources(self, sources):
        self.microphone_source.set_sources(sources)
        self.output_source.set_sources(sources)
