"""Deliver dictated chunks in order without blocking the desktop event loop."""

from collections import deque

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from .desktop import deliver_transcript


class DictationDelivery(QObject):
    def __init__(self, controller):
        super().__init__(controller)
        self.c = controller
        self.queue = deque()
        self.busy = False
        self.last_pasted = ""
        self.epoch = 0
        self.closed = False

    def reset(self):
        self.last_pasted = ""
        self.epoch += 1

    def enqueue(self, text, mode):
        self.queue.append((text, mode, QApplication.activeWindow() is None, self.epoch))
        self._start()

    def _start(self):
        if self.closed or self.busy or not self.queue:
            return
        text, mode, allow_paste, epoch = self.queue.popleft()
        allow_paste = allow_paste and QApplication.activeWindow() is None
        paste = allow_paste and mode in ("paste", "copy_and_paste")
        previous = self.last_pasted if epoch == self.epoch else ""
        separator = " " if (paste and previous and text and
                             previous[-1].isascii() and text[0].isascii()) else ""
        self.busy = True

        def success(message):
            if epoch == self.epoch:
                self.last_pasted = text if message.startswith("Pasted") else ""
            self.c.status(message)

        def done():
            self.busy = False
            self._start()

        def failed(message):
            if epoch == self.epoch:
                self.last_pasted = ""
            self.c.fail("Transcript ready; delivery failed: " + message)

        self.c.jobs.submit(
            lambda cancel, progress: deliver_transcript(
                separator + text, mode, allow_paste=allow_paste
            ),
            success,
            failed,
            finished=done,
        )

    def close(self):
        self.closed = True
        self.queue.clear()
