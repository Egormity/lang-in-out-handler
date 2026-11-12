"""Small shared presentation components."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def title_block(title: str, description: str) -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 5)
    heading = QLabel(title)
    heading.setObjectName("title")
    sub = QLabel(description)
    sub.setObjectName("subtitle")
    sub.setWordWrap(True)
    layout.addWidget(heading)
    layout.addWidget(sub)
    return widget


def label(text: str, muted: bool = False) -> QLabel:
    item = QLabel(text)
    item.setObjectName("muted" if muted else "section")
    item.setWordWrap(True)
    return item


def button(text: str, primary: bool = False) -> QPushButton:
    item = QPushButton(text)
    if primary:
        item.setObjectName("primary")
    item.setCursor(Qt.CursorShape.PointingHandCursor)
    return item


def editable_combo(items: list[str], value: str) -> QComboBox:
    widget = QComboBox()
    widget.setEditable(True)
    widget.addItems(list(dict.fromkeys([*items, value])))
    widget.setCurrentText(value)
    return widget


def language_combo(value: str) -> QComboBox:
    widget = QComboBox()
    widget.setEditable(True)
    for display, code in [
        ("Auto detect", ""),
        ("Japanese", "ja"),
        ("English", "en"),
        ("Russian", "ru"),
        ("Spanish", "es"),
        ("French", "fr"),
        ("German", "de"),
        ("Chinese", "zh"),
        ("Korean", "ko"),
    ]:
        widget.addItem(display, code)
    index = widget.findData(value)
    if index >= 0:
        widget.setCurrentIndex(index)
    else:
        widget.setCurrentText(value)
    widget.setToolTip("Choose a language or enter an ISO language code, such as ja or en.")
    return widget


def language_value(widget: QComboBox) -> str:
    index = widget.findText(widget.currentText())
    return widget.itemData(index) if index >= 0 else widget.currentText().strip()


class TextPane(QWidget):
    def __init__(self, title: str, placeholder: str, read_only: bool = True):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        row.addWidget(label(title))
        row.addStretch()
        copy = button("Copy")
        copy.setMaximumWidth(85)
        row.addWidget(copy)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(read_only)
        self.text.setAccessibleName(title)
        self.text.setTabChangesFocus(True)
        self.text.setPlaceholderText(placeholder)
        self.text.document().setMaximumBlockCount(2000)
        copy.clicked.connect(lambda: QApplication.clipboard().setText(self.text.toPlainText()))
        layout.addLayout(row)
        layout.addWidget(self.text)

    def append(self, text: str):
        if text.strip():
            self.text.appendPlainText(text.strip())
            scrollbar = self.text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
