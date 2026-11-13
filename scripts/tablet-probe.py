#!/usr/bin/env python3
"""Three-minute, API-free tablet event probe; logs no coordinates or drawn content."""

import argparse
import json
import os
import time
from pathlib import Path

from lang_handler.qt_platform import configure_platform

configure_platform()

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget

from lang_handler.ui.drawing_canvas import DrawingCanvas

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--log", default="/tmp/lang-in-out-tablet-events.jsonl")
parser.add_argument("--seconds", type=int, default=180)
parser.add_argument("--label", default="XP-Pen input check")
parser.add_argument("--left", action="store_true")
args = parser.parse_args()
log_path = Path(args.log)
descriptor = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
stream = os.fdopen(descriptor, "w", buffering=1)
application = QApplication([])
window = QWidget()
window.setWindowTitle("XP-Pen — " + args.label)
window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
window.resize(640, 450)
if args.left:
    window.move(40, 100)
layout = QVBoxLayout(window)
heading = QLabel(args.label)
heading.setStyleSheet("font-size:22px; font-weight:bold")
layout.addWidget(heading)
layout.addWidget(QLabel("Local input check only. No images or audio are sent to OpenAI."))
pen_button = QPushButton("Click this button with the pen, then draw a line below")
pen_button.setMinimumHeight(48)
layout.addWidget(pen_button)
canvas = DrawingCanvas()
layout.addWidget(canvas, 1)
status = QLabel("Waiting for pen input…")
layout.addWidget(status)
counts = {"tablet": 0, "mouse": 0, "strokes": 0, "button_clicks": 0}
started = time.monotonic()


class Probe(QObject):
    def eventFilter(self, target, event):
        if target is canvas:
            kind = event.type()
            tablet = kind in (
                QEvent.Type.TabletPress,
                QEvent.Type.TabletMove,
                QEvent.Type.TabletRelease,
            )
            mouse = kind in (
                QEvent.Type.MouseButtonPress,
                QEvent.Type.MouseMove,
                QEvent.Type.MouseButtonRelease,
            )
            if tablet or mouse:
                counts["tablet" if tablet else "mouse"] += 1
                record = {
                    "event": kind.name,
                    "device": event.pointingDevice().name(),
                    "spontaneous": event.spontaneous(),
                    "pressure": event.pressure() if tablet else None,
                    "button": event.button().name,
                    "buttons": event.buttons().value,
                    "source": "tablet" if tablet else event.source().name,
                    "strokes": len(canvas.strokes),
                }
                stream.write(json.dumps(record) + "\n")
                QTimer.singleShot(0, self.refresh)
        return False

    def refresh(self):
        counts["strokes"] = len(canvas.strokes)
        status.setText(
            f"Pen events: {counts['tablet']} · Mouse events: {counts['mouse']} · "
            f"Strokes: {counts['strokes']} · Button clicks: {counts['button_clicks']}"
        )


probe = Probe()
application.installEventFilter(probe)
canvas.changed.connect(lambda revision: probe.refresh())


def clicked():
    counts["button_clicks"] += 1
    pen_button.setText(f"Pen click received ({counts['button_clicks']}) — now draw below")
    stream.write(json.dumps({"event": "button_clicked", "counts": counts}) + "\n")
    probe.refresh()


pen_button.clicked.connect(clicked)
window.show()
window.raise_()
window.activateWindow()
QTimer.singleShot(max(5, args.seconds) * 1000, application.quit)
print(
    json.dumps({"pid": os.getpid(), "log": str(log_path), "platform": application.platformName()}),
    flush=True,
)
application.exec()
stream.write(
    json.dumps({"summary": counts, "duration_seconds": round(time.monotonic() - started, 1)}) + "\n"
)
stream.close()
