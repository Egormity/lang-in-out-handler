"""Settings that belong to each workbench tool, outside the floating windows."""

from .audio_controls import AudioSourceCombo
from .common import label, selection_combo
from .language_selectors import target_language_selector
from .preference_controls import NumberInput
from .preference_sections import group, instructions, language, model, number, reasoning, toggle
from .provider_controls import ProviderControls


def capture(page, settings, layout):
    mode = page.mode
    form = group("Speech recognition", layout)
    model(page, settings, form, f"{mode}_model")
    language(page, settings, form, f"{mode}_language")
    source_key = "microphone_source" if mode == "input" else "output_source"
    source = AudioSourceCombo(mode == "output", getattr(settings, source_key))
    setattr(page, source_key, source)
    page.fields.add(
        form, "Microphone" if mode == "input" else "Audio source", source_key, source,
        read=source.source_name, write=source.set_value,
    )
    toggle(page, form, "Continuous chunks", f"{mode}_chunked")
    number(
        page, form, "Chunk duration", f"{mode}_chunk_seconds",
        minimum=2, maximum=30, step=0.5, decimals=1, suffix=" seconds",
    )
    instructions(page, settings, form, f"{mode}_instructions")
    if mode == "input":
        delivery(page, settings, layout)
    else:
        captions(page, settings, layout)
        translation(page, settings, layout, captions=True)


def delivery(page, settings, layout):
    form = group("Recognized text", layout)
    page.input_delivery = selection_combo([], "")
    for title, value in [
        ("Copy to clipboard", "copy"),
        ("Paste to selection", "paste"),
        ("Copy and paste", "copy_and_paste"),
    ]:
        page.input_delivery.addItem(title, value)
    page.input_delivery.setToolTip(
        "Paste to selection inserts at the focused text cursor or replaces selected text, "
        "while preserving your clipboard. Copy and paste also leaves the transcript on the clipboard."
    )
    page.fields.add(
        form, "After transcription", "input_delivery", page.input_delivery,
        read=page.input_delivery.currentData,
        write=lambda value: page.input_delivery.setCurrentIndex(
            max(0, page.input_delivery.findData(value))
        ),
    )


def captions(page, settings, layout):
    form = group("Floating captions", layout)
    number(page, form, "Text size", "font_size", minimum=12, maximum=56, suffix=" px")
    page.opacity = NumberInput(40, 100, step=5, suffix="%", name="Background opacity")
    page.opacity.setToolTip("Caption background opacity. Text and controls stay readable.")
    page.fields.add(
        form, "Background opacity", "overlay_opacity", page.opacity,
        read=lambda: page.opacity.value() / 100,
        write=lambda value: page.opacity.setValue(round(value * 100)),
    )
    toggle(page, form, "Keep on top", "overlay_on_top")
    toggle(page, form, "Show transcript", "transcript_visible")
    toggle(page, form, "Show translation", "translation_visible")


def translation(page, settings, layout, *, captions=False):
    form = group("Caption translation" if captions else "Translation", layout)
    provider = ProviderControls(page, settings, form, "translation_provider")
    model_widget = model(page, settings, form, "translation_model")
    reasoning(page, settings, form, "translation_reasoning", model_widget)
    page.target_language = target_language_selector(settings.target_language, compact=False)
    page.fields.add(form, "Translate into", "target_language", page.target_language)
    instructions(page, settings, form, "translation_instructions", captions=captions)
    provider.hide_for_google(
        model_widget, page.translation_reasoning,
        page.builtin_instructions["translation_instructions"],
        page.instructions["translation_instructions"],
    )
    if captions:
        form.addRow(label("Translation settings are shared with the Translate tool.", True))


def handwriting(page, settings, layout):
    form = group("Handwriting recognition", layout)
    provider = ProviderControls(page, settings, form, "drawing_provider")
    model_widget = model(page, settings, form, "drawing_model")
    reasoning(page, settings, form, "drawing_reasoning", model_widget)
    written_language = language(page, settings, form, "drawing_language")
    written_language.setToolTip("Choose the language written on the canvas. OpenAI also supports automatic detection.")
    provider.require_handwriting_language(written_language)
    toggle(page, form, "Automatic recognition", "drawing_auto_send")
    page.drawing_delay = NumberInput(
        0.2, 10, step=0.1, decimals=1, suffix=" seconds", name="Wait after drawing"
    )
    page.fields.add(
        form, "Wait after drawing", "drawing_debounce_ms", page.drawing_delay,
        read=lambda: round(page.drawing_delay.value() * 1000),
        write=lambda value: page.drawing_delay.setValue(value / 1000),
    )
    page.drawing_auto_send.toggled.connect(page.drawing_delay.setEnabled)
    instructions(page, settings, form, "drawing_instructions")
    provider.hide_for_google(
        model_widget, page.drawing_reasoning,
        page.builtin_instructions["drawing_instructions"],
        page.instructions["drawing_instructions"],
    )
    form = group("Canvas", layout)
    page.drawing_canvas_theme = selection_combo([], "")
    page.drawing_canvas_theme.addItem("Light", "light")
    page.drawing_canvas_theme.addItem("Dark", "dark")
    page.drawing_canvas_theme.setAccessibleName("Canvas theme")
    page.fields.add(
        form, "Canvas theme", "drawing_canvas_theme", page.drawing_canvas_theme,
        read=page.drawing_canvas_theme.currentData,
        write=lambda value: page.drawing_canvas_theme.setCurrentIndex(
            max(0, page.drawing_canvas_theme.findData(value))
        ),
    )
    number(page, form, "Pen width", "drawing_pen_width", minimum=1, maximum=16, suffix=" px")
    toggle(page, form, "Keep on top", "drawing_on_top")
    form.addRow(label("When automatic recognition is off, use Send to transcribe on the canvas.", True))
