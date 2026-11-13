"""An independent, pinnable host for the shared handwriting editor."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from ..window_pin import WindowPin
from .icons import icon_button
from .theme import STYLE


class DrawingWindow(QWidget):
    dock_requested = Signal()

    def __init__(self, on_top=True):
        super().__init__()
        self.setWindowTitle("Lang In/Out · Handwriting")
        self.setWindowFlags(Qt.WindowType.Tool)
        self.setStyleSheet(STYLE)
        self.resize(650, 530)
        self.setMinimumSize(440, 440)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 12)
        layout.setSpacing(8)
        toolbar = QHBoxLayout()
        title = QLabel("Draw")
        title.setObjectName("section")
        toolbar.addWidget(title)
        toolbar.addStretch()
        self.dock_button = icon_button("dock", "Dock canvas")
        self.dock_button.setObjectName("quiet")
        self.dock_button.clicked.connect(self.dock_requested)
        self.hide_button = icon_button("close", "Hide canvas")
        self.hide_button.setObjectName("quiet")
        self.hide_button.clicked.connect(self.hide)
        toolbar.addWidget(self.dock_button)
        toolbar.addWidget(self.hide_button)
        layout.addLayout(toolbar)
        self.pin_status = QLabel()
        self.pin_status.setObjectName("muted")
        self.pin_status.setWordWrap(True)
        self.pin_status.hide()
        layout.addWidget(self.pin_status)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        layout.addWidget(self.scroll, 1)
        self.pin_control = WindowPin(self, on_top)
        self.pin_control.message.connect(self._pin_message)
        self.pin_control.request(on_top)

    def set_workspace(self, workspace):
        self.scroll.setWidget(workspace)
        workspace.show()

    def take_workspace(self):
        return self.scroll.takeWidget()

    def show_workspace(self):
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.show()
        self.raise_()
        # A tablet/mouse click must be able to focus the editor after initial display.
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
        self.pin_control.request(self.pin_control.desired, activate=True)

    def _pin_message(self, message):
        self.pin_status.setText(message)
        self.pin_status.setVisible(bool(message))

    def showEvent(self, event):
        super().showEvent(event)
        self.pin_control.on_show()

    def closeEvent(self, event):
        self.pin_control.stop()
        self.dock_requested.emit()
        event.accept()
