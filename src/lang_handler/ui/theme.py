"""A readable, consistent desktop palette."""

from pathlib import Path

STYLE = """
QWidget { color: #e6ecec; background: #131a20; font-size: 14px; }
QLabel { background: transparent; }
QMainWindow { background: #131a20; }
QWidget#sidebar { background: #0c1217; border-right: 1px solid #26313a; }
QLabel#brand { font-size: 23px; font-weight: 700; color: #f0fbf8; }
QLabel#eyebrow { font-size: 11px; font-weight: 600; color: #5ed6b5; }
QLabel#title { font-size: 29px; font-weight: 700; }
QLabel#subtitle { color: #98a9b5; font-size: 14px; }
QLabel#section { color: #c7d8df; font-weight: 600; }
QLabel#status { padding: 10px 14px; background: #10171c; border-top: 1px solid #29343d; color: #9cafbb; }
QLabel#status[error="true"] { color: #ffaea5; }
QLabel#badge { color: #7ad9be; background: #17372f; border-radius: 8px; padding: 5px 9px; font-size: 11px; }
QLabel#muted { color: #8c9da9; }
QPushButton { background: #25313b; border: 1px solid #364551; border-radius: 7px; padding: 9px 14px; }
QPushButton:hover { background: #32424e; border-color: #536c7b; }
QPushButton:pressed { background: #425967; }
QPushButton:disabled { color: #687782; border-color: #26313a; background: #1b252d; }
QPushButton#primary { background: #52c6a7; color: #08291f; font-weight: 600; border-color: #52c6a7; }
QPushButton#primary:hover { background: #74ddbf; }
QPushButton#primary:disabled { background: #26483f; border-color: #26483f; color: #77968b; }
QPushButton#danger { color: #f4b0a7; }
QPushButton#nav { text-align: left; border: none; background: transparent; padding: 12px; color: #a3b5c1; }
QPushButton#nav:checked { color: #8fe7cd; background: #18352e; }
QPushButton#nav:hover { background: #202d35; }
QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QKeySequenceEdit {
 background: #0d1419; border: 1px solid #32414c; border-radius: 6px; padding: 8px; selection-background-color: #246a58;
}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus { border-color: #56b99e; }
QPlainTextEdit { padding: 12px; }
QComboBox { min-height: 21px; }
QComboBox::drop-down { border: none; width: 25px; }
QComboBox QAbstractItemView { background: #1c2933; selection-background-color: #275447; }
QCheckBox { spacing: 8px; padding: 4px 0; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 4px; border: 1px solid #5e7381; background: #0d1419; }
QCheckBox::indicator:checked { background: #52c6a7; border: 3px solid #235b4c; }
QGroupBox { border: 1px solid #2c3b46; border-radius: 9px; margin-top: 20px; padding: 15px; }
QGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 5px; color: #b9cbd5; }
QScrollArea { border: none; }
QScrollBar:vertical { background: #131a20; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #344955; min-height: 28px; border-radius: 5px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QSplitter::handle { background: #2a3b45; width: 3px; }
QProgressBar#audioLevel { border: 1px solid #32414c; border-radius: 5px; background: #0d1419; text-align: center; font-size: 11px; }
QProgressBar#audioLevel::chunk { background: #286f5d; border-radius: 4px; }
QTableWidget { background: #0d1419; border: 1px solid #32414c; gridline-color: #24323c; }
QTableWidget::item { padding: 6px; }
QTableWidget::item:selected { background: #234b40; }
QHeaderView::section { background: #1c2932; color: #a6bdc9; padding: 9px; border: none; }
QToolTip { background: #283a44; color: #e6ecec; border: 1px solid #6a8c9c; padding: 5px; }
"""

STYLE += f'QComboBox::down-arrow {{ image: url("{Path(__file__).with_name("chevron.svg").as_posix()}"); width: 12px; height: 8px; }}'
