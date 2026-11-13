"""File import, text translation, and generated speech workflows."""

import os
import subprocess
import tempfile
from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import QObject, QTimer

from .api import OpenAIService
from .audio import audio_file_chunks
from .desktop import play_audio


class Workflows(QObject):
    def __init__(self, controller):
        super().__init__(controller)
        self.c = controller
        self.imports = {}
        self.import_generations = {}
        self.speech_job = None
        self.translation_job = None
        self.player = None
        self.audio_files = []
        self.playback_timer = QTimer(self)
        self.playback_timer.setInterval(300)
        self.playback_timer.timeout.connect(self._playback_status)

    def import_file(self, mode, path, chunked):
        key = self.c.require_key()
        if not key:
            return
        if mode in self.imports or self.c.captures[mode].is_running:
            self.c.fail("Stop the current recording or file import first.")
            return
        settings = deepcopy(self.c.settings)
        generation = self.import_generations.get(mode, 0) + 1
        self.import_generations[mode] = generation
        model = getattr(settings, f"{mode}_model")
        self.c.window.set_recording(mode, True)
        self.c.status("Transcribing audio file…")
        if mode == "output":
            self.c.show_overlay()
            self.c.overlay.set_status("Transcribing audio file…")

        def work(cancel, progress):
            service = OpenAIService(key, proxy=settings.api_proxy_url or None)
            count = 0
            try:
                chunks = audio_file_chunks(Path(path), settings.chunk_seconds if chunked else None)
                for audio in chunks:
                    if cancel.is_set():
                        break
                    text = service.transcribe(
                        audio,
                        model,
                        getattr(settings, f"{mode}_language"),
                        getattr(settings, f"{mode}_instructions"),
                    )
                    if cancel.is_set():
                        break
                    translated = ""
                    if text and mode == "output" and settings.translation_enabled:
                        try:
                            translated = service.translate(
                                text,
                                settings.translation_model,
                                settings.target_language,
                                settings.translation_instructions,
                            )
                        except Exception:  # preserve recognized speech before reporting the failure
                            if not cancel.is_set():
                                progress((text, ""))
                            raise
                    if text and not cancel.is_set():
                        progress((text, translated))
                        count += 1
                return count
            finally:
                service.close()

        def progress(pair):
            if mode not in self.imports or self.import_generations.get(mode) != generation:
                return
            text, translated = pair
            self.c.window.append_result(mode, text, translated)
            if mode == "output":
                self.c.overlay.append_caption(text, translated)
            self.c.remember(mode, text, translated, model)

        def done():
            if self.import_generations.get(mode) != generation:
                return
            self.imports.pop(mode, None)
            self.c.window.set_recording(mode, False)

        def completed(count):
            if self.import_generations.get(mode) == generation:
                self.c.status(f"File complete: {count} segment(s).")
                if mode == "output":
                    self.c.overlay.set_status("File complete.")

        def failed(message):
            if self.import_generations.get(mode) == generation:
                self.c.fail(message)
                if mode == "output":
                    self.c.overlay.set_status(message)

        job = self.c.jobs.submit(work, completed, failed, progress, done)
        self.imports[mode] = job

    def translate(self, text):
        key = self.c.require_key()
        if not key or not text.strip():
            if key:
                self.c.fail("Enter or copy some text to translate.")
            return
        if self.translation_job:
            self.c.status("Translation is already in progress.")
            return
        settings = deepcopy(self.c.settings)
        self.c.status("Translating…")

        def work(cancel, progress):
            service = OpenAIService(key, proxy=settings.api_proxy_url or None)
            try:
                return service.translate(
                    text,
                    settings.translation_model,
                    settings.target_language,
                    settings.translation_instructions,
                )
            finally:
                service.close()

        def success(translated):
            self.c.window.set_translation(translated)
            self.c.remember("translate", text, translated, settings.translation_model)
            self.c.status("Translation ready.")

        self.translation_job = self.c.jobs.submit(
            work, success, self.c.fail, finished=lambda: setattr(self, "translation_job", None)
        )

    def speak(self, text):
        key = self.c.require_key()
        if not key:
            return
        if self.speech_job:
            self.c.status(
                "Speech is already being generated. Stop it before starting another request."
            )
            return
        settings = deepcopy(self.c.settings)
        self.stop_speech()
        self.c.status("Generating speech…")

        def work(cancel, progress):
            service = OpenAIService(key, proxy=settings.api_proxy_url or None)
            try:
                return service.synthesize(
                    text, settings.tts_model, settings.voice, settings.tts_instructions
                )
            finally:
                service.close()

        def success(audio):
            directory = self.c.store.data_dir / "speech"
            directory.mkdir(mode=0o700, exist_ok=True)
            fd, path = tempfile.mkstemp(suffix=".wav", prefix="speech-", dir=directory)
            with os.fdopen(fd, "wb") as output:
                output.write(audio)
            self.audio_files.append(Path(path))
            self.c.window.set_speech(path)
            self.c.remember("tts", text, "", settings.tts_model)
            self._play(path)

        self.speech_job = self.c.jobs.submit(
            work, success, self.c.fail, finished=lambda: setattr(self, "speech_job", None)
        )

    def replay(self, path):
        """Replay existing speech through the same player controlled by Stop."""
        if not Path(path).is_file():
            self.c.fail("This generated audio is no longer available. Generate it again.")
            return
        self.stop_speech()
        self._play(path)

    def _play(self, path):
        try:
            self.player = play_audio(path)
            self.playback_timer.start()
            self.c.status("Playing AI-generated speech.")
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            self.c.fail(str(exc))

    def _playback_status(self):
        if self.player and self.player.poll() is not None:
            code = self.player.returncode
            self.player = None
            self.playback_timer.stop()
            if code:
                self.c.fail("Audio playback failed. You can still save the generated WAV file.")
            else:
                self.c.status("Speech finished. Save the audio if you want to keep it.")

    def stop_speech(self):
        if self.speech_job:
            self.speech_job.cancelled.set()
        if self.player and self.player.poll() is None:
            self.player.terminate()
        self.player = None
        self.playback_timer.stop()

    def cancel_import(self, mode):
        job = self.imports.pop(mode, None)
        if job:
            self.import_generations[mode] = self.import_generations.get(mode, 0) + 1
            job.cancelled.set()
            self.c.window.set_recording(mode, False)
            self.c.status("File import cancelled; completed segments remain in history.")

    def shutdown(self):
        self.stop_speech()
        for mode, job in self.imports.items():
            self.import_generations[mode] = self.import_generations.get(mode, 0) + 1
            job.cancelled.set()
        self.imports.clear()
        for path in self.audio_files:
            path.unlink(missing_ok=True)
