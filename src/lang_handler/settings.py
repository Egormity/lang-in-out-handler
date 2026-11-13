"""Serializable application preferences. Credentials are stored separately."""

from dataclasses import asdict, dataclass, field

_OLD_STOCK_INSTRUCTIONS = {
    "translation_instructions": "Translate naturally. Preserve names, tone, and meaning.",
    "tts_instructions": "Speak naturally and clearly.",
    "drawing_instructions": (
        "Recognize the handwriting. Return plausible text candidates, most likely first. "
        "Preserve the original language. Do not translate or explain."
    ),
}


@dataclass
class Settings:
    api_proxy_url: str = ""
    drawing_provider: str = "google"
    translation_provider: str = "google"
    input_model: str = "gpt-transcribe"
    output_model: str = "gpt-transcribe"
    translation_model: str = "gpt-6-luna"
    tts_model: str = "gpt-realtime-2.1-mini"
    drawing_model: str = "gpt-6.1-sol"
    input_language: str = ""
    output_language: str = "ja"
    target_language: str = "English"
    drawing_language: str = "ja"
    translation_reasoning: str = "medium"
    drawing_reasoning: str = "low"
    input_instructions: str = ""
    output_instructions: str = ""
    translation_instructions: str = ""
    tts_instructions: str = ""
    drawing_instructions: str = ""
    translation_auto_send: bool = True
    translation_debounce_ms: int = 1000
    drawing_auto_send: bool = True
    drawing_debounce_ms: int = 1000
    drawing_pen_width: int = 4
    drawing_canvas_theme: str = "light"
    drawing_on_top: bool = True
    voice: str = "coral"
    input_chunk_seconds: float = 5.0
    output_chunk_seconds: float = 5.0
    output_context_seconds: int = 20
    input_chunked: bool = False
    output_chunked: bool = True
    translation_enabled: bool = True
    transcript_visible: bool = True
    translation_visible: bool = True
    input_delivery: str = "copy_and_paste"
    microphone_source: str = ""
    output_source: str = ""
    font_size: int = 21
    overlay_opacity: float = 0.95
    overlay_on_top: bool = True
    shortcuts: dict[str, str] = field(default_factory=lambda: {
        "input": "Meta+Alt+I", "output": "Meta+Alt+O",
        "translate": "Meta+Alt+T", "tts": "Meta+Alt+V",
    })

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Settings":
        data = dict(data)
        for key, previous_default in _OLD_STOCK_INSTRUCTIONS.items():
            if data.get(key) == previous_default:
                data[key] = ""
        if "input_delivery" not in data and "auto_paste" in data:
            data["input_delivery"] = "copy_and_paste" if data["auto_paste"] else "copy"
        if "chunk_seconds" in data:
            data.setdefault("input_chunk_seconds", data["chunk_seconds"])
            data.setdefault("output_chunk_seconds", data["chunk_seconds"])
        known = cls.__dataclass_fields__
        return cls(**{key: value for key, value in data.items() if key in known})
