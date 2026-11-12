"""Local transcript and translation history."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .common import TextPane, button, label, title_block


class HistoryPage(QWidget):
    refresh_requested = Signal()
    delete_requested = Signal()

    def __init__(self):
        super().__init__()
        self.entries = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(14)
        layout.addWidget(
            title_block(
                "History", "Revisit your transcripts and translations, stored on this computer."
            )
        )
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["When", "Mode", "Preview"])
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
        self.detail = TextPane("Selected entry", "Select an entry to see its full text.")
        layout.addWidget(self.detail, 1)
        row = QHBoxLayout()
        row.addWidget(
            label("Audio files and API credentials are not included in this history.", True), 1
        )
        refresh = button("Refresh")
        clear = button("Delete all history")
        clear.setObjectName("danger")
        refresh.clicked.connect(self.refresh_requested)
        clear.clicked.connect(self._delete)
        row.addWidget(refresh)
        row.addWidget(clear)
        layout.addLayout(row)

    def set_entries(self, entries):
        self.entries = entries
        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            for column, value in enumerate(
                [
                    entry.get("created_at", ""),
                    entry.get("mode", ""),
                    entry.get("source_text", "")[:150].replace("\n", " "),
                ]
            ):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, entry.get("id"))
                self.table.setItem(row, column, item)
        self.detail.text.clear()

    def _selected(self):
        row = self.table.currentRow()
        if 0 <= row < len(self.entries):
            entry = self.entries[row]
            text = entry.get("source_text", "")
            if entry.get("translated_text"):
                text += "\n\n── Translation ──\n\n" + entry["translated_text"]
            self.detail.text.setPlainText(text)

    def _delete(self):
        choice = QMessageBox.question(
            self,
            "Delete history",
            "Delete all saved text history from this computer? This cannot be undone.",
        )
        if choice == QMessageBox.StandardButton.Yes:
            self.delete_requested.emit()
