"""Selection-only dropdowns with bounded menus on every Qt desktop style."""

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QListView,
    QProxyStyle,
    QStyle,
    QStyledItemDelegate,
)


class _ComboStyle(QProxyStyle):
    def styleHint(self, hint, option=None, widget=None, returnData=None):
        if hint == QStyle.StyleHint.SH_ComboBox_Popup:
            # Native menu-style popups can ignore QComboBox.maxVisibleItems.
            return 0
        return super().styleHint(hint, option, widget, returnData)


class _MenuRow(QStyledItemDelegate):
    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        size.setHeight(max(32, option.fontMetrics.height() + 12))
        return size


class CompactComboBox(QComboBox):
    """Use a normal scrollable list, never a full-height or full-width menu."""

    MAX_ROWS = 8
    MAX_POPUP_WIDTH = 360

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(False)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setMaxVisibleItems(self.MAX_ROWS)
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(12)
        self._menu_style = _ComboStyle("Fusion")
        self._menu_style.setParent(self)
        self.setStyle(self._menu_style)
        view = QListView(self)
        view.setUniformItemSizes(True)
        view.setTextElideMode(Qt.TextElideMode.ElideRight)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerItem)
        view.setItemDelegate(_MenuRow(view))
        self.setView(view)

    def showPopup(self):
        if not self.count():
            return
        view = self.view()
        for index in range(self.count()):
            if not self.itemData(index, Qt.ItemDataRole.ToolTipRole):
                self.setItemData(index, self.itemText(index), Qt.ItemDataRole.ToolTipRole)
        screen = self.screen().availableGeometry()
        width = min(self.MAX_POPUP_WIDTH, max(200, self.width()), screen.width())
        row_height = max(32, self.fontMetrics().height() + 12)
        height = min(self.count(), self.MAX_ROWS) * row_height + 2
        height = min(height, screen.height() - 16)
        popup = view.window()
        # Set both constraints before Qt opens its internal popup container, so
        # the full-width form field cannot flash as a screen-sized menu.
        popup.setFixedSize(QSize(width, height))
        super().showPopup()
        popup.setFixedSize(QSize(width, height))
        anchor = self.mapToGlobal(QPoint(0, self.height()))
        x = max(screen.left(), min(anchor.x(), screen.right() - width + 1))
        y = anchor.y()
        if y + height > screen.bottom() + 1:
            y = self.mapToGlobal(QPoint(0, 0)).y() - height
        y = max(screen.top(), min(y, screen.bottom() - height + 1))
        popup.move(x, y)
        selected = self.model().index(self.currentIndex(), self.modelColumn(), self.rootModelIndex())
        view.setCurrentIndex(selected)
        view.doItemsLayout()
        view.scrollTo(selected, QAbstractItemView.ScrollHint.PositionAtCenter)
