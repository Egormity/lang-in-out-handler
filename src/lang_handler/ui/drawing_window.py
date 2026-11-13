"""An independent, pinnable host for the shared handwriting editor."""

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from ..window_pin import WindowPin
from .common import button
from .theme import STYLE


class DrawingWindow(QWidget):
    dock_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Lang In/Out · Handwriting")
        self.setWindowFlags(Qt.WindowType.Tool)
        self.setStyleSheet(STYLE)
        self.resize(750, 600)
        self.setMinimumSize(480, 480)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 12)
        layout.setSpacing(8)
        toolbar = QHBoxLayout()
        title = QLabel("Handwriting")
        title.setObjectName("section")
        toolbar.addWidget(title)
        toolbar.addStretch()
        self.pin = QCheckBox("On top")
        self.pin.setAccessibleName("Keep handwriting window on top")
        self.pin.toggled.connect(self._pin)
        self.dock_button = button("Dock back")
        self.dock_button.setObjectName("quiet")
        self.dock_button.clicked.connect(self.dock_requested)
        self.hide_button = button("Hide")
        self.hide_button.setObjectName("quiet")
        self.hide_button.clicked.connect(self.hide)
        toolbar.addWidget(self.pin)
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
        self.pin_control = WindowPin(self)
        self.pin_control.changed.connect(self._pin_state)
        self.pin_control.message.connect(self._pin_message)
        self.pin_control.request(True)

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

    def _pin(self, enabled):
        self.pin_control.request(enabled, activate=True)

    def _pin_state(self, enabled):
        with QSignalBlocker(self.pin):
            self.pin.setChecked(enabled)

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
