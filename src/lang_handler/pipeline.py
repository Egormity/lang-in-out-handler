"""Ordered, bounded transcription and translation queues for live audio."""

from collections import deque
from copy import deepcopy

from PySide6.QtCore import QObject, Signal

from lang_handler.api import OpenAIService
from lang_handler.jobs import Jobs


class CaptionPipeline(QObject):
    transcript = Signal(str, str)
    translation = Signal(str, str)
    completed = Signal(str, str, str, str)
    error = Signal(str, str)
    pending_changed = Signal(str, int)

    def __init__(self, jobs: Jobs, parent=None):
        super().__init__(parent)
        self.jobs = jobs
        self.queues = {mode: deque() for mode in ("input", "output", "translation")}
        self.busy = {mode: False for mode in self.queues}
        self.generations = {mode: 0 for mode in self.queues}
        self.active_translation = None
        self.closed = False

    def enqueue(self, mode, audio, settings, key):
        if self.closed:
            return
        if len(self.queues[mode]) >= 6:
            self.abort(mode)
            self.error.emit(
                mode,
                "Caption processing is falling behind. Capture stopped; increase chunk duration or choose a faster model.",
            )
            return
        self.queues[mode].append((audio, deepcopy(settings), key))
        self._start(mode)

    def abort(self, mode):
        self.generations[mode] += 1
        self.queues[mode].clear()
        if mode == "output":
            self.generations["translation"] += 1
            # Recognition already succeeded for these captions. Preserve their source
            # even when translation fails, capture is aborted, or the app is closed.
            pending = []
            if self.active_translation is not None:
                pending.append(self.active_translation)
                self.active_translation = None
            pending.extend((text, model) for text, _, _, model in self.queues["translation"])
            self.queues["translation"].clear()
            for text, model in pending:
                self.completed.emit("output", text, "", model)

    def _start(self, mode):
        if self.closed or self.busy[mode] or not self.queues[mode]:
            return
        self.busy[mode] = True
        audio, settings, key = self.queues[mode].popleft()
        generation = self.generations[mode]
        model = getattr(settings, f"{mode}_model")

        def work(cancel, progress):
            service = OpenAIService(key, proxy=settings.api_proxy_url or None)
            try:
                return service.transcribe(
                    audio,
                    model,
                    getattr(settings, f"{mode}_language"),
                    getattr(settings, f"{mode}_instructions"),
                )
            finally:
                service.close()

        def success(text):
            if self.closed or generation != self.generations[mode] or not text.strip():
                return
            self.transcript.emit(mode, text)
            if mode == "output" and settings.translation_enabled:
                if len(self.queues["translation"]) >= 6:
                    self.abort(mode)
                    self.completed.emit(mode, text, "", model)
                    self.error.emit(
                        mode,
                        "Translation is falling behind. Capture stopped; choose a faster translation model or disable translation.",
                    )
                    return
                self.queues["translation"].append((text, settings, key, model))
                self._translate()
            else:
                self.completed.emit(mode, text, "", model)

        def failure(message):
            if generation == self.generations[mode] and not self.closed:
                self.abort(mode)
                self.error.emit(mode, message)

        def done():
            self.busy[mode] = False
            self.pending_changed.emit(mode, len(self.queues[mode]))
            self._start(mode)

        self.pending_changed.emit(mode, len(self.queues[mode]) + 1)
        self.jobs.submit(work, success, failure, finished=done)

    def _translate(self):
        mode = "translation"
        if self.closed or self.busy[mode] or not self.queues[mode]:
            return
        self.busy[mode] = True
        text, settings, key, asr_model = self.queues[mode].popleft()
        self.active_translation = (text, asr_model)
        generation = self.generations[mode]

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
            if generation == self.generations[mode] and not self.closed:
                self.active_translation = None
                self.translation.emit("output", translated)
                self.completed.emit("output", text, translated, asr_model)

        def failed(message):
            if generation == self.generations[mode] and not self.closed:
                self.abort("output")
                self.error.emit("output", "Translation: " + message)

        def done():
            self.busy[mode] = False
            self._translate()

        self.jobs.submit(work, success, failed, finished=done)

    def shutdown(self):
        if self.closed:
            return
        self.closed = True
        self.abort("input")
        self.abort("output")
