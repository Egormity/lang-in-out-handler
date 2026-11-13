"""Readable desktop typography and a restrained charcoal / mint palette."""

from pathlib import Path

STYLE = """
QWidget { color: #e7ecef; background: #181d23; font-family: 'Noto Sans'; font-size: 14px; }
QLabel { background: transparent; }
QWidget#sidebar { background: #10151a; border-right: 1px solid #2c343e; }
QLabel#brand { font-size: 21px; font-weight: 700; color: #f4f8fa; }
QLabel#eyebrow { font-size: 10px; font-weight: 600; color: #83959e; }
QLabel#title { font-size: 27px; font-weight: 700; }
QLabel#subtitle { color: #9fadb8; font-size: 13px; }
QLabel#section { color: #ced8de; font-weight: 600; }
QLabel#status { padding: 9px 16px; background: #12171d; border-top: 1px solid #2d3540; color: #a5b3bf; font-size: 12px; }
QLabel#status[error="true"] { color: #ffb5ad; }
QLabel#badge { color: #8bd9c3; background: #1b322d; border-radius: 6px; padding: 7px 9px; font-size: 11px; }
QLabel#muted { color: #98a8b5; font-size: 12px; }
QPushButton { background: #2b3541; border: 1px solid #414d5c; border-radius: 7px; padding: 8px 12px; }
QPushButton:hover { background: #364252; border-color: #647686; }
QPushButton:pressed { background: #425364; }
QPushButton:disabled { color: #74808e; border-color: #303a45; background: #222b34; }
QPushButton#primary { background: #83dbbd; color: #10382b; font-weight: 600; border-color: #83dbbd; }
QPushButton#primary:hover { background: #a1e9d0; }
QPushButton#primary:disabled { background: #2b5549; border-color: #2b5549; color: #88a89c; }
QPushButton#numberStep { padding: 3px; font-size: 20px; font-weight: 600; }
QPushButton#preferenceReset { padding: 7px 6px; font-size: 12px; background: transparent; color: #a5b8c5; }
QPushButton#preferenceReset:hover { background: #2b3943; color: #e1f5f0; }
QPushButton#danger { color: #f4b0a7; }
QPushButton#quiet { border: none; background: transparent; color: #a5b8c5; padding: 6px 8px; }
QPushButton#quiet:hover { background: #2b3943; color: #e1f5f0; }
QPushButton#nav { text-align: left; border: none; background: transparent; padding: 11px 12px; color: #a9b7c1; }
QPushButton#nav:checked { color: #b0efdb; background: #223c33; font-weight: 600; }
QPushButton#nav:hover { background: #25323b; }
QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QKeySequenceEdit {
 background: #11171d; border: 1px solid #3c4756; border-radius: 6px; padding: 8px; selection-background-color: #356854;
}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus { border-color: #83cdb4; }
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled { color: #71808d; background: #20272e; }
QPlainTextEdit { padding: 10px; }
QSpinBox#preferenceNumber::up-button, QSpinBox#preferenceNumber::down-button,
QDoubleSpinBox#preferenceNumber::up-button, QDoubleSpinBox#preferenceNumber::down-button { width: 0; height: 0; border: none; }
QSpinBox#preferenceNumber QLineEdit, QDoubleSpinBox#preferenceNumber QLineEdit { border: none; padding: 0; background: transparent; }
QComboBox { min-height: 20px; padding-right: 25px; }
QComboBox::drop-down { border: none; width: 25px; }
QComboBox QAbstractItemView { background: #22303a; selection-background-color: #315f4d; }
QCheckBox { spacing: 8px; padding: 4px 0; }
QCheckBox::indicator { width: 17px; height: 17px; border-radius: 4px; border: 1px solid #7a8b99; background: #11171d; }
QCheckBox::indicator:checked { background: #83dbbd; border: 1px solid #83dbbd; }
QGroupBox { border: 1px solid #36424e; border-radius: 8px; margin-top: 16px; padding: 16px; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: #c7d8e2; font-weight: 600; }
QToolButton#sectionToggle { color: #a6b9c6; border: none; padding: 5px 0; text-align: left; background: transparent; }
QToolButton#sectionToggle:hover { color: #bcebdc; }
QFrame#optionsBody { background: #202932; border: 1px solid #36424e; border-radius: 7px; }
QFrame#optionsBody QLabel { background: transparent; }
QWidget#textPane { background: #11171d; border: 1px solid #3b4653; border-radius: 9px; }
QWidget#textPane QPlainTextEdit { border: none; border-radius: 0; font-size: 16px; padding: 8px 2px; }
QWidget#textPane QLabel { background: transparent; }
QScrollArea { border: none; }
QScrollBar:vertical { background: #181d23; width: 9px; margin: 0; }
QScrollBar::handle:vertical { background: #455665; min-height: 28px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QSplitter::handle { background: #181d23; width: 12px; }
QProgressBar#audioLevel { border: 1px solid #36424e; border-radius: 5px; background: #11171d; text-align: center; font-size: 10px; }
QProgressBar#audioLevel::chunk { background: #326451; border-radius: 4px; }
QTableWidget { background: #11171d; border: 1px solid #3b4653; gridline-color: #2e3a45; }
QTableWidget::item { padding: 6px; }
QTableWidget::item:selected { background: #2a5143; }
QHeaderView::section { background: #27323e; color: #c0d0da; padding: 9px; border: none; }
QTabWidget::pane { border: none; border-top: 1px solid #394653; }
QTabBar::tab { background: transparent; color: #9dacb9; padding: 11px 10px; border-bottom: 2px solid transparent; font-size: 12px; }
QTabBar::tab:selected { color: #b0efdb; border-bottom: 2px solid #83dbbd; }
QTabBar::tab:hover { background: #24313a; }
QToolTip { background: #2c3e49; color: #e6ecec; border: 1px solid #6a8c9c; padding: 5px; }
"""

_ASSETS = Path(__file__).parent
STYLE += f'QComboBox::down-arrow {{ image: url("{(_ASSETS / "chevron.svg").as_posix()}"); width: 12px; height: 8px; }}'
STYLE += (
    f'QCheckBox::indicator:checked {{ image: url("{(_ASSETS / "checkmark.svg").as_posix()}"); }}'
)
