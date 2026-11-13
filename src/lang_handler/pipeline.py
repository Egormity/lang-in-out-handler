"""Ordered recognition and bounded contextual revisions for continuous captions."""

from collections import deque
from copy import deepcopy
from itertools import count

from PySide6.QtCore import QObject, Signal

from .api import OpenAIService
from .caption_recognition import GrowingCaptionWindow
from .errors import ServiceError
from .file_transcription import transcribe_file_once
from .google_api import GoogleService
from .jobs import Jobs
from .translation_context import next_context, translation_configuration


class CaptionPipeline(QObject):
    transcript = Signal(str, str, int)
    source_ready = Signal(str, int, str, str)
    source_revised = Signal(int, str)
    revisions = Signal(object)
    error = Signal(str, str)
    pending_changed = Signal(str, int)

    def __init__(self, jobs: Jobs, parent=None):
        super().__init__(parent)
        self.jobs = jobs
        self.queues = {mode: deque() for mode in ("input", "output", "translation")}
        self.busy = {mode: False for mode in self.queues}
        self.generations = {mode: 0 for mode in self.queues}
        self._segment_ids = count(1)
        self.context = []
        self.untranslated = set()
        self.context_signature = None
        self.translation_settings = None
        self.closed = False
        self.recognizer = GrowingCaptionWindow(self.allocate_segment_id)
        self._recognition_signature = None
        self._recognition_epoch = 0
        self._published_block = None
        self._published_text = ""

    def update_settings(self, settings):
        previous = self.translation_settings
        self.translation_settings = deepcopy(settings)
        if previous is not None and translation_configuration(previous) != translation_configuration(settings):
            self._reset_context()
            self._notify("output")

    def allocate_segment_id(self):
        """Allocate one identity shared by live recognition and file import workers."""
        return next(self._segment_ids)

    def begin_session(self, mode):
        """Start fresh context after the previous recording has finished draining."""
        self.abort(mode)

    def clear_translation_context(self):
        """Clearing visible captions starts a fresh passage without stopping audio."""
        self._reset_context()
        self._reset_recognition()
        self._notify("output")

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
            self._reset_context()
            self._reset_recognition()
        self._notify(mode)

    def _reset_context(self, signature=None):
        self.generations["translation"] += 1
        self.queues["translation"].clear()
        self.context.clear()
        self.untranslated.clear()
        self.context_signature = signature

    def _reset_recognition(self):
        self._recognition_epoch += 1
        self.recognizer.reset()
        self._recognition_signature = None
        self._published_block = None
        self._published_text = ""

    def _recognition_window(self, audio, settings, key):
        signature = (settings.output_model, settings.output_language, settings.output_instructions,
                     settings.output_context_seconds, settings.api_proxy_url, key)
        if signature != self._recognition_signature:
            self._reset_recognition()
            self.recognizer = GrowingCaptionWindow(
                self.allocate_segment_id, limit_seconds=settings.output_context_seconds
            )
            self._recognition_signature = signature
        return self.recognizer.accept(audio)

    def pending_count(self, mode):
        pending = len(self.queues[mode]) + int(self.busy[mode])
        if mode == "output":
            pending += max(
                len(self.untranslated),
                len(self.queues["translation"]) + int(self.busy["translation"]),
            )
        return pending

    def _notify(self, mode):
        self.pending_changed.emit(mode, self.pending_count(mode))

    def _start(self, mode):
        if self.closed or self.busy[mode] or not self.queues[mode]:
            return
        self.busy[mode] = True
        audio, settings, key = self.queues[mode].popleft()
        generation = self.generations[mode]
        model = getattr(settings, f"{mode}_model")
        window = None
        if mode == "output" and settings.output_chunked and settings.output_context_seconds:
            try:
                window = self._recognition_window(audio, settings, key)
            except (ServiceError, ValueError) as error:
                self.busy[mode] = False
                self.abort(mode)
                self.error.emit(mode, str(error))
                return
            if window is None:
                self.busy[mode] = False
                self._start(mode)
                self._notify(mode)
                return
            audio = window.audio
        elif mode == "output" and self._recognition_signature is not None:
            self._reset_recognition()
        recognition_epoch = self._recognition_epoch

        def work(cancel, progress):
            service = OpenAIService(key, proxy=settings.api_proxy_url or None)
            try:
                if not getattr(settings, f"{mode}_chunked"):
                    return transcribe_file_once(
                        service, audio, model, getattr(settings, f"{mode}_language"),
                        getattr(settings, f"{mode}_instructions"), cancel=cancel,
                    )
                return service.transcribe(
                    audio, model,
                    getattr(settings, f"{mode}_language"),
                    getattr(settings, f"{mode}_instructions"),
                    **({"context": window.prior_context} if window is not None else {}),
                )
            finally:
                service.close()

        def success(text):
            if (self.closed or generation != self.generations[mode]
                    or (window is not None and recognition_epoch != self._recognition_epoch)):
                return
            if window is not None:
                try:
                    accepted = self.recognizer.commit(window, text)
                except ServiceError as error:
                    failure(str(error))
                    return
                if not accepted:
                    return
                segment_id = window.block_id
                if segment_id == self._published_block:
                    if text != self._published_text:
                        self.source_revised.emit(segment_id, text)
                else:
                    self.source_ready.emit(mode, segment_id, text, model)
                    self.transcript.emit(mode, text, segment_id)
                self._published_block, self._published_text = segment_id, text
            else:
                if not text.strip():
                    return
                segment_id = self.allocate_segment_id()
                self.source_ready.emit(mode, segment_id, text, model)
                self.transcript.emit(mode, text, segment_id)
            if mode == "output":
                self._schedule_revision(segment_id, text, settings, key)

        def failure(message):
            if (generation == self.generations[mode] and not self.closed
                    and (window is None or recognition_epoch == self._recognition_epoch)):
                self.abort(mode)
                self.error.emit(mode, message)

        def done():
            self.busy[mode] = False
            self._start(mode)
            self._notify(mode)

        self._notify(mode)
        self.jobs.submit(work, success, failure, finished=done)

    def _schedule_revision(self, segment_id, text, settings, key):
        settings = self.translation_settings or settings
        signature = (*translation_configuration(settings),
                     key if settings.translation_provider == "openai" else "")
        if signature != self.context_signature:
            self._reset_context(signature)
        if not settings.translation_enabled:
            return
        recent = next_context(self.context, (segment_id, text), settings.translation_provider)
        if recent == self.context:
            return
        retained_ids = {item[0] for item in recent}
        if self.untranslated - retained_ids:
            # Coalescing must not silently skip a source that was never translated.
            self.abort("output")
            self.error.emit(
                "output",
                "Caption translation is falling behind. Capture stopped; all recognized text is saved. Increase chunk duration or choose a faster translation model.",
            )
            return
        self.context = recent
        self.untranslated.add(segment_id)
        # One active call plus one newest snapshot; superseded snapshots cost no requests.
        self.queues["translation"].clear()
        self.queues["translation"].append((list(recent), settings, key))
        self._translate()
        self._notify("output")

    def _translate(self):
        mode = "translation"
        if self.closed or self.busy[mode] or not self.queues[mode]:
            return
        self.busy[mode] = True
        segments, settings, key = self.queues[mode].popleft()
        generation = self.generations[mode]

        def current_sources():
            current = dict(self.context)
            return all(current.get(segment_id) == text for segment_id, text in segments)

        def work(cancel, progress):
            google = settings.translation_provider == "google"
            service = (GoogleService(proxy=settings.api_proxy_url or None) if google else
                       OpenAIService(key, proxy=settings.api_proxy_url or None))
            try:
                if google:
                    return service.revise_translation(segments, settings.target_language)
                return service.revise_captions(
                    segments, settings.translation_model, settings.target_language,
                    settings.translation_instructions, settings.translation_reasoning,
                )
            finally:
                service.close()

        def success(revisions):
            if generation == self.generations[mode] and not self.closed and current_sources():
                self.untranslated.difference_update(item.segment_id for item in revisions)
                self.revisions.emit(revisions)

        def failed(message):
            if generation == self.generations[mode] and not self.closed and current_sources():
                self.abort("output")
                self.error.emit("output", "Translation: " + message)

        def done():
            self.busy[mode] = False
            self._translate()
            self._notify("output")

        self.jobs.submit(work, success, failed, finished=done)

    def shutdown(self):
        if self.closed:
            return
        self.closed = True
        self.abort("input")
        self.abort("output")
