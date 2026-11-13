"""An independent, pinnable host for the shared handwriting editor."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout

from ..window_pin import WindowPin
from .icons import icon_button
from .theme import STYLE
from .translucent_window import TRANSLUCENT_CONTENT_STYLE, TranslucentWindow


class DrawingWindow(TranslucentWindow):
    dock_requested = Signal()

    def __init__(self, on_top=True, opacity=1.0):
        super().__init__()
        self.setWindowTitle("Lang In/Out · Handwriting")
        self.setWindowFlags(Qt.WindowType.Tool)
        self.setStyleSheet(STYLE + TRANSLUCENT_CONTENT_STYLE)
        self.resize(650, 420)
        self.setMinimumSize(440, 260)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        self.workspace = None
        self.scroll = None
        self.set_background_opacity(opacity)
        self.dock_button = icon_button("dock", "Dock canvas")
        self.dock_button.setObjectName("quiet")
        self.dock_button.clicked.connect(self.dock_requested)
        self.dock_button.hide()
        self.hide_button = icon_button("close", "Hide canvas")
        self.hide_button.setObjectName("quiet")
        self.hide_button.clicked.connect(self.hide)
        self.hide_button.hide()
        self.pin_status = QLabel()
        self.pin_status.setObjectName("muted")
        self.pin_status.setWordWrap(True)
        self.pin_status.hide()
        layout.addWidget(self.pin_status)
        self.pin_control = WindowPin(self, on_top)
        self.pin_control.message.connect(self._pin_message)
        self.pin_control.request(on_top)

    def set_background_opacity(self, opacity):
        super().set_background_opacity(opacity)
        if self.workspace is not None:
            self.workspace.canvas.set_background_opacity(self.background_opacity)

    def set_workspace(self, workspace):
        self.workspace = workspace
        self.scroll = workspace.scroll
        self.layout().insertWidget(0, workspace, 1)
        workspace.set_floating(True, (self.dock_button, self.hide_button))
        workspace.canvas.set_background_opacity(self.background_opacity)
        workspace.show()

    def take_workspace(self):
        workspace = self.workspace
        if workspace is not None:
            self.layout().removeWidget(workspace)
            workspace.set_floating(False)
            workspace.canvas.set_background_opacity(1.0)
            for control in (self.dock_button, self.hide_button):
                control.setParent(self)
                control.hide()
            workspace.setParent(None)
        self.workspace = None
        self.scroll = None
        return workspace

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
