"""Cancelable audio import with continuous, context-aware caption translation."""

from copy import deepcopy
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QObject

from .api import OpenAIService
from .audio import audio_file_chunks
from .google_api import GoogleService
from .translation_context import next_context, translation_configuration


class FileImports(QObject):
    def __init__(self, controller):
        super().__init__(controller)
        self.c = controller
        self.imports = {}
        self.generations = {}
        self.context_epoch = 0

    def start(self, mode, path, chunked):
        key = self.c.require_key()
        if not key:
            return
        if mode in self.imports or self.c.captures[mode].is_running:
            self.c.fail("Stop the current recording or file import first.")
            return
        if self.c.pipeline_busy(mode):
            self.c.status("Finishing the previous recording. Please wait before opening audio.")
            return
        settings = deepcopy(self.c.settings)
        generation = self.generations.get(mode, 0) + 1
        session_id = uuid4().hex
        self.generations[mode] = generation
        model = getattr(settings, f"{mode}_model")
        self.c.capture_errors[mode] = ""

        def work(cancel, progress):
            service = OpenAIService(key, proxy=settings.api_proxy_url or None)
            translator = None
            completed = 0
            context = []
            context_epoch = self.context_epoch
            try:
                length = getattr(settings, f"{mode}_chunk_seconds") if chunked else None
                for audio in audio_file_chunks(Path(path), length):
                    if cancel.is_set():
                        break
                    text = service.transcribe(
                        audio, model, getattr(settings, f"{mode}_language"),
                        getattr(settings, f"{mode}_instructions"),
                    )
                    if cancel.is_set():
                        break
                    if not text.strip():
                        continue
                    segment_id = self.c.pipeline.allocate_segment_id()
                    progress(("source", segment_id, text))
                    completed += 1
                    if (mode == "output" and settings.translation_enabled
                            and translation_configuration(settings) == translation_configuration(self.c.settings)):
                        if context_epoch != self.context_epoch:
                            context = []
                            context_epoch = self.context_epoch
                        context = next_context(context, (segment_id, text), settings.translation_provider)
                        if settings.translation_provider == "google":
                            if translator is None:
                                translator = GoogleService(proxy=settings.api_proxy_url or None)
                            revisions = translator.revise_translation(context, settings.target_language)
                        else:
                            revisions = service.revise_captions(
                                context, settings.translation_model, settings.target_language,
                                settings.translation_instructions, settings.translation_reasoning,
                            )
                        if not cancel.is_set():
                            progress(("revisions", revisions))
                return completed
            finally:
                service.close()
                if translator is not None:
                    translator.close()

        def current():
            return mode in self.imports and self.generations.get(mode) == generation

        def progress(event):
            if not current():
                return
            if event[0] == "source":
                _, segment_id, text = event
                self.c.remember_segment(mode, segment_id, text, model, session_id=session_id)
                self.c.window.append_result(mode, text, segment_id=segment_id)
                if mode == "output":
                    self.c.overlay.append_caption(text, segment_id=segment_id)
            elif translation_configuration(settings) == translation_configuration(self.c.settings):
                self.c._revisions(event[1])

        def done():
            if self.generations.get(mode) != generation:
                return
            self.imports.pop(mode, None)
            self.c.refresh_capture_state(mode)

        def success(count):
            if self.generations.get(mode) == generation:
                self.c.status(f"File complete: {count} segment(s).")
                if mode == "output":
                    self.c.overlay.set_status("File complete.")

        def failed(message):
            if self.generations.get(mode) == generation:
                self.c.capture_errors[mode] = message
                self.c.fail(message)
                if mode == "output":
                    self.c.overlay.set_status(message)

        self.imports[mode] = self.c.jobs.submit(work, success, failed, progress, done)
        self.c.refresh_capture_state(mode)
        self.c.status("Transcribing audio file…")
        if mode == "output":
            self.c.show_overlay()

    def cancel(self, mode):
        job = self.imports.pop(mode, None)
        if job:
            self.generations[mode] = self.generations.get(mode, 0) + 1
            job.cancelled.set()
            self.c.refresh_capture_state(mode)
            self.c.status("File import cancelled; completed text remains in history.")

    def shutdown(self):
        for mode in tuple(self.imports):
            self.cancel(mode)
