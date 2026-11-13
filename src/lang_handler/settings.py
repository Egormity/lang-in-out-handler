"""Serializable application preferences. Credentials are stored separately."""

from dataclasses import asdict, dataclass, field


@dataclass
class Settings:
    api_proxy_url: str = ""
    input_model: str = "gpt-transcribe"
    output_model: str = "gpt-transcribe"
    translation_model: str = "gpt-6-luna"
    tts_model: str = "gpt-realtime-2.1-mini"
    drawing_model: str = "gpt-6-luna"
    input_language: str = ""
    output_language: str = "ja"
    target_language: str = "English"
    input_instructions: str = ""
    output_instructions: str = ""
    translation_instructions: str = "Translate naturally. Preserve names, tone, and meaning. Return only the translation."
    tts_instructions: str = "Speak naturally and clearly."
    drawing_instructions: str = "Recognize the handwriting. Return plausible text candidates, most likely first. Preserve the original language. Do not translate or explain."
    drawing_auto_send: bool = True
    drawing_debounce_ms: int = 1200
    drawing_pen_width: int = 4
    drawing_on_top: bool = True
    voice: str = "coral"
    chunk_seconds: float = 5.0
    input_chunked: bool = False
    output_chunked: bool = True
    translation_enabled: bool = True
    transcript_visible: bool = True
    translation_visible: bool = True
    auto_paste: bool = True
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
        known = cls.__dataclass_fields__
        return cls(**{key: value for key, value in data.items() if key in known})
