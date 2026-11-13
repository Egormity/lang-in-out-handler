"""One handwriting editor shared by the docked and floating views."""

from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .common import TextPane, button, label
from .drawing_canvas import DrawingCanvas
from .sections import ExpandableSection


class DrawingWorkspace(QWidget):
    def __init__(self, settings):
        super().__init__()
        self.setObjectName("drawingWorkspace")
        self.setStyleSheet(
            "QWidget#drawingWorkspace QPushButton { padding: 5px 10px; }"
            "QWidget#drawingWorkspace QSpinBox { padding: 5px 8px; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        tools = QHBoxLayout()
        self.undo_button = button("Undo")
        self.undo_button.setToolTip("Remove the last stroke.")
        self.clear_button = button("Clear")
        self.clear_button.setToolTip("Clear the canvas and recognized text.")
        self.pen = QSpinBox()
        self.pen.setRange(1, 16)
        self.pen.setValue(4)
        self.pen.setPrefix("Pen: ")
        self.pen.setSuffix(" px")
        self.pen.setMaximumWidth(120)
        tools.addWidget(self.undo_button)
        tools.addWidget(self.clear_button)
        tools.addStretch()
        tools.addWidget(self.pen)
        layout.addLayout(tools)

        self.canvas = DrawingCanvas()
        self.canvas.setMinimumHeight(240)
        layout.addWidget(self.canvas, 3)
        options = QHBoxLayout()
        self.auto_send = QCheckBox("Auto recognize")
        self.auto_send.setChecked(settings.drawing_auto_send)
        self.auto_send.setToolTip(
            "Send the canvas to OpenAI after you stop drawing. Change the delay in Preferences."
        )
        self.send_button = button("Send to transcribe", True)
        self.send_button.setEnabled(False)
        options.addWidget(self.auto_send)
        options.addStretch()
        options.addWidget(self.send_button)
        layout.addLayout(options)
        self.status = label("Draw something to begin.", True)
        layout.addWidget(self.status)

        self.result = TextPane("Recognized text", "Edit or copy the recognized text here.", False)
        self.result.text.setMinimumHeight(76)
        self.result.setMaximumHeight(150)
        layout.addWidget(self.result, 1)

        self.advanced = ExpandableSection("Recognition instructions")
        self.advanced_toggle = self.advanced.toggle
        self.advanced_toggle.setAccessibleName("Show recognition instructions")
        layout.addWidget(self.advanced)
        self.instructions = QPlainTextEdit(settings.drawing_instructions)
        self.instructions.setAccessibleName("Handwriting recognition instructions")
        self.instructions.setPlaceholderText("Language, vocabulary, or formatting hints…")
        self.instructions.setFixedHeight(80)
        self.advanced.body_layout.addWidget(self.instructions)
