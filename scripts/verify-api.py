"""An explicit, paid smoke test using synthetic, nonpersonal Japanese audio."""

import argparse
import io
import os
import tempfile
import wave
from pathlib import Path

from lang_handler.api import OpenAIService, ServiceError
from lang_handler.audio import audio_file_chunks
from lang_handler.credentials import Credentials
from lang_handler.settings import Settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-api-charge", action="store_true")
    args = parser.parse_args()
    if not args.allow_api_charge:
        parser.error("Pass --allow-api-charge to authorize the short paid audio test.")
    settings = Settings()
    key = os.environ.get("OPENAI_API_KEY") or Credentials().get()
    service = OpenAIService(key)
    sample = "今日は日本語の字幕と翻訳をテストしています。音声が正しく認識されています。"
    try:
        audio = service.synthesize(sample, settings.tts_model, settings.voice,
                                   "Read this Japanese text naturally and exactly.")
        with wave.open(io.BytesIO(audio)) as wav:
            print(f"Speech: {wav.getnframes() / wav.getframerate():.1f}s WAV")
        transcript = service.transcribe(audio, settings.input_model, "ja")
        if not transcript:
            raise RuntimeError("Whole-recording transcription was empty.")
        print("Once:", transcript)
        translated = service.translate(transcript, settings.translation_model, "English")
        if not translated:
            raise RuntimeError("Translation was empty.")
        print("English:", translated)
        with tempfile.TemporaryDirectory(prefix="lang-in-out-api-test-") as directory:
            path = Path(directory) / "sample.wav"
            path.write_bytes(audio)
            chunks = list(audio_file_chunks(path, 4))
            results = [service.transcribe(chunk, settings.input_model, "ja") for chunk in chunks]
            if not any(results):
                raise RuntimeError("Chunk transcription was empty.")
            print(f"Chunks ({len(results)}):", " | ".join(results))
        print("PASS: speech, once transcription, chunk transcription, translation.")
    except (ServiceError, RuntimeError) as exc:
        print(f"FAIL: {exc}")
        return 1
    finally:
        service.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

