"""Quiet charcoal surfaces, readable text, and a single mint action accent."""

from pathlib import Path

STYLE = """
QWidget { color: #e6e9e7; background: #1d2021; font-family: 'Noto Sans'; font-size: 14px; }
QLabel { background: transparent; }
QWidget#sidebar { background: #171a1b; border-right: 1px solid #343938; }
QLabel#brand { font-size: 20px; font-weight: 600; color: #f1f4f2; }
QLabel#eyebrow { font-size: 10px; color: #8d9992; }
QLabel#title { font-size: 24px; font-weight: 600; }
QLabel#subtitle { color: #a1aaa5; font-size: 13px; }
QLabel#section { color: #d7dfda; font-weight: 500; }
QLabel#status { padding: 6px 12px; color: #a4afa8; font-size: 12px; }
QLabel#status[error="true"] { color: #ffb7af; }
QLabel#badge { color: #a4b5ab; font-size: 11px; padding: 5px 0; }
QLabel#muted { color: #99a59e; font-size: 13px; }
QPushButton { background: transparent; border: 1px solid #414a45; border-radius: 7px; padding: 8px 14px; }
QPushButton:hover { background: #29322d; border-color: #6c8174; }
QPushButton:pressed { background: #34473c; }
QPushButton:disabled { color: #68766c; border-color: #303933; }
QPushButton#primary { background: #9ae0c0; color: #142a20; font-weight: 600; border: none; padding: 11px 22px; }
QPushButton#primary:hover { background: #b0ebce; }
QPushButton#primary:disabled { background: #2b4b3c; color: #829b8c; }
QPushButton#numberStep { padding: 3px; font-size: 20px; }
QPushButton#preferenceReset { padding: 3px; font-size: 18px; border: none; color: #92a69a; }
QPushButton#preferenceReset:hover { background: #2b3930; color: #e1f5e8; }
QPushButton#danger { color: #edada5; }
QPushButton#quiet, QPushButton#iconButton { border: none; background: transparent; color: #b3c0b8; padding: 6px 8px; }
QPushButton#quiet:hover, QPushButton#iconButton:hover { background: #2c3730; color: #e4f5e9; }
QPushButton#quiet:disabled, QPushButton#iconButton:disabled { background: transparent; color: #5d6c62; }
QPushButton#nav { text-align: left; border: none; border-left: 3px solid transparent; border-radius: 0; background: transparent; padding: 12px 14px; color: #aebbb2; }
QPushButton#nav:checked { color: #d9f2e4; background: #263d30; border-left-color: #9ae0c0; font-weight: 500; }
QPushButton#nav:hover { background: #253129; }
QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QKeySequenceEdit {
 background: #202725; border: 1px solid #3e4a43; border-radius: 6px; padding: 8px; selection-background-color: #426e54;
}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus { border-color: #91cdaa; }
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled { color: #718077; }
QPlainTextEdit { padding: 8px; }
QSpinBox#preferenceNumber::up-button, QSpinBox#preferenceNumber::down-button,
QDoubleSpinBox#preferenceNumber::up-button, QDoubleSpinBox#preferenceNumber::down-button { width: 0; height: 0; border: none; }
QSpinBox#preferenceNumber QLineEdit, QDoubleSpinBox#preferenceNumber QLineEdit { border: none; padding: 0; background: transparent; }
QComboBox { min-height: 20px; padding-right: 28px; }
QComboBox::drop-down { border: none; width: 28px; }
QComboBox QAbstractItemView { background: #252d28; selection-background-color: #355d43; border: 1px solid #4d6153; padding: 3px; }
QCheckBox { spacing: 8px; padding: 4px 0; }
QCheckBox::indicator { width: 17px; height: 17px; border-radius: 4px; border: 1px solid #7a8b7e; background: #1b211e; }
QCheckBox::indicator:checked { background: #9ae0c0; border: 1px solid #9ae0c0; }
QGroupBox { border: none; border-top: 1px solid #39463d; margin-top: 16px; padding: 16px 0; }
QGroupBox::title { subcontrol-origin: margin; left: 0; color: #d4e1d8; font-weight: 500; }
QWidget#settingsSection { background: transparent; border: none; border-bottom: 1px solid #38443c; }
QLabel#settingsHeading { color: #d6e5db; font-size: 15px; font-weight: 600; padding: 8px 0; }
QLabel#settingsTitle { font-size: 21px; font-weight: 600; padding: 4px 0; }
QToolButton#sectionToggle { color: #a6b9ad; border: none; padding: 5px 0; background: transparent; }
QFrame#optionsBody { background: transparent; border: none; }
QWidget#textPane, QWidget#textBody { background: transparent; border: none; }
QPlainTextEdit#contentText { background: transparent; border: none; padding: 4px 0; font-size: 22px; color: #eef1ee; }
QPlainTextEdit#pronunciationText { background: transparent; border: none; padding: 0; font-size: 15px; color: #a3b0a7; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 0; }
QScrollBar::handle:vertical { background: #4c5d51; min-height: 28px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QSplitter::handle { background: #3b453e; width: 1px; }
QTableWidget { background: transparent; border: none; gridline-color: #364239; }
QTableWidget::item { padding: 8px; }
QTableWidget::item:selected { background: #294735; }
QHeaderView::section { background: #232c27; color: #bdcec3; padding: 9px; border: none; }
QTabWidget::pane { border: none; border-top: 1px solid #3a483f; }
QTabBar::tab { background: transparent; color: #a3b1a8; padding: 11px 14px; border-bottom: 2px solid transparent; font-size: 13px; }
QTabBar::tab:selected { color: #c7edda; border-bottom: 2px solid #9ae0c0; }
QTabBar::tab:hover { background: #253129; }
QToolTip { background: #303e35; color: #e7f0e9; border: 1px solid #647c6c; padding: 5px; }
"""

_ASSETS = Path(__file__).parent
STYLE += f'QComboBox::down-arrow {{ image: url("{(_ASSETS / "chevron.svg").as_posix()}"); width: 12px; height: 8px; }}'
STYLE += f'QCheckBox::indicator:checked {{ image: url("{(_ASSETS / "checkmark.svg").as_posix()}"); }}'
