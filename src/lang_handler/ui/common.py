"""Small shared presentation components."""

from PySide6.QtCore import Qt, Signal
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

from .dropdown import CompactComboBox


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


def selection_combo(items: list[str], value: str) -> QComboBox:
    widget = CompactComboBox()
    widget.setEditable(False)
    widget.addItems(list(dict.fromkeys(item for item in [*items, value] if item)))
    widget.setCurrentText(value)
    return widget


def language_combo(value: str) -> QComboBox:
    widget = CompactComboBox()
    widget.setEditable(False)
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
        ("Arabic", "ar"),
        ("Bengali", "bn"),
        ("Bulgarian", "bg"),
        ("Catalan", "ca"),
        ("Croatian", "hr"),
        ("Czech", "cs"),
        ("Danish", "da"),
        ("Dutch", "nl"),
        ("Estonian", "et"),
        ("Finnish", "fi"),
        ("Greek", "el"),
        ("Hebrew", "he"),
        ("Hindi", "hi"),
        ("Hungarian", "hu"),
        ("Indonesian", "id"),
        ("Italian", "it"),
        ("Latvian", "lv"),
        ("Lithuanian", "lt"),
        ("Malay", "ms"),
        ("Norwegian", "no"),
        ("Persian", "fa"),
        ("Polish", "pl"),
        ("Portuguese", "pt"),
        ("Romanian", "ro"),
        ("Serbian", "sr"),
        ("Slovak", "sk"),
        ("Slovenian", "sl"),
        ("Swedish", "sv"),
        ("Tamil", "ta"),
        ("Telugu", "te"),
        ("Thai", "th"),
        ("Turkish", "tr"),
        ("Ukrainian", "uk"),
        ("Urdu", "ur"),
        ("Vietnamese", "vi"),
    ]:
        widget.addItem(display, code)
    index = widget.findData(value)
    if index >= 0:
        widget.setCurrentIndex(index)
    else:
        if value.isalpha() and len(value) in (2, 3):
            widget.addItem(value, value)
            widget.setCurrentIndex(widget.count() - 1)
    widget.setToolTip("Choose the spoken language, or detect it automatically.")
    return widget


def language_value(widget: QComboBox) -> str:
    return widget.currentData() or ""


class TextPane(QWidget):
    speech_requested = Signal(str)

    def __init__(self, title: str, placeholder: str, read_only: bool = True):
        super().__init__()
        self.setObjectName("textPane")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 10)
        layout.setSpacing(6)
        row = QHBoxLayout()
        row.addWidget(label(title))
        row.addStretch()
        self.speak = button("Speak")
        self.speak.setObjectName("quiet")
        self.speak.setAccessibleName(f"Speak {title.lower()}")
        self.speak.setToolTip("Read this text aloud using your speech preferences.")
        self.speak.setEnabled(False)
        row.addWidget(self.speak)
        copy = button("Copy")
        copy.setObjectName("quiet")
        copy.setMaximumWidth(85)
        row.addWidget(copy)
        self.text = QPlainTextEdit()
        self.text.setMinimumWidth(0)
        self.text.setReadOnly(read_only)
        self.text.setAccessibleName(title)
        self.text.setTabChangesFocus(True)
        self.text.setPlaceholderText(placeholder)
        self.text.document().setMaximumBlockCount(2000)
        copy.clicked.connect(lambda: QApplication.clipboard().setText(self.text.toPlainText()))
        self.speak.clicked.connect(lambda: self.speech_requested.emit(self.text.toPlainText()))
        self.text.textChanged.connect(
            lambda: self.speak.setEnabled(bool(self.text.toPlainText().strip()))
        )
        layout.addLayout(row)
        layout.addWidget(self.text)
        from .pronunciation import PronunciationGuide

        self.pronunciation = PronunciationGuide()
        layout.addWidget(self.pronunciation)
        self.text.textChanged.connect(lambda: self.pronunciation.set_text(""))
        self.actions = QHBoxLayout()
        self.actions.addStretch()
        layout.addLayout(self.actions)

    def set_pronunciation(self, text: str):
        self.pronunciation.set_text(text)

    def add_action(self, text: str) -> QPushButton:
        action = button(text)
        self.actions.addWidget(action)
        return action

    def append(self, text: str):
        if text.strip():
            self.text.appendPlainText(text.strip())
            scrollbar = self.text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
