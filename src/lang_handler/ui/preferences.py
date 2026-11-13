"""Editable connection, model, audio, and shortcut preferences."""

from dataclasses import replace

from PySide6.QtCore import Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QKeySequenceEdit,
    QLineEdit,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .audio_controls import AudioSourceCombo
from .common import button, editable_combo, label, language_combo, language_value, title_block


class PreferencesPage(QWidget):
    saved = Signal(object)
    key_saved = Signal(str)
    key_test_requested = Signal(str)
    models_requested = Signal(str)

    def __init__(self, settings, api_key_present=False):
        super().__init__()
        self.settings = settings
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 20)
        outer.addWidget(
            title_block("Preferences", "Your connection, models, and keyboard controls.")
        )
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 12, 10)
        layout.setSpacing(12)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)
        _, form = self._group("OpenAI connection", layout)
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("Enter a new API key to save or replace it")
        form.addRow("API key", self.api_key)
        self.api_proxy_url = QLineEdit(settings.api_proxy_url)
        self.api_proxy_url.setPlaceholderText("Use environment proxy (or direct if unset)")
        self.api_proxy_url.setToolTip(
            "Supports HTTP, HTTPS, and SOCKS proxy URLs. Leave empty to use the environment proxy, or connect directly when none is configured."
        )
        form.addRow("Proxy URL", self.api_proxy_url)
        actions = QHBoxLayout()
        save_key = button("Save key")
        self.test_key_button = button("Test connection")
        self.refresh_models_button = button("Refresh models")
        self.remove_key_button = button("Remove saved key")
        self.remove_key_button.setEnabled(api_key_present)
        self.remove_key_button.clicked.connect(self._remove_key)
        actions.addWidget(save_key)
        actions.addWidget(self.test_key_button)
        actions.addWidget(self.refresh_models_button)
        actions.addWidget(self.remove_key_button)
        form.addRow(actions)
        self.key_status = label(
            "API key saved." if api_key_present else "Add an API key to get started.", True
        )
        form.addRow(self.key_status)
        save_key.clicked.connect(self._save_key)
        self.test_key_button.clicked.connect(
            lambda: self.key_test_requested.emit(self.api_key.text().strip())
        )
        self.refresh_models_button.clicked.connect(
            lambda: self.models_requested.emit(self.api_key.text().strip())
        )
        self.api_key.textChanged.connect(self._update_key_actions)
        _, form = self._group("Models", layout)
        self.models = {}
        for key, title in [
            ("input_model", "Voice input"),
            ("output_model", "Output captions"),
            ("translation_model", "Translation"),
            ("tts_model", "Text to speech"),
            ("drawing_model", "Handwriting"),
        ]:
            widget = editable_combo([], getattr(settings, key))
            widget.setToolTip("Choose a model from your account or enter its model ID.")
            self.models[key] = widget
            form.addRow(title, widget)
        _, form = self._group("Languages & audio", layout)
        self.input_language = language_combo(settings.input_language)
        self.output_language = language_combo(settings.output_language)
        self.target_language = editable_combo(
            ["English", "Russian", "Japanese", "Spanish", "French", "German"],
            settings.target_language,
        )
        self.voice = editable_combo(
            [
                "coral",
                "alloy",
                "ash",
                "ballad",
                "echo",
                "fable",
                "nova",
                "onyx",
                "sage",
                "shimmer",
                "verse",
                "marin",
                "cedar",
            ],
            settings.voice,
        )
        form.addRow("Input language", self.input_language)
        form.addRow("Output language", self.output_language)
        form.addRow("Translate into", self.target_language)
        form.addRow("Speech voice", self.voice)
        self.chunk_seconds = QDoubleSpinBox()
        self.chunk_seconds.setRange(2, 30)
        self.chunk_seconds.setSingleStep(0.5)
        self.chunk_seconds.setSuffix(" seconds")
        self.chunk_seconds.setValue(settings.chunk_seconds)
        form.addRow("Chunk duration", self.chunk_seconds)
        self.microphone_source = AudioSourceCombo(False, settings.microphone_source)
        self.output_source = AudioSourceCombo(True, settings.output_source)
        form.addRow("Microphone source", self.microphone_source)
        form.addRow("Output monitor", self.output_source)
        form.addRow(
            label(
                "Default sources follow your system devices. You can also enter an audio source name.",
                True,
            )
        )
        _, form = self._group("Floating captions", layout)
        self.font_size = QSpinBox()
        self.font_size.setRange(12, 56)
        self.font_size.setSuffix(" px")
        self.font_size.setValue(settings.font_size)
        form.addRow("Text size", self.font_size)
        self.opacity = QDoubleSpinBox()
        self.opacity.setRange(0.4, 1)
        self.opacity.setSingleStep(0.05)
        self.opacity.setValue(settings.overlay_opacity)
        form.addRow("Opacity", self.opacity)
        _, form = self._group("Handwriting", layout)
        self.drawing_auto_send = QCheckBox("Recognize automatically after drawing")
        self.drawing_auto_send.setChecked(settings.drawing_auto_send)
        self.drawing_delay = QDoubleSpinBox()
        self.drawing_delay.setRange(0.2, 10)
        self.drawing_delay.setSingleStep(0.1)
        self.drawing_delay.setSuffix(" seconds")
        self.drawing_delay.setValue(settings.drawing_debounce_ms / 1000)
        self.drawing_delay.setEnabled(settings.drawing_auto_send)
        self.drawing_auto_send.toggled.connect(self.drawing_delay.setEnabled)
        form.addRow(self.drawing_auto_send)
        form.addRow("Wait after drawing", self.drawing_delay)
        _, form = self._group("Global shortcuts", layout)
        self.shortcuts = {}
        for mode, title in [
            ("input", "Toggle voice input"),
            ("output", "Toggle output captions"),
            ("translate", "Translate clipboard"),
            ("tts", "Read clipboard aloud"),
        ]:
            widget = QKeySequenceEdit(QKeySequence(settings.shortcuts.get(mode, "")))
            widget.setMaximumSequenceLength(1)
            self.shortcuts[mode] = widget
            form.addRow(title, widget)
        form.addRow(
            label("Meta is the Super / Windows key. Leave a shortcut empty to disable it.", True)
        )
        layout.addStretch()
        save = button("Save preferences", True)
        save.clicked.connect(lambda: self.saved.emit(self.collect()))
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(save)
        outer.addLayout(row)

    @staticmethod
    def _group(title, parent_layout):
        group = QGroupBox(title.replace("&", "&&"))
        form = QFormLayout(group)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setHorizontalSpacing(20)
        form.setVerticalSpacing(12)
        parent_layout.addWidget(group)
        return group, form

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

    def set_sources(self, sources: list[dict]):
        self.microphone_source.set_sources(sources)
        self.output_source.set_sources(sources)
