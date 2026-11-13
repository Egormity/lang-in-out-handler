"""One scrolling canvas/result document, reused in the page and floating window."""

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QLayout, QScrollArea, QVBoxLayout, QWidget

from .common import button
from .drawing_candidates import DrawingCandidates
from .drawing_canvas import DrawingCanvas
from .icons import icon_button


class DrawingWorkspace(QWidget):
    def __init__(self, settings):
        super().__init__()
        self.setObjectName("drawingWorkspace")
        self._floating = False
        self._window_buttons = ()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.toolbar = QWidget()
        self.tools = QHBoxLayout(self.toolbar)
        self.tools.setContentsMargins(0, 0, 0, 0)
        self.tools.setSpacing(2)
        self.left_controls = self._control_group()
        self.right_controls = self._control_group()
        self.undo_button = icon_button("undo", "Undo drawing (Ctrl+Z)")
        self.redo_button = icon_button("redo", "Redo drawing (Ctrl+Shift+Z)")
        self.clear_button = icon_button("clear", "Clear canvas")
        for control in (self.undo_button, self.redo_button, self.clear_button):
            self.left_controls.layout().addWidget(control)
        self.send_button = button("Recognize", True)
        self.send_button.setAccessibleName("Send canvas to transcribe")
        self.send_button.setEnabled(False)
        self.right_controls.layout().addWidget(self.send_button)
        self.tools.addWidget(self.left_controls)
        self.tools.addStretch()
        self.tools.addWidget(self.right_controls)
        layout.addWidget(self.toolbar)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.viewport().installEventFilter(self)
        self.body = QWidget()
        self.document = QVBoxLayout(self.body)
        self.document.setContentsMargins(0, 0, 0, 0)
        self.document.setSpacing(8)
        self.document.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.document.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.canvas_frame = QWidget()
        frame_layout = QVBoxLayout(self.canvas_frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        self.canvas_frame.installEventFilter(self)
        self.canvas = DrawingCanvas()
        self.canvas.set_theme(settings.drawing_canvas_theme)
        self.canvas.pen_width = settings.drawing_pen_width
        self.canvas.installEventFilter(self)
        self.canvas.setFixedHeight(300)
        frame_layout.addWidget(self.canvas)
        self.document.addWidget(self.canvas_frame)
        self.result = DrawingCandidates()
        self.document.addWidget(self.result)
        self.scroll.setWidget(self.body)
        layout.addWidget(self.scroll, 1)
        self.undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.redo_shortcut = QShortcut(QKeySequence("Ctrl+Shift+Z"), self)
        for shortcut in (self.undo_shortcut, self.redo_shortcut):
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.undo_shortcut.activated.connect(self.canvas.undo)
        self.redo_shortcut.activated.connect(self.canvas.redo)

    def _control_group(self):
        group = QWidget()
        group.setObjectName("canvasControls")
        row = QHBoxLayout(group)
        row.setContentsMargins(2, 2, 2, 2)
        row.setSpacing(2)
        group.installEventFilter(self)
        return group

    def set_floating(self, enabled, window_buttons=()):
        """Only the compact button clusters intercept input over the canvas."""
        self._floating = enabled
        if enabled:
            self._window_buttons = tuple(window_buttons)
            for group in (self.left_controls, self.right_controls):
                self.tools.removeWidget(group)
                # Controls are siblings of the tablet-aware canvas: unhandled
                # tablet input can become a normal button click, never an ink stroke.
                group.setParent(self.canvas_frame)
                group.setStyleSheet(
                    "QWidget#canvasControls { background: rgba(29, 32, 33, 235); "
                    "border-radius: 7px; }"
                )
                group.show()
            for control in self._window_buttons:
                self.right_controls.layout().addWidget(control)
                control.show()
            self.toolbar.hide()
            self._position_controls()
        else:
            for control in self._window_buttons:
                self.right_controls.layout().removeWidget(control)
                control.hide()
            self._window_buttons = ()
            for group in (self.left_controls, self.right_controls):
                group.setParent(self.toolbar)
                group.setStyleSheet("")
            self.tools.insertWidget(0, self.left_controls)
            self.tools.addWidget(self.right_controls)
            self.toolbar.show()
            self.left_controls.show()
            self.right_controls.show()
        self._fit_canvas()

    def _fit_canvas(self):
        # Reserve only a short result row. Additional readings extend the same
        # document instead of shrinking the pen area or creating another scrollbar.
        height = max(200, self.scroll.viewport().height() - 50)
        if self.canvas.height() != height:
            self.canvas.setFixedHeight(height)
        self.canvas_frame.setFixedHeight(height)

    def _position_controls(self):
        if not self._floating:
            return
        self.left_controls.adjustSize()
        self.right_controls.adjustSize()
        self.left_controls.move(8, 8)
        self.right_controls.move(self.canvas_frame.width() - self.right_controls.width() - 8, 8)
        self.left_controls.raise_()
        self.right_controls.raise_()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Resize:
            if watched is self.scroll.viewport():
                self._fit_canvas()
            elif watched is self.canvas or watched is self.canvas_frame:
                self._position_controls()
        elif event.type() == QEvent.Type.LayoutRequest and watched in (
            self.left_controls, self.right_controls
        ):
            self._position_controls()
        return super().eventFilter(watched, event)
