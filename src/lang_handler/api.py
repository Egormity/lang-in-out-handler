"""OpenAI-only speech recognition, translation and speech generation."""

import base64
import json
from pathlib import Path

import httpx
from openai import OpenAI

from .caption_context import caption_options, parse_revisions, validate_segments
from .errors import ServiceError, service_error
from .network import proxy_url
from .prompts import builtin_instructions, single_prompt, source_input
from .reasoning import reasoning_options
from .results import CaptionRevision, TranslationResult
from .transcription_context import recognized_text, transcription_prompt

MAX_AUDIO_BYTES = 25 * 1024 * 1024


class OpenAIService:
    def __init__(self, api_key: str, *, client=None, proxy: str | None = None):
        if not api_key.strip():
            raise ServiceError("Add your OpenAI API key in Preferences first.")
        self._key = api_key.strip()
        self._proxy = proxy_url(proxy)
        self._client = client or OpenAI(
            api_key=self._key,
            base_url="https://api.openai.com/v1",
            max_retries=1,
            http_client=httpx.Client(
                proxy=self._proxy,
                trust_env=False,
                timeout=httpx.Timeout(90, connect=15, write=30, pool=15),
            ),
        )

    def list_models(self) -> list[str]:
        try:
            return sorted(model.id for model in self._client.models.list())
        except Exception as error:  # noqa: BLE001 - sanitize every SDK/proxy failure at this boundary
            raise service_error(error, self._key) from None

    def transcribe(
        self,
        audio: bytes,
        model: str,
        language: str = "",
        instructions: str = "",
        filename: str = "audio.wav",
        *,
        context: str = "",
    ) -> str:
        if not audio:
            raise ServiceError("There is no audio to transcribe.")
        if len(audio) > MAX_AUDIO_BYTES:
            raise ServiceError("This recording exceeds 25 MB. Import it using chunks instead.")
        if "live-transcribe" in model or "realtime" in model:
            raise ServiceError(
                "Choose gpt-transcribe for recordings and chunks; live-only models need a different connection."
            )
        options = {
            "model": model,
            "file": (Path(filename).name, audio),
            "response_format": "json",
            "prompt": transcription_prompt(instructions, context),
        }
        if language and language.lower() != "auto":
            if model.startswith("gpt-transcribe"):
                options["extra_body"] = {
                    "languages": [code.strip() for code in language.split(",") if code.strip()]
                }
            else:
                options["language"] = language.strip()
        try:
            result = self._client.audio.transcriptions.create(**options)
            return recognized_text(result.text)
        except Exception as error:  # noqa: BLE001 - never expose SDK request headers in the UI
            raise service_error(error, self._key) from None

    def translate(
        self,
        text: str,
        model: str,
        target_language: str,
        instructions: str = "",
        reasoning: str = "medium",
    ) -> TranslationResult:
        if not text.strip():
            return TranslationResult("")
        if not target_language.strip():
            raise ServiceError("Choose a target language in the Translate settings.")
        guidance = builtin_instructions("translation_instructions")
        guidance += f"\n\nSelected target language: {target_language.strip()}."
        required_fields = ("translation", "source_pronunciation", "translation_pronunciation")
        fields = (*required_fields, "source_correction")
        options = {
            "model": model,
            "instructions": guidance,
            "input": source_input(text, instructions),
            "store": False,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "translation_with_pronunciation",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {key: {"type": "string"} for key in fields},
                        "required": list(fields),
                        "additionalProperties": False,
                    },
                }
            },
            **reasoning_options(model, reasoning),
        }
        try:
            result = self._client.responses.create(**options)
            try:
                payload = json.loads(result.output_text)
            except (ValueError, TypeError):
                raise ServiceError(
                    "The model returned an invalid translation result. Try again or choose another model."
                ) from None
            if (
                not isinstance(payload, dict)
                or not set(required_fields).issubset(payload)
                or not set(payload).issubset(fields)
                or any(not isinstance(value, str) for value in payload.values())
                or not payload["translation"].strip()
            ):
                raise ServiceError("The model returned an invalid translation result. Try again.")
            values = {key: payload.get(key, "").strip() for key in fields}
            if values["source_correction"] == text.strip():
                values["source_correction"] = ""
            return TranslationResult(**values)
        except Exception as error:  # noqa: BLE001 - sanitize every SDK/proxy failure at this boundary
            raise service_error(error, self._key) from None

    def revise_captions(
        self,
        segments: list[tuple[int, str]],
        model: str,
        target_language: str,
        instructions: str = "",
        reasoning: str = "medium",
    ) -> list[CaptionRevision]:
        segments = validate_segments(segments)
        if not target_language.strip():
            raise ServiceError("Choose a target language in the caption settings.")
        options = {
            "model": model,
            **caption_options(segments, target_language.strip(), instructions),
            **reasoning_options(model, reasoning),
        }
        try:
            response = self._client.responses.create(**options)
            return parse_revisions(response.output_text, segments)
        except Exception as error:  # noqa: BLE001 - sanitize SDK failures at the service boundary
            raise service_error(error, self._key) from None

    def synthesize(
        self,
        text: str,
        model: str,
        voice: str = "coral",
        instructions: str = "",
    ) -> bytes:
        if not text.strip():
            raise ServiceError("Enter text to read aloud first.")
        if len(text) > 4096:
            raise ServiceError("Read-aloud text is limited to 4,096 characters per request.")
        try:
            if model.startswith("gpt-realtime"):
                from .tts_api import realtime_speech

                return realtime_speech(
                    self._key,
                    text,
                    model,
                    voice,
                    instructions,
                    proxy=self._proxy,
                )
            options = {
                "model": model,
                "voice": voice,
                "input": text,
                "response_format": "wav",
            }
            if model.startswith("tts-"):
                if instructions.strip():
                    raise ServiceError(
                        "This legacy TTS model cannot follow instructions. Select a GPT speech model."
                    )
            else:
                options["instructions"] = single_prompt("tts_instructions", instructions)
            response = self._client.audio.speech.create(**options)
            audio = response.content
            if not audio:
                raise ServiceError("OpenAI returned no speech audio.")
            return audio
        except Exception as error:  # noqa: BLE001 - covers SDK and WebSocket backends without leaking keys
            raise service_error(error, self._key) from None

    def close(self) -> None:
        self._client.close()

    def recognize_handwriting(
        self,
        png: bytes,
        model: str,
        instructions: str = "",
        *,
        reasoning: str = "medium",
        language: str = "",
    ) -> list[str]:
        if not png.startswith(b"\x89PNG\r\n\x1a\n") or len(png) > 8 * 1024 * 1024:
            raise ServiceError("Send a valid canvas PNG smaller than 8 MB.")
        guidance = builtin_instructions("drawing_instructions")
        if language and language.lower() != "auto":
            guidance += (
                f"\nExpected handwriting language: {language.strip()}. "
                "Use this language to resolve ambiguous strokes, preserving the written script."
            )
        options = {
            "model": model,
            "instructions": guidance,
            "store": False,
            **reasoning_options(model, reasoning),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "handwriting_candidates",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "items": {"type": "array", "items": {"type": "string"}, "maxItems": 6}
                        },
                        "required": ["items"],
                        "additionalProperties": False,
                    },
                }
            },
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_image",
                            "detail": "high",
                            "image_url": "data:image/png;base64,"
                            + base64.b64encode(png).decode("ascii"),
                        },
                        {
                            "type": "input_text",
                            "text": json.dumps(
                                {"custom_instructions": instructions.strip()}, ensure_ascii=False
                            ),
                        },
                    ],
                }
            ],
        }
        try:
            result = self._client.responses.create(**options)
            try:
                payload = json.loads(result.output_text)
            except (ValueError, TypeError):
                raise ServiceError(
                    "The model returned an invalid handwriting result. Try again."
                ) from None
            items = payload.get("items") if isinstance(payload, dict) else None
            if (
                not isinstance(items, list)
                or len(items) > 6
                or any(not isinstance(item, str) for item in items)
            ):
                raise ServiceError("The model returned an invalid handwriting result. Try again.")
            return list(dict.fromkeys(item.strip() for item in items if item.strip()))
        except Exception as error:  # noqa: BLE001 - sanitize SDK failures before displaying them
            raise service_error(error, self._key) from None
