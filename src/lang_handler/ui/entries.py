"""Scrollable text entries with an independent copy and speech action per result."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .common import button, label


class EntryRow(QWidget):
    speech_requested = Signal(str)

    def __init__(self, text: str, pronunciation="", *, compact=False, segment_id=None):
        super().__init__()
        self.text = text
        self.segment_id = segment_id
        self.setObjectName("entryRow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6 if compact else 10, 8, 4)
        layout.setSpacing(2)
        self.content = QLabel(text)
        self.content.setObjectName("entryText")
        self.content.setTextFormat(Qt.TextFormat.PlainText)
        self.content.setWordWrap(True)
        self.content.setMinimumWidth(0)
        self.content.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.content.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.content)
        self.guide = QLabel()
        self.guide.setObjectName("muted")
        self.guide.setTextFormat(Qt.TextFormat.PlainText)
        self.guide.setWordWrap(True)
        self.guide.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.guide.setMinimumWidth(0)
        self.guide.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.set_pronunciation(pronunciation)
        layout.addWidget(self.guide)
        actions = QHBoxLayout()
        actions.setSpacing(2)
        actions.addStretch()
        self.copy = button("Copy")
        self.speak = button("Speak")
        for control in (self.copy, self.speak):
            control.setObjectName("quiet")
            control.setFocusPolicy(Qt.FocusPolicy.TabFocus)
            actions.addWidget(control)
        self.copy.setAccessibleName("Copy this entry")
        self.speak.setAccessibleName("Speak this entry")
        self.copy.clicked.connect(lambda: QApplication.clipboard().setText(self.text))
        self.speak.clicked.connect(lambda: self.speech_requested.emit(self.text))
        layout.addLayout(actions)


    def set_pronunciation(self, text):
        self.pronunciation = text
        self.guide.setText(text)
        self.guide.setVisible(bool(text))
        self.guide.setAccessibleName("Pronunciation: " + text)


class EntryList(QWidget):
    speech_requested = Signal(str)

    def __init__(self, title: str, placeholder: str, max_entries=100, compact=False):
        super().__init__()
        self.entries: list[EntryRow] = []
        self.max_entries = max(1, max_entries)
        self.compact = compact
        self.text_size = 16
        self.setMinimumWidth(0)
        self.setObjectName("entryList")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setStyleSheet(
            "QWidget#entryList { background: #11171d; border: 1px solid #3b4653; border-radius: 8px; }"
            "QWidget#entryBody, QWidget#entryRow { background: transparent; border: none; }"
            "QWidget#entryRow { border-bottom: 1px solid #28333c; border-radius: 0; }"
            "QWidget#entryList QScrollArea { background: transparent; border: none; }"
            "QWidget#entryList QPushButton { padding: 3px 7px; font-size: 12px; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)
        heading = QHBoxLayout()
        heading.addWidget(label(title))
        heading.addStretch()
        self.copy_all = button("Copy all")
        self.copy_all.setObjectName("quiet")
        self.copy_all.setEnabled(False)
        self.copy_all.clicked.connect(lambda: QApplication.clipboard().setText(self.toPlainText()))
        heading.addWidget(self.copy_all)
        layout.addLayout(heading)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        body.setObjectName("entryBody")
        self.body_layout = QVBoxLayout(body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(3)
        self.empty = label(placeholder, True)
        self.body_layout.addWidget(self.empty)
        self.body_layout.addStretch()
        self.scroll.setWidget(body)
        layout.addWidget(self.scroll, 1)
        self._following = True
        scrollbar = self.scroll.verticalScrollBar()
        scrollbar.rangeChanged.connect(self._range_changed)
        scrollbar.valueChanged.connect(self._position_changed)

    def append(self, text: str, pronunciation="", *, segment_id=None):
        text = text.strip()
        if not text:
            return
        row = EntryRow(text, pronunciation, compact=self.compact, segment_id=segment_id)
        row.content.setStyleSheet(f"font-size: {self.text_size}px;")
        row.speech_requested.connect(self.speech_requested)
        self.entries.append(row)
        self.body_layout.insertWidget(self.body_layout.count() - 1, row)
        self.empty.hide()
        self.copy_all.setEnabled(True)
        while len(self.entries) > self.max_entries:
            removed = self.entries.pop(0)
            self.body_layout.removeWidget(removed)
            removed.hide()
            removed.deleteLater()
    def _range_changed(self, minimum, maximum):
        if self._following:
            self.scroll.verticalScrollBar().setValue(maximum)

    def _position_changed(self, position):
        self._following = position >= self.scroll.verticalScrollBar().maximum() - 4

    def clear(self):
        for row in self.entries:
            self.body_layout.removeWidget(row)
            row.hide()
            row.deleteLater()
        self.entries.clear()
        self._following = True
        self.empty.show()
        self.copy_all.setEnabled(False)

    def set_pronunciation_for(self, segment_id, pronunciation):
        for row in self.entries:
            if segment_id is not None and row.segment_id == segment_id:
                row.set_pronunciation(pronunciation)
                return True
        return False

    def toPlainText(self) -> str:
        return "\n".join(row.text for row in self.entries)

    def set_text_size(self, pixels: int):
        self.text_size = pixels
        for row in self.entries:
            row.content.setStyleSheet(f"font-size: {pixels}px;")
