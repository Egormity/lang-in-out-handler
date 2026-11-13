"""Debounced handwriting recognition controls; API work stays in the controller."""

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QLayout, QScrollArea, QVBoxLayout, QWidget

from .common import button, label
from .drawing_window import DrawingWindow
from .drawing_workspace import DrawingWorkspace
from .icons import icon, icon_button
from .tool_settings import ToolSettings, ToolSettingsDialog


class DrawingPage(QWidget):
    requested = Signal(bytes, int)
    cancel_requested = Signal()
    speech_requested = Signal(str)
    speech_stop_requested = Signal()
    settings_saved = Signal(object)

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
        self.body_layout = layout
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(10)
        self.scroll.setWidget(body)
        outer.addWidget(self.scroll)
        heading = QHBoxLayout()
        title = label("Draw")
        title.setObjectName("title")
        heading.addWidget(title, 1)
        self.float_button = button("Float")
        self.float_button.setObjectName("quiet")
        self.float_button.setIcon(icon("float"))
        self.float_button.clicked.connect(self.show_floating)
        heading.addWidget(self.float_button)
        self.settings_button = icon_button("settings", "Handwriting settings")
        heading.addWidget(self.settings_button)
        layout.addLayout(heading)
        self.tool_settings = ToolSettings("drawing", settings)
        self.tool_settings.saved.connect(self.settings_saved)
        self.settings_dialog = ToolSettingsDialog(self.tool_settings, "Handwriting", self)
        self.settings_button.clicked.connect(self.settings_dialog.show_settings)
        self.workspace = DrawingWorkspace(settings)
        # Keep a single set of public controls for the existing controller interface.
        for name in (
            "canvas",
            "result",
            "send_button",
            "undo_button",
            "redo_button",
            "clear_button",
            "status",
        ):
            setattr(self, name, getattr(self.workspace, name))
        layout.addWidget(self.workspace, 1)
        self.result.speech_requested.connect(self.speech_requested)
        self.result.speech_stop_requested.connect(self.speech_stop_requested)
        self.floating = DrawingWindow(settings.drawing_on_top)
        self.floating.dock_requested.connect(self.dock_workspace)
        self.destroyed.connect(self.floating.deleteLater)
        self.is_floating = False
        self._floating_positioned = False
        self.placeholder = QWidget()
        placeholder_layout = QVBoxLayout(self.placeholder)
        placeholder_layout.addWidget(
            label("Your canvas is open in the floating handwriting window.", True)
        )
        restore = button("Dock canvas here")
        restore.clicked.connect(self.dock_workspace)
        placeholder_layout.addWidget(restore)
        placeholder_layout.addStretch()
        self.placeholder.hide()
        layout.addWidget(self.placeholder, 1)
        self.undo_button.clicked.connect(self.canvas.undo)
        self.redo_button.clicked.connect(self.canvas.redo)
        self.clear_button.clicked.connect(self.canvas.clear)
        self.send_button.clicked.connect(self.send)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(settings.drawing_debounce_ms)
        self.timer.timeout.connect(self.send)
        self.canvas.changed.connect(self._canvas_changed)
        self.undo_button.setEnabled(False)
        self.redo_button.setEnabled(False)
        self.clear_button.setEnabled(False)

    def show_floating(self):
        if not self.is_floating:
            self.body_layout.removeWidget(self.workspace)
            self.floating.set_workspace(self.workspace)
            self.is_floating = True
            self.placeholder.show()
            self.float_button.setText("Show canvas")
        if not self._floating_positioned:
            self.floating.move(
                self.window().frameGeometry().center() - self.floating.rect().center()
            )
            self._floating_positioned = True
        self.floating.show_workspace()

    def dock_workspace(self):
        if self.is_floating:
            self.floating.take_workspace()
            self.body_layout.insertWidget(1, self.workspace, 1)
            self.workspace.show()
            self.is_floating = False
            self.placeholder.hide()
            self.float_button.setText("Float")
        self.floating.hide()

    def shutdown(self):
        self.timer.stop()
        self.floating.pin_control.stop()
        self.dock_workspace()

    def _canvas_changed(self, revision):
        self.timer.stop()
        blank = self.canvas.is_blank
        self.undo_button.setEnabled(self.canvas.can_undo)
        self.redo_button.setEnabled(self.canvas.can_redo)
        self.clear_button.setEnabled(not blank)
        self.send_button.setEnabled(not blank and not self.canvas.is_drawing)
        self.result.clear()
        if blank:
            self.status.setText("")
            self.cancel_requested.emit()
        elif self.canvas.is_drawing:
            self.status.setText("Drawing…")
        else:
            self.status.setText(
                "Waiting to recognize…" if self.settings.drawing_auto_send else "Ready to send."
            )
            self._schedule()

    def _schedule(self):
        if (
            self.settings.drawing_auto_send
            and not self.canvas.is_blank
            and not self.canvas.is_drawing
        ):
            self.timer.start(self.settings.drawing_debounce_ms)

    def send(self):
        self.timer.stop()
        if self.canvas.is_blank or self.canvas.is_drawing:
            return
        self.requested.emit(self.canvas.snapshot(), self.canvas.revision)

    def set_result(self, items, revision):
        if revision == self.canvas.revision:
            self.result.set_items(items)
            self.status.setText(
                "" if items else "No readable handwriting found."
            )

    def set_busy(self, busy):
        self.busy = busy
        if busy:
            self.status.setText("Recognizing handwriting…")
        elif self.status.text() == "Recognizing handwriting…" and not self.canvas.is_blank:
            self.status.setText("Ready to send.")

    def set_speech_active(self, active):
        self.result.set_speech_active(active)

    def update_settings(self, settings):
        was_enabled = self.settings.drawing_auto_send
        delay_changed = self.settings.drawing_debounce_ms != settings.drawing_debounce_ms
        self.settings = settings
        self.tool_settings.update_settings(settings)
        self.canvas.pen_width = settings.drawing_pen_width
        self.canvas.set_theme(settings.drawing_canvas_theme)
        if self.floating.pin_control.desired != settings.drawing_on_top:
            self.floating.pin_control.request(settings.drawing_on_top)
        if was_enabled and not settings.drawing_auto_send:
            self.timer.stop()
            self.cancel_requested.emit()
        elif (not was_enabled and settings.drawing_auto_send) or (
            delay_changed and self.timer.isActive()
        ):
            self._schedule()
