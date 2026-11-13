"""Preference sections grouped by the task they configure."""

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QCheckBox, QFormLayout, QGroupBox, QKeySequenceEdit, QPlainTextEdit

from .audio_controls import AudioSourceCombo
from .common import label, language_combo, language_value, selection_combo
from .preference_controls import NumberInput
from .sections import scrollable_body


def group(title, layout):
    box = QGroupBox(title.replace("&", "&&"))
    form = QFormLayout(box)
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    form.setHorizontalSpacing(16)
    form.setVerticalSpacing(12)
    layout.addWidget(box)
    return form


def model(page, settings, form, key):
    value = getattr(settings, key)
    choices = [getattr(page.fields.defaults, key)]
    if key in ("translation_model", "drawing_model"):
        choices += ["gpt-6-luna", "gpt-6.1-sol"]
    widget = selection_combo(choices, value)
    widget.setToolTip(
        "Choose a model. Refresh models in Connection to load your account's choices."
    )
    page.models[key] = widget
    page.fields.add(form, "Model", key, widget)


def instructions(page, settings, form, key):
    widget = QPlainTextEdit(getattr(settings, key))
    widget.setAccessibleName(key.replace("_", " ").capitalize())
    widget.setTabChangesFocus(True)
    widget.setPlaceholderText("Language, style, vocabulary, or pronunciation instructions…")
    widget.setFixedHeight(88)
    page.instructions[key] = widget
    page.fields.add(form, "Instructions", key, widget)


def toggle(page, form, title, key):
    widget = QCheckBox("Enabled")
    widget.setAccessibleName(title)
    setattr(page, key, widget)
    page.fields.add(form, title, key, widget)
    return widget


def number(page, form, title, key, *, attr=None, read=None, write=None, **kwargs):
    widget = NumberInput(name=title, **kwargs)
    setattr(page, attr or key, widget)
    page.fields.add(form, title, key, widget, read=read, write=write)
    return widget


def recognition(page, settings):
    scroll, layout = scrollable_body()
    layout.addWidget(label("Capture, recognition, and floating caption behavior.", True))
    for mode, heading, source_key in [
        ("input", "Voice input", "microphone_source"),
        ("output", "Live captions", "output_source"),
    ]:
        form = group(heading, layout)
        model(page, settings, form, f"{mode}_model")
        language = language_combo(getattr(settings, f"{mode}_language"))
        setattr(page, f"{mode}_language", language)
        page.fields.add(
            form,
            "Language",
            f"{mode}_language",
            language,
            read=lambda w=language: language_value(w),
            write=lambda value, w=language: w.setCurrentIndex(max(0, w.findData(value))),
        )
        source = AudioSourceCombo(mode == "output", getattr(settings, source_key))
        setattr(page, source_key, source)
        page.fields.add(
            form,
            "Audio source" if mode == "output" else "Microphone",
            source_key,
            source,
            read=source.source_name,
            write=source.set_value,
        )
        toggle(page, form, "Continuous chunks", f"{mode}_chunked")
        if mode == "input":
            toggle(page, form, "Paste into active app", "auto_paste")
        instructions(page, settings, form, f"{mode}_instructions")
    form = group("Capture & floating window", layout)
    number(
        page,
        form,
        "Chunk duration",
        "chunk_seconds",
        minimum=2,
        maximum=30,
        step=0.5,
        decimals=1,
        suffix=" seconds",
    )
    number(page, form, "Caption text size", "font_size", minimum=12, maximum=56, suffix=" px")
    page.opacity = NumberInput(40, 100, step=5, suffix="%", name="Window opacity")
    page.fields.add(
        form,
        "Window opacity",
        "overlay_opacity",
        page.opacity,
        read=lambda: page.opacity.value() / 100,
        write=lambda value: page.opacity.setValue(round(value * 100)),
    )
    toggle(page, form, "Keep captions on top", "overlay_on_top")
    toggle(page, form, "Show transcript", "transcript_visible")
    toggle(page, form, "Show translation", "translation_visible")
    layout.addStretch()
    return scroll


def translation(page, settings):
    scroll, layout = scrollable_body()
    layout.addWidget(label("Speech settings apply to every Speak button in the app.", True))
    form = group("Translation", layout)
    model(page, settings, form, "translation_model")
    page.target_language = selection_combo(
        ["English", "Russian", "Japanese", "Spanish", "French", "German", "Chinese", "Korean"],
        settings.target_language,
    )
    page.fields.add(form, "Translate into", "target_language", page.target_language)
    instructions(page, settings, form, "translation_instructions")
    form = group("Speech playback", layout)
    model(page, settings, form, "tts_model")
    page.voice = selection_combo(
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
    page.fields.add(form, "Voice", "voice", page.voice)
    instructions(page, settings, form, "tts_instructions")
    layout.addStretch()
    return scroll


def handwriting(page, settings):
    scroll, layout = scrollable_body()
    layout.addWidget(
        label("Handwriting returns a list of possible readings, most likely first.", True)
    )
    form = group("Handwriting recognition", layout)
    model(page, settings, form, "drawing_model")
    toggle(page, form, "Automatic recognition", "drawing_auto_send")
    page.drawing_delay = NumberInput(
        0.2, 10, step=0.1, decimals=1, suffix=" seconds", name="Wait after drawing"
    )
    page.fields.add(
        form,
        "Wait after drawing",
        "drawing_debounce_ms",
        page.drawing_delay,
        read=lambda: round(page.drawing_delay.value() * 1000),
        write=lambda value: page.drawing_delay.setValue(value / 1000),
    )
    page.drawing_auto_send.toggled.connect(page.drawing_delay.setEnabled)
    instructions(page, settings, form, "drawing_instructions")
    form = group("Canvas", layout)
    number(page, form, "Pen width", "drawing_pen_width", minimum=1, maximum=16, suffix=" px")
    toggle(page, form, "Keep handwriting on top", "drawing_on_top")
    layout.addWidget(
        label("When automatic recognition is off, use Send to transcribe on the canvas.", True)
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
        page.fields.add(
            form,
            title,
            f"shortcut:{mode}",
            widget,
            read=lambda w=widget: w.keySequence().toString(
                QKeySequence.SequenceFormat.PortableText
            ),
            write=lambda value, w=widget: w.setKeySequence(QKeySequence(value)),
            default=page.fields.defaults.shortcuts.get(mode, ""),
        )
    form.addRow(label("Meta is the Super / Windows key. Clear a shortcut to disable it.", True))
    layout.addStretch()
    return scroll
