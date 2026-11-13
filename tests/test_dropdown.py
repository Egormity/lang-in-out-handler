"""Dropdowns stay compact while retaining normal selection and keyboard behavior."""

from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy

from lang_handler.settings import Settings
from lang_handler.ui.dropdown import CompactComboBox
from lang_handler.ui.main_window import MainWindow
from lang_handler.ui.theme import STYLE


def make_combo(qtbot, width=1200):
    combo = CompactComboBox()
    combo.setStyleSheet(STYLE)
    combo.addItems([f"Language {index:02d}" for index in range(44)])
    combo.resize(width, 42)
    qtbot.addWidget(combo)
    combo.show()
    return combo


def test_menu_has_at_most_eight_rows_and_does_not_inherit_field_width(qtbot):
    combo = make_combo(qtbot)
    combo.showPopup()
    qtbot.wait(20)
    popup = combo.view().window()
    assert popup.width() <= 360
    assert popup.height() <= 8 * max(32, combo.fontMetrics().height() + 12) + 2
    assert combo.view().verticalScrollBar().maximum() > 0
    assert combo.view().horizontalScrollBar().maximum() == 0
    combo.hidePopup()


def test_keyboard_can_select_an_item_outside_initial_view(qtbot):
    combo = make_combo(qtbot, 240)
    selected = QSignalSpy(combo.activated)
    combo.showPopup()
    qtbot.keyClick(combo.view(), Qt.Key.Key_End)
    qtbot.keyClick(combo.view(), Qt.Key.Key_Return)
    assert combo.currentIndex() == 43
    assert selected.count() == 1
    assert not combo.view().isVisible()


def test_escape_keeps_selection_and_reopening_scrolls_to_it(qtbot):
    combo = make_combo(qtbot, 240)
    combo.setCurrentIndex(30)
    combo.showPopup()
    qtbot.keyClick(combo.view(), Qt.Key.Key_Home)
    qtbot.keyClick(combo.view(), Qt.Key.Key_Escape)
    assert combo.currentIndex() == 30
    combo.showPopup()
    qtbot.wait(20)
    rect = combo.view().visualRect(combo.model().index(30, 0))
    assert combo.view().viewport().rect().intersects(rect)
    combo.hidePopup()


def test_pointer_selection_keeps_item_data_and_no_arbitrary_text(qtbot):
    combo = CompactComboBox()
    qtbot.addWidget(combo)
    combo.addItem("Japanese", "ja")
    combo.addItem("English", "en")
    combo.show()
    combo.showPopup()
    rect = combo.view().visualRect(combo.model().index(1, 0))
    qtbot.mouseClick(combo.view().viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
    assert combo.currentData() == "en"
    assert not combo.isEditable()
    combo.setCurrentText("arbitrary words")
    assert combo.currentData() == "en"


def test_long_labels_are_elided_with_full_tooltip(qtbot):
    combo = make_combo(qtbot, 1000)
    value = "Very long output audio device " * 20
    combo.addItem(value)
    combo.showPopup()
    assert combo.view().window().width() <= 360
    assert combo.itemData(44, Qt.ItemDataRole.ToolTipRole) == value
    combo.hidePopup()


def test_embedded_settings_reopen_saved_values_and_keep_actions_visible(qtbot):
    window = MainWindow(Settings(), True)
    qtbot.addWidget(window)
    window.resize(850, 620)
    window.show()
    window.show_tool_settings("output")
    panel = window.pages["output"].tool_settings
    view = window.pages["output"].settings_view
    panel.instructions["output_instructions"].setPlainText("A pending vocabulary hint")
    view.back_button.click()
    window.show_tool_settings("output")
    assert panel.instructions["output_instructions"].toPlainText() == ""
    assert not view.isWindow()
    assert window.stack.currentWidget() is view
    assert panel.actions.parentWidget() is view
    assert view.scroll.horizontalScrollBar().maximum() == 0
    panel.instructions["output_instructions"].setPlainText("Saved vocabulary hint")
    patch = QSignalSpy(panel.saved)
    panel.save_button.click()
    assert patch.at(0)[0]["output_instructions"] == "Saved vocabulary hint"
