"""Coalesce canvas recognition work and discard results for outdated drawings."""

from copy import deepcopy

from PySide6.QtCore import QObject

from .api import OpenAIService


class Handwriting(QObject):
    def __init__(self, controller):
        super().__init__(controller)
        self.c = controller
        self.job = None
        self.pending = None
        self.epoch = 0
        self._active_signature = None

    @staticmethod
    def _signature(request):
        png, revision, settings, key = request
        return (
            png, revision, key, settings.drawing_model, settings.drawing_instructions,
            settings.drawing_reasoning, settings.drawing_language, settings.api_proxy_url,
        )

    def recognize(self, png, revision):
        if not png or revision != self.c.window.drawing_revision():
            return
        key = self.c.require_key()
        if not key:
            return
        # At most one active request and one pending snapshot. New changes replace
        # the pending snapshot rather than spending API credit on obsolete canvases.
        request = (png, revision, deepcopy(self.c.settings), key)
        if self.job:
            signature = self._signature(request)
            if not self.job.cancelled.is_set() and signature == self._active_signature:
                return
            if self.pending and signature == self._signature(self.pending):
                return
            self.pending = request
            self.c.window.set_drawing_busy(True)
            return
        self._start(request)

    def _start(self, request):
        png, revision, settings, key = request
        epoch = self.epoch
        self._active_signature = self._signature(request)
        self.c.window.set_drawing_busy(True)

        def work(cancel, progress):
            service = OpenAIService(key, proxy=settings.api_proxy_url or None)
            try:
                return service.recognize_handwriting(
                    png,
                    settings.drawing_model,
                    settings.drawing_instructions,
                    reasoning=settings.drawing_reasoning,
                    language=settings.drawing_language,
                )
            finally:
                service.close()

        def success(items):
            if epoch != self.epoch or revision != self.c.window.drawing_revision():
                return
            self.c.window.set_drawing_result(items, revision)
            if items:
                for text in items:
                    self.c.remember("drawing", text, "", settings.drawing_model)

        def failed(message):
            if epoch == self.epoch and revision == self.c.window.drawing_revision():
                self.c.fail(message)

        def done():
            self.job = None
            self._active_signature = None
            request = self.pending
            self.pending = None
            if request and request[1] == self.c.window.drawing_revision():
                self._start(request)
            else:
                self.c.window.set_drawing_busy(False)

        self.job = self.c.jobs.submit(work, success, failed, finished=done)

    def cancel(self):
        self.epoch += 1
        self.pending = None
        if self.job:
            self.job.cancelled.set()
        self.c.window.set_drawing_busy(False)
