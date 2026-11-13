"""Preference sections grouped by the task they configure."""

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QKeySequenceEdit,
    QSpinBox,
)

from .audio_controls import AudioSourceCombo
from .common import editable_combo, label, language_combo
from .sections import scrollable_body


def group(title, layout):
    box = QGroupBox(title.replace("&", "&&"))
    form = QFormLayout(box)
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    form.setHorizontalSpacing(20)
    form.setVerticalSpacing(12)
    layout.addWidget(box)
    return form


def model(page, settings, form, key):
    widget = editable_combo([], getattr(settings, key))
    widget.setToolTip("Choose a model from your account or enter its model ID.")
    page.models[key] = widget
    form.addRow("Model", widget)


def recognition(page, settings):
    scroll, layout = scrollable_body()
    layout.addWidget(label("Choose how you capture and recognize speech.", True))
    form = group("Voice input", layout)
    model(page, settings, form, "input_model")
    page.input_language = language_combo(settings.input_language)
    page.microphone_source = AudioSourceCombo(False, settings.microphone_source)
    form.addRow("Language", page.input_language)
    form.addRow("Microphone", page.microphone_source)
    form = group("Live captions", layout)
    model(page, settings, form, "output_model")
    page.output_language = language_combo(settings.output_language)
    page.output_source = AudioSourceCombo(True, settings.output_source)
    form.addRow("Language", page.output_language)
    form.addRow("Audio source", page.output_source)
    form = group("Capture & floating window", layout)
    page.chunk_seconds = QDoubleSpinBox()
    page.chunk_seconds.setRange(2, 30)
    page.chunk_seconds.setSingleStep(0.5)
    page.chunk_seconds.setSuffix(" seconds")
    page.font_size = QSpinBox()
    page.font_size.setRange(12, 56)
    page.font_size.setSuffix(" px")
    page.opacity = QDoubleSpinBox()
    page.opacity.setRange(0.4, 1)
    page.opacity.setSingleStep(0.05)
    form.addRow("Chunk duration", page.chunk_seconds)
    form.addRow("Caption text size", page.font_size)
    form.addRow("Window opacity", page.opacity)
    layout.addStretch()
    return scroll


def translation(page, settings):
    scroll, layout = scrollable_body()
    layout.addWidget(label("Translation and spoken playback share the Translate tool.", True))
    form = group("Translation", layout)
    model(page, settings, form, "translation_model")
    page.target_language = editable_combo(
        ["English", "Russian", "Japanese", "Spanish", "French", "German"], settings.target_language
    )
    form.addRow("Translate into", page.target_language)
    form = group("Speech playback", layout)
    model(page, settings, form, "tts_model")
    page.voice = editable_combo(
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
    form.addRow("Voice", page.voice)
    form.addRow(
        label(
            "Change translation and speaking instructions under Translation & voice options in the Translate tool.",
            True,
        )
    )
    layout.addStretch()
    return scroll


def handwriting(page, settings):
    scroll, layout = scrollable_body()
    layout.addWidget(label("Recognize handwritten text using an image-capable model.", True))
    form = group("Handwriting recognition", layout)
    model(page, settings, form, "drawing_model")
    page.drawing_auto_send = QCheckBox("Recognize after I finish drawing")
    page.drawing_auto_send.setChecked(settings.drawing_auto_send)
    page.drawing_delay = QDoubleSpinBox()
    page.drawing_delay.setRange(0.2, 10)
    page.drawing_delay.setSingleStep(0.1)
    page.drawing_delay.setSuffix(" seconds")
    page.drawing_auto_send.toggled.connect(page.drawing_delay.setEnabled)
    form.addRow(page.drawing_auto_send)
    form.addRow("Wait after drawing", page.drawing_delay)
    form.addRow(
        label(
            "Automatic recognition sends the canvas image to OpenAI. You can always send it manually instead.",
            True,
        )
    )
    layout.addStretch()
    return scroll


def shortcuts(page, settings):
    scroll, layout = scrollable_body()
    layout.addWidget(label("Use your tools without switching windows.", True))
    form = group("Global shortcuts", layout)
    page.shortcuts = {}
    for mode, title in [
        ("input", "Toggle voice input"),
        ("output", "Toggle live captions"),
        ("translate", "Translate clipboard"),
        ("tts", "Read clipboard aloud"),
    ]:
        widget = QKeySequenceEdit(QKeySequence(settings.shortcuts.get(mode, "")))
        widget.setMaximumSequenceLength(1)
        page.shortcuts[mode] = widget
        form.addRow(title, widget)
    form.addRow(label("Meta is the Super / Windows key. Clear a shortcut to disable it.", True))
    layout.addStretch()
    return scroll
