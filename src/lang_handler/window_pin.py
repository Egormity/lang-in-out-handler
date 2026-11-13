"""Keep floating windows above on X11 or through verified GNOME Wayland controls."""

import json
import os
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QProcess, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication


class WindowPin(QObject):
    changed = Signal(bool)
    message = Signal(str)

    def __init__(self, window, enabled=True):
        super().__init__(window)
        self.window = window
        self.desired = enabled
        self.confirmed = False
        self.verified = False
        self.auto_pending = False
        self.process = None
        self.window.installEventFilter(self)
        self.timeout = QTimer(self)
        self.timeout.setSingleShot(True)
        self.timeout.timeout.connect(self._timeout)

    @property
    def native_wayland(self):
        return QGuiApplication.platformName().startswith("wayland")

    def request(self, enabled, activate=False):
        self.desired = bool(enabled)
        self.auto_pending = True
        if not self.native_wayland:
            visible, geometry = self.window.isVisible(), self.window.geometry()
            self.window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, self.desired)
            self.window.setGeometry(geometry)
            if visible:
                self.window.show()
            self.confirmed, self.verified = self.desired, True
            self.auto_pending = False
            self.changed.emit(self.confirmed)
            self.message.emit("")
            return
        self.changed.emit(self.confirmed)
        if activate:
            self.window.activateWindow()
        QTimer.singleShot(100, self._attempt)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.WindowActivate and self.auto_pending:
            QTimer.singleShot(100, self._attempt)
        return False

    def on_show(self):
        if self.native_wayland:
            # A hidden Wayland surface may be recreated as a new compositor window.
            self.confirmed, self.verified = False, False
        self.request(self.desired)

    def _attempt(self):
        if self.process or not self.window.isVisible() or not self.auto_pending:
            return
        if self.verified and self.confirmed == self.desired:
            return
        if not self.window.isActiveWindow():
            self.message.emit("Click this window to apply On top.")
            return
        self.message.emit("Applying On top…")
        self.auto_pending = False
        process = QProcess(self)
        self.process = process
        process.finished.connect(self._finished)
        process.errorOccurred.connect(self._process_error)
        process.start(
            "/usr/bin/python3",
            [
                str(Path(__file__).with_name("gnome_pin.py")),
                str(os.getpid()),
                self.window.windowTitle(),
                "true" if self.desired else "false",
            ],
        )
        self.timeout.start(6000)

    def _finished(self, exit_code, exit_status):
        process = self.process
        if process is None:
            return
        self.process = None
        self.timeout.stop()
        try:
            result = json.loads(bytes(process.readAllStandardOutput()).decode().strip())
        except (ValueError, UnicodeError):
            result = {
                "ok": False,
                "message": "Could not verify On top. Click the window and try again.",
            }
        process.deleteLater()
        if result.get("ok"):
            self.confirmed = bool(result["above"])
            self.verified = True
            self.changed.emit(self.confirmed)
            self.message.emit("")
            if self.desired != self.confirmed:
                QTimer.singleShot(100, self._attempt)
        else:
            self.verified = False
            self.auto_pending = True
            self.changed.emit(self.confirmed)
            self.message.emit(result.get("message", "Could not verify On top."))

    def _process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.timeout.stop()
            self.verified = False
            self.auto_pending = True
            if self.process:
                self.process.deleteLater()
                self.process = None
            self.message.emit("On top needs the system Python and GNOME accessibility service.")

    def _timeout(self):
        if self.process:
            self.verified = False
            self.auto_pending = True
            self.process.kill()
            self.message.emit("On top verification timed out. Try again after focusing the window.")

    def stop(self):
        self.timeout.stop()
        if self.process:
            self.process.terminate()
            self.process.waitForFinished(1000)
            if self.process:
                self.process.kill()
        self.auto_pending = False
