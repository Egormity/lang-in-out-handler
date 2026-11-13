"""An optional source correction that is applied only on explicit selection."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .common import button, label
from .icons import icon_button


class TranslationSuggestion(QWidget):
    applied = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._correction = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addWidget(label("Did you mean?", muted=True), 1)
        self.text = QLabel()
        self.text.setTextFormat(Qt.TextFormat.PlainText)
        self.text.setWordWrap(True)
        self.text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.use_button = button("Use")
        self.use_button.setAccessibleName("Use correction suggestion")
        self.use_button.clicked.connect(self._apply)
        actions.addWidget(self.use_button)
        self.dismiss_button = icon_button("close", "Dismiss correction suggestion")
        self.dismiss_button.clicked.connect(self.clear)
        actions.addWidget(self.dismiss_button)
        layout.addLayout(actions)
        layout.addWidget(self.text)
        self.hide()

    def set_suggestion(self, correction: str, original: str = ""):
        self._correction = correction.strip()
        if not self._correction or self._correction == original.strip():
            self.clear()
            return
        self.text.setText(self._correction)
        self.show()

    def clear(self):
        self._correction = ""
        self.text.clear()
        self.hide()

    def _apply(self):
        correction = self._correction
        self.clear()
        if correction:
            self.applied.emit(correction)
