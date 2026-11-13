"""Small shared presentation components."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .copy_button import CopyButton
from .dropdown import CompactComboBox
from .inline_audio import InlineAudio
from .text_edit import GrowingTextEdit


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
    if description:
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
    audio_requested = Signal(str, object)

    def __init__(self, title: str, placeholder: str, read_only: bool = True):
        super().__init__()
        self.setObjectName("textPane")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        self.heading = label(title, True)
        layout.addWidget(self.heading)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        body.setObjectName("textBody")
        content = QVBoxLayout(body)
        self.content_layout = content
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(0)
        self.text = GrowingTextEdit(minimum=58)
        self.text.setObjectName("contentText")
        self.text.setReadOnly(read_only)
        self.text.setAccessibleName(title)
        self.text.setTabChangesFocus(True)
        self.text.setPlaceholderText(placeholder)
        content.addWidget(self.text)
        from .pronunciation import PronunciationGuide

        self.pronunciation = PronunciationGuide()
        content.addWidget(self.pronunciation)
        content.addStretch(1)
        body.mousePressEvent = lambda event: self.text.setFocus()
        self.scroll.setWidget(body)
        layout.addWidget(self.scroll, 1)
        self.actions = QHBoxLayout()
        self.actions.setSpacing(4)
        self.actions.addStretch()
        self.copy = CopyButton(f"Copy {title.lower()}", self.text.toPlainText)
        self.audio = InlineAudio()
        self.speak = self.audio.speak
        self.speak.setAccessibleName(f"Speak {title.lower()}")
        self.speak.setToolTip("Read selected text, or the whole pane.")
        self.copy.setEnabled(False)
        self.speak.setEnabled(False)
        self.audio.requested.connect(self._request_audio)
        self.text.textChanged.connect(self._changed)
        self.actions.addWidget(self.copy)
        self.actions.addWidget(self.audio)
        layout.addLayout(self.actions)
        self._audio_text = ""

    def _request_audio(self):
        text = (self.text.textCursor().selectedText().replace("\u2029", "\n")
                or self.text.toPlainText())
        self.speech_requested.emit(text)
        self.audio_requested.emit(text, self.audio)

    def _changed(self):
        text = self.text.toPlainText()
        if text != self._audio_text:
            self.audio.reset()
            self._audio_text = text
        has_text = bool(text.strip())
        self.copy.setEnabled(has_text)
        self.copy.reset_feedback()
        self.speak.setEnabled(has_text)
        self.pronunciation.set_text("")

    def set_pronunciation(self, text: str):
        self.pronunciation.set_text(text)

    def add_action(self, text: str) -> QPushButton:
        action = button(text)
        self.actions.addWidget(action)
        return action

    def append(self, text: str):
        if text.strip():
            self.text.appendPlainText(text.strip())
            self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum())
