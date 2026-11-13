"""The same uncluttered canvas in docked and floating views."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from .common import button, label
from .drawing_candidates import DrawingCandidates
from .drawing_canvas import DrawingCanvas
from .icons import icon_button


class DrawingWorkspace(QWidget):
    def __init__(self, settings):
        super().__init__()
        self.setObjectName("drawingWorkspace")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        tools = QHBoxLayout()
        tools.setSpacing(2)
        self.undo_button = icon_button("undo", "Undo drawing (Ctrl+Z)")
        self.redo_button = icon_button("redo", "Redo drawing (Ctrl+Shift+Z)")
        self.clear_button = icon_button("clear", "Clear canvas")
        tools.addWidget(self.undo_button)
        tools.addWidget(self.redo_button)
        tools.addWidget(self.clear_button)
        tools.addStretch()
        layout.addLayout(tools)
        self.canvas = DrawingCanvas()
        self.canvas.set_theme(settings.drawing_canvas_theme)
        self.undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.redo_shortcut = QShortcut(QKeySequence("Ctrl+Shift+Z"), self)
        for shortcut in (self.undo_shortcut, self.redo_shortcut):
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.undo_shortcut.activated.connect(self.canvas.undo)
        self.redo_shortcut.activated.connect(self.canvas.redo)
        self.canvas.pen_width = settings.drawing_pen_width
        self.canvas.setMinimumHeight(200)
        layout.addWidget(self.canvas, 3)
        self.result = DrawingCandidates()
        layout.addWidget(self.result, 1)
        footer = QHBoxLayout()
        self.status = label("", True)
        footer.addWidget(self.status, 1)
        self.send_button = button("Recognize", True)
        self.send_button.setAccessibleName("Send canvas to transcribe")
        self.send_button.setEnabled(False)
        footer.addWidget(self.send_button)
        layout.addLayout(footer)
