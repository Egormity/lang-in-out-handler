"""File import, text translation, and generated speech workflows."""

import os
import subprocess
import tempfile
from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from .api import OpenAIService
from .desktop import play_audio
from .file_import import FileImports


class Workflows(QObject):
    speech_active_changed = Signal(bool)

    def __init__(self, controller):
        super().__init__(controller)
        self.c = controller
        self.files = FileImports(controller)
        self.imports = self.files.imports
        self.import_generations = self.files.generations
        self.speech_job = None
        self.translation_job = None
        self.player = None
        self.audio_files = []
        self.playback_timer = QTimer(self)
        self.playback_timer.setInterval(300)
        self.playback_timer.timeout.connect(self._playback_status)

    def import_file(self, mode, path, chunked):
        self.files.start(mode, path, chunked)

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
                    settings.translation_reasoning,
                )
            finally:
                service.close()

        def success(translated):
            displayed = self.c.window.set_translation(translated, text, settings.target_language)
            self.c.remember("translate", text, translated, settings.translation_model)
            self.c.status("Translation ready." if displayed else
                          "Translation saved in History; the original text or target language changed.")

        self.translation_job = self.c.jobs.submit(
            work, success, self.c.fail, finished=lambda: setattr(self, "translation_job", None)
        )

    def speak(self, text):
        if not text.strip():
            return
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
        self.speech_active_changed.emit(True)

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

        def done():
            self.speech_job = None
            self.speech_active_changed.emit(self.player is not None)

        self.speech_job = self.c.jobs.submit(work, success, self.c.fail, finished=done)

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
            self.speech_active_changed.emit(True)
            self.c.status("Reading aloud…")
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            self.c.fail(str(exc))

    def _playback_status(self):
        if self.player and self.player.poll() is not None:
            code = self.player.returncode
            self.player = None
            self.playback_timer.stop()
            self.speech_active_changed.emit(False)
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
        self.speech_active_changed.emit(False)

    def cancel_import(self, mode):
        self.files.cancel(mode)

    def shutdown(self):
        self.stop_speech()
        self.files.shutdown()
        for path in self.audio_files:
            path.unlink(missing_ok=True)
