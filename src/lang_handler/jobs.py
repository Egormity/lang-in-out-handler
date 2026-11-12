"""Bounded background work with results delivered on the Qt UI thread."""

import re
import threading
from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot


def safe_error(error: Exception) -> str:
    return re.sub(r"sk-[A-Za-z0-9_-]+", "[redacted]", str(error))[:700]


class JobSignals(QObject):
    result = Signal(object)
    failed = Signal(str)
    progress = Signal(object)
    finished = Signal()


class Job(QRunnable):
    def __init__(self, work: Callable):
        super().__init__()
        self.signals = JobSignals()
        self.work = work
        self.cancelled = threading.Event()

    @Slot()
    def run(self):
        try:
            if not self.cancelled.is_set():
                result = self.work(self.cancelled, self.signals.progress.emit)
                if not self.cancelled.is_set():
                    self.signals.result.emit(result)
        except Exception as exc:  # noqa: BLE001 - worker boundary must report failures through Qt
            if not self.cancelled.is_set():
                self.signals.failed.emit(safe_error(exc))
        finally:
            self.signals.finished.emit()


class Jobs(QObject):
    """Keep Python signal objects alive until their worker completes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(4)
        self.active: set[Job] = set()

    def submit(self, work, result=None, failed=None, progress=None, finished=None):
        job = Job(work)

        # Cancellation can happen after a worker emits, before Qt delivers the queued signal.
        # Check again on the receiving thread so stale results cannot update a new operation.
        def deliver(callback):
            def guarded(*args):
                if not job.cancelled.is_set():
                    callback(*args)

            return guarded

        if result:
            job.signals.result.connect(deliver(result))
        if failed:
            job.signals.failed.connect(deliver(failed))
        if progress:
            job.signals.progress.connect(deliver(progress))
        if finished:
            job.signals.finished.connect(finished)
        job.signals.finished.connect(lambda: self.active.discard(job))
        self.active.add(job)
        self.pool.start(job)
        return job

    def cancel_all(self):
        for job in self.active:
            job.cancelled.set()
