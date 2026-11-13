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

    def recognize(self, png, revision):
        key = self.c.require_key()
        if not key:
            return
        # At most one active request and one pending snapshot. New changes replace
        # the pending snapshot rather than spending API credit on obsolete canvases.
        request = (png, revision, deepcopy(self.c.settings), key)
        if self.job:
            self.pending = request
            return
        self._start(request)

    def _start(self, request):
        png, revision, settings, key = request
        epoch = self.epoch
        self.c.window.set_drawing_busy(True)
        self.c.status("Reading handwriting…")

        def work(cancel, progress):
            service = OpenAIService(key, proxy=settings.api_proxy_url or None)
            try:
                return service.recognize_handwriting(
                    png, settings.drawing_model, settings.drawing_instructions
                )
            finally:
                service.close()

        def success(text):
            if epoch != self.epoch or revision != self.c.window.drawing_revision():
                return
            self.c.window.set_drawing_result(text, revision)
            if text:
                self.c.remember("drawing", text, "", settings.drawing_model)
                self.c.status("Handwriting recognized.")
            else:
                self.c.status("No readable handwriting found. Try larger, clearer strokes.")

        def failed(message):
            if epoch == self.epoch and revision == self.c.window.drawing_revision():
                self.c.fail(message)

        def done():
            self.job = None
            self.c.window.set_drawing_busy(False)
            request = self.pending
            self.pending = None
            if request and request[1] == self.c.window.drawing_revision():
                self._start(request)

        self.job = self.c.jobs.submit(work, success, failed, finished=done)

    def cancel(self):
        self.epoch += 1
        self.pending = None
        if self.job:
            self.job.cancelled.set()
        self.c.window.set_drawing_busy(False)
