"""Shared settings builders and the application-wide speech/shortcut sections."""

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QCheckBox, QFormLayout, QGroupBox, QKeySequenceEdit, QPlainTextEdit

from ..reasoning import REASONING_EFFORTS, supports_reasoning
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
    widget.setToolTip("Refresh models in global Preferences → Connection to load your account's choices.")
    page.models[key] = widget
    page.fields.add(form, "Model", key, widget)
    return widget


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


def language(page, settings, form, key):
    widget = language_combo(getattr(settings, key))
    setattr(page, key, widget)
    page.fields.add(
        form, "Language", key, widget,
        read=lambda: language_value(widget),
        write=lambda value: widget.setCurrentIndex(max(0, widget.findData(value))),
    )
    return widget


def reasoning(page, settings, form, key, model_widget):
    widget = selection_combo([effort.capitalize() for effort in REASONING_EFFORTS], getattr(settings, key).capitalize())
    widget.setAccessibleName("Reasoning effort")
    widget.setToolTip("More reasoning can improve difficult results and take longer. Applies to reasoning models.")
    setattr(page, key, widget)
    page.fields.add(
        form, "Reasoning", key, widget,
        read=lambda: widget.currentText().lower(),
        write=lambda value: widget.setCurrentText(value.capitalize()),
    )

    def update():
        widget.setEnabled(supports_reasoning(model_widget.currentText()))

    model_widget.currentTextChanged.connect(update)
    update()


def speech(page, settings):
    scroll, layout = scrollable_body()
    layout.addWidget(label("These settings apply to every Speak button and Read clipboard shortcut.", True))
    form = group("Shared speech playback", layout)
    model(page, settings, form, "tts_model")
    page.voice = selection_combo(
        ["coral", "alloy", "ash", "ballad", "echo", "fable", "nova", "onyx", "sage",
         "shimmer", "verse", "marin", "cedar"],
        settings.voice,
    )
    page.fields.add(form, "Voice", "voice", page.voice)
    instructions(page, settings, form, "tts_instructions")
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
            form, title, f"shortcut:{mode}", widget,
            read=lambda w=widget: w.keySequence().toString(QKeySequence.SequenceFormat.PortableText),
            write=lambda value, w=widget: w.setKeySequence(QKeySequence(value)),
            default=page.fields.defaults.shortcuts.get(mode, ""),
        )
    form.addRow(label("Meta is the Super / Windows key. Clear a shortcut to disable it.", True))
    layout.addStretch()
    return scroll
