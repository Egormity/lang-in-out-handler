"""A compact handwriting editor shared by docked and floating views."""

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from .common import button, label
from .drawing_candidates import DrawingCandidates
from .drawing_canvas import DrawingCanvas


class DrawingWorkspace(QWidget):
    def __init__(self, settings):
        super().__init__()
        self.setObjectName("drawingWorkspace")
        self.setStyleSheet("QWidget#drawingWorkspace QPushButton { padding: 5px 10px; }")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        tools = QHBoxLayout()
        self.undo_button = button("Undo")
        self.undo_button.setToolTip("Remove the last stroke.")
        self.clear_button = button("Clear")
        self.clear_button.setToolTip("Clear the canvas and recognized readings.")
        tools.addWidget(self.undo_button)
        tools.addWidget(self.clear_button)
        tools.addStretch()
        self.send_button = button("Send to transcribe", True)
        self.send_button.setEnabled(False)
        tools.addWidget(self.send_button)
        layout.addLayout(tools)
        self.canvas = DrawingCanvas()
        self.canvas.pen_width = settings.drawing_pen_width
        self.canvas.setMinimumHeight(240)
        layout.addWidget(self.canvas, 3)
        self.status = label("Draw something to begin.", True)
        layout.addWidget(self.status)
        self.result = DrawingCandidates()
        layout.addWidget(self.result, 1)
