"""Local transcript and translation history."""

from PySide6.QtCore import QDateTime, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMessageBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .common import TextPane, button, label, title_block

MODE_NAMES = {
    "input": "Voice input", "output": "Live captions", "translate": "Translation",
    "tts": "Read aloud", "drawing": "Handwriting",
}


class HistoryPage(QWidget):
    refresh_requested = Signal()
    delete_requested = Signal()
    speech_requested = Signal(str)
    audio_requested = Signal(str, object)

    def __init__(self):
        super().__init__()
        self.entries = []
        self.visible_entries = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(14)
        heading = QHBoxLayout()
        heading.addWidget(
            title_block(
                "History", "Revisit your transcripts and translations, stored on this computer."
            ), 1
        )
        self.refresh_button = button("Refresh")
        self.delete_button = button("Delete all history")
        self.delete_button.setObjectName("danger")
        self.refresh_button.clicked.connect(self.refresh_requested)
        self.delete_button.clicked.connect(self._delete)
        heading.addWidget(self.refresh_button)
        heading.addWidget(self.delete_button)
        layout.addLayout(heading)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search saved text…")
        self.search.textChanged.connect(self._render)
        layout.addWidget(self.search)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["When", "Tool", "Text"])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.itemSelectionChanged.connect(self._selected)
        layout.addWidget(self.table, 1)
        self.details = QSplitter()
        self.detail = TextPane("Original", "Select an entry to see its full text.")
        self.translation = TextPane("Translation", "This entry has no translation.")
        for pane in (self.detail, self.translation):
            pane.speech_requested.connect(self.speech_requested)
            pane.audio_requested.connect(self.audio_requested)
            self.details.addWidget(pane)
        self.details.setSizes([450, 450])
        self.translation.hide()
        layout.addWidget(self.details, 1)
        layout.addWidget(
            label("Audio files and API credentials are not included in this history.", True)
        )

    def set_entries(self, entries):
        self.entries = entries
        self._render()

    def _render(self):
        selected = self.table.currentRow()
        selected_id = (self.visible_entries[selected].get("id")
                       if 0 <= selected < len(self.visible_entries) else None)
        query = self.search.text().strip().casefold()
        self.visible_entries = [entry for entry in self.entries if not query or query in
                                (entry.get("source_text", "") + " " +
                                 entry.get("translated_text", "")).casefold()]
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.visible_entries))
        restore_row = 0
        for row, entry in enumerate(self.visible_entries):
            timestamp = entry.get("created_at", "")
            date = QDateTime.fromString(timestamp, Qt.DateFormat.ISODate)
            when = date.toLocalTime().toString("MMM d, HH:mm") if date.isValid() else timestamp
            if entry.get("id") == selected_id:
                restore_row = row
            for column, value in enumerate(
                [
                    when,
                    MODE_NAMES.get(entry.get("mode", ""), entry.get("mode", "")),
                    entry.get("source_text", "")[:150].replace("\n", " "),
                ]
            ):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, entry.get("id"))
                self.table.setItem(row, column, item)
        self.table.blockSignals(False)
        if self.visible_entries:
            self.table.selectRow(restore_row)
            self._selected()
        else:
            self.detail.text.clear()
            self.translation.text.clear()
            self.translation.hide()

    def _selected(self):
        row = self.table.currentRow()
        if 0 <= row < len(self.visible_entries):
            entry = self.visible_entries[row]
            source = entry.get("source_text", "")
            if self.detail.text.toPlainText() != source:
                self.detail.text.setPlainText(source)
            translation = entry.get("translated_text", "")
            if self.translation.text.toPlainText() != translation:
                self.translation.text.setPlainText(translation)
            self.translation.setVisible(bool(translation))
            self.detail.set_pronunciation(entry.get("source_pronunciation", ""))
            self.translation.set_pronunciation(entry.get("translation_pronunciation", ""))

    def _delete(self):
        choice = QMessageBox.question(
            self,
            "Delete history",
            "Delete all saved text history from this computer? This cannot be undone.",
        )
        if choice == QMessageBox.StandardButton.Yes:
            self.delete_requested.emit()
