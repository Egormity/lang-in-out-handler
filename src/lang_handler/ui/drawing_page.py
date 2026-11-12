"""Debounced handwriting recognition controls; API work stays in the controller."""

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLayout,
    QPlainTextEdit,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .common import TextPane, button, label, title_block
from .drawing_canvas import DrawingCanvas


class DrawingPage(QWidget):
    requested = Signal(bytes, int)
    cancel_requested = Signal()
    options_changed = Signal()

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.busy = False
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(10)
        self.scroll.setWidget(body)
        outer.addWidget(self.scroll)
        layout.addWidget(
            title_block(
                "Handwriting", "Write characters or words, then turn them into editable text."
            )
        )
        layout.addWidget(label("Recognition instructions"))
        self.instructions = QPlainTextEdit(settings.drawing_instructions)
        self.instructions.setAccessibleName("Handwriting recognition instructions")
        self.instructions.setMaximumHeight(66)
        layout.addWidget(self.instructions)
        toolbar = QHBoxLayout()
        self.undo_button = button("Undo stroke")
        self.clear_button = button("Clear canvas")
        self.pen = QSpinBox()
        self.pen.setRange(1, 16)
        self.pen.setValue(4)
        self.pen.setPrefix("Pen: ")
        self.pen.setSuffix(" px")
        self.pen.setMaximumWidth(130)
        toolbar.addWidget(self.undo_button)
        toolbar.addWidget(self.clear_button)
        toolbar.addStretch()
        toolbar.addWidget(self.pen)
        layout.addLayout(toolbar)
        self.canvas = DrawingCanvas()
        self.pen.valueChanged.connect(lambda value: setattr(self.canvas, "pen_width", value))
        self.undo_button.clicked.connect(self.canvas.undo)
        self.clear_button.clicked.connect(self.canvas.clear)
        layout.addWidget(self.canvas, 3)
        options = QHBoxLayout()
        self.auto_send = QCheckBox("Automatically recognize after drawing")
        self.auto_send.setChecked(settings.drawing_auto_send)
        options.addWidget(self.auto_send)
        options.addStretch()
        self.send_button = button("Send to transcribe", True)
        self.send_button.setEnabled(False)
        self.send_button.clicked.connect(self.send)
        options.addWidget(self.send_button)
        layout.addLayout(options)
        layout.addWidget(
            label(
                "Automatic recognition sends the canvas image to OpenAI. Set its delay in Preferences.",
                True,
            )
        )
        self.status = label("Draw something to begin.", True)
        layout.addWidget(self.status)
        self.result = TextPane(
            "Recognized text", "Your handwriting will appear here as text.", False
        )
        layout.addWidget(self.result, 2)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(settings.drawing_debounce_ms)
        self.timer.timeout.connect(self.send)
        self.canvas.changed.connect(self._canvas_changed)
        self.auto_send.toggled.connect(self._auto_changed)
        self.undo_button.setEnabled(False)
        self.clear_button.setEnabled(False)

    def _canvas_changed(self, revision):
        self.timer.stop()
        blank = self.canvas.is_blank
        self.undo_button.setEnabled(not blank)
        self.clear_button.setEnabled(not blank)
        self.send_button.setEnabled(not blank and not self.canvas.is_drawing)
        self.result.text.clear()
        if blank:
            self.status.setText("Draw something to begin.")
            self.cancel_requested.emit()
        elif self.canvas.is_drawing:
            self.status.setText("Drawing…")
        else:
            self.status.setText(
                "Waiting to recognize…" if self.auto_send.isChecked() else "Ready to send."
            )
            self._schedule()

    def _schedule(self):
        if self.auto_send.isChecked() and not self.canvas.is_blank and not self.canvas.is_drawing:
            self.timer.start(self.settings.drawing_debounce_ms)

    def _auto_changed(self, enabled):
        self.timer.stop()
        if not enabled:
            self.cancel_requested.emit()
        self.options_changed.emit()
        if enabled:
            self._schedule()

    def send(self):
        self.timer.stop()
        if self.canvas.is_blank or self.canvas.is_drawing:
            return
        self.requested.emit(self.canvas.snapshot(), self.canvas.revision)

    def set_result(self, text, revision):
        if revision == self.canvas.revision:
            self.result.text.setPlainText(text)
            self.status.setText("Recognition ready. You can edit or copy the text.")

    def set_busy(self, busy):
        self.busy = busy
        if busy:
            self.status.setText("Recognizing handwriting…")
        elif not self.result.text.toPlainText() and not self.canvas.is_blank:
            self.status.setText("Ready to send.")

    def update_settings(self, settings):
        was_enabled = self.auto_send.isChecked()
        delay_changed = self.settings.drawing_debounce_ms != settings.drawing_debounce_ms
        self.settings = settings
        self.instructions.setPlainText(settings.drawing_instructions)
        self.auto_send.blockSignals(True)
        self.auto_send.setChecked(settings.drawing_auto_send)
        self.auto_send.blockSignals(False)
        if was_enabled and not settings.drawing_auto_send:
            self.timer.stop()
            self.cancel_requested.emit()
        elif (not was_enabled and settings.drawing_auto_send) or (
            delay_changed and self.timer.isActive()
        ):
            self._schedule()
