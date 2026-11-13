"""One flowing text document backed by individually revisable audio fragments."""

from collections import OrderedDict

from PySide6.QtGui import QTextCursor

from .common import TextPane


def flowing_text(parts):
    result = ""
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if result and not result[-1].isspace() and not part[0].isspace():
            left_cjk = "\u3000" <= result[-1] <= "\u9fff" or "\uac00" <= result[-1] <= "\ud7af"
            right_cjk = "\u3000" <= part[0] <= "\u9fff" or "\uac00" <= part[0] <= "\ud7af"
            if not (left_cjk and right_cjk) and part[0] not in ".,!?;:)]}、。！？":
                result += " "
        result += part
    return result


class ContinuousPane(TextPane):
    def __init__(self, title, placeholder, *, compact=False):
        super().__init__(title, placeholder)
        self._fragments = OrderedDict()
        self._anonymous = 0
        self._following = True
        self.scroll.verticalScrollBar().rangeChanged.connect(self._range_changed)
        self.scroll.verticalScrollBar().valueChanged.connect(self._position_changed)
        if compact:
            self.layout().setContentsMargins(4, 2, 4, 2)
            self.text.minimum = 48

    def append(self, text, pronunciation="", *, segment_id=None):
        if not text.strip():
            return
        if segment_id is None:
            self._anonymous += 1
            segment_id = ("local", self._anonymous)
        self._fragments[segment_id] = (text.strip(), pronunciation.strip())
        self._render()

    def contains(self, segment_id):
        return segment_id in self._fragments

    def revise(self, segment_id, text=None, pronunciation=""):
        if not self.contains(segment_id):
            return False
        if text is None:
            text = self._fragments[segment_id][0]
        self._fragments[segment_id] = (text.strip(), pronunciation.strip())
        self._render()
        return True

    def upsert(self, segment_id, text, pronunciation=""):
        self._fragments[segment_id] = (text.strip(), pronunciation.strip())
        if all(isinstance(key, int) for key in self._fragments):
            self._fragments = OrderedDict(sorted(self._fragments.items()))
        self._render()

    def set_pronunciation_for(self, segment_id, pronunciation):
        if not self.contains(segment_id):
            return False
        text, _ = self._fragments[segment_id]
        return self.revise(segment_id, text, pronunciation)

    def _render(self):
        text = flowing_text(part[0] for part in self._fragments.values())
        pronunciation = flowing_text(part[1] for part in self._fragments.values())
        cursor = self.text.textCursor()
        anchor, position = cursor.anchor(), cursor.position()
        scrollbar = self.scroll.verticalScrollBar()
        scroll_position, following = scrollbar.value(), self._following
        if text != self.text.toPlainText():
            self.text.setPlainText(text)
            cursor = self.text.textCursor()
            limit = self.text.document().characterCount() - 1
            cursor.setPosition(min(anchor, limit))
            cursor.setPosition(min(position, limit), QTextCursor.MoveMode.KeepAnchor)
            self.text.setTextCursor(cursor)
        self.set_pronunciation(pronunciation)
        self._following = following
        if following:
            scrollbar.setValue(scrollbar.maximum())
        else:
            scrollbar.setValue(scroll_position)

    def _range_changed(self, minimum, maximum):
        if self._following:
            self.scroll.verticalScrollBar().setValue(maximum)

    def _position_changed(self, position):
        self._following = position >= self.scroll.verticalScrollBar().maximum() - 4

    def clear(self):
        self._fragments.clear()
        self.text.clear()
        self.set_pronunciation("")
        self._following = True

    def toPlainText(self):
        return self.text.toPlainText()

    def set_text_size(self, pixels):
        self.text.setStyleSheet(f"font-size: {pixels}px;")
        self.text.fit_content()
