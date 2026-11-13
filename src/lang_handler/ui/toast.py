"""Transient notifications overlay the page without moving its content."""

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QWidget

from .icons import icon_button


class Toast(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("toast")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 8, 10)
        self.message = QLabel()
        self.message.setObjectName("toastMessage")
        self.message.setWordWrap(True)
        self.message.setTextFormat(Qt.TextFormat.PlainText)
        self.message.setAccessibleName("Notification")
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setWidget(self.message)
        layout.addWidget(self.scroll, 1)
        self.dismiss = icon_button("close", "Dismiss notification")
        self.dismiss.setFixedSize(30, 30)
        self.dismiss.clicked.connect(self.hide)
        layout.addWidget(self.dismiss, 0, Qt.AlignmentFlag.AlignTop)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)
        parent.installEventFilter(self)
        self.hide()

    def show_message(self, text, error=False):
        self.timer.stop()
        self.message.setText(text)
        self.message.setProperty("error", error)
        self.setProperty("error", error)
        self.style().unpolish(self)
        self.style().polish(self)
        self.message.style().unpolish(self.message)
        self.message.style().polish(self.message)
        if not text:
            self.hide()
            return
        self._position()
        self.show()
        self.raise_()
        self.timer.start(12000 if error else 5000)

    def _position(self):
        host = self.parentWidget()
        width = min(440, max(160, host.width() - 32))
        text_width = max(80, width - 70)
        text_height = max(30, self.message.heightForWidth(text_width))
        self.message.setMinimumHeight(text_height)
        self.setFixedSize(width, min(text_height, max(60, min(220, host.height() - 120))) + 22)
        self.move(max(16, host.width() - self.width() - 16), 76)

    def eventFilter(self, watched, event):
        if watched is self.parentWidget() and event.type() == QEvent.Type.Resize:
            self._position()
        return super().eventFilter(watched, event)
