"""Small consistent line icons drawn from local SVG paths."""

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QPushButton

_PATHS = {
    "captions": '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M10 9H7v6h3M18 9h-3v6h3"/>',
    "translate": '<path d="M2 5h12M8 2v3M4 5c0 5 4 8 8 10M12 5c0 5-4 8-8 10M13 21l4-10 4 10M14.5 17h5"/>',
    "draw": '<path d="m3 16 13-13 5 5-13 13H3zM13 6l5 5M3 16l5 5"/>',
    "history": '<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 3"/>',
    "copy": '<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h3"/>',
    "check": '<path d="m4 12 5 5L20 6"/>',
    "speak": '<path d="m11 5-5 4H3v6h3l5 4V5Z"/><path d="M15 8a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14"/>',
    "settings": '<path d="m9.2 3-.6 2.1-1.9 1.1-2.1-.6-2 3.5 1.5 1.5v2.2l-1.5 1.5 2 3.5 2.1-.6 1.9 1.1.6 2.1h4l.6-2.1 1.9-1.1 2.1.6 2-3.5-1.5-1.5v-2.2l1.5-1.5-2-3.5-2.1.6-1.9-1.1-.6-2.1z"/><circle cx="11.2" cy="11.7" r="3"/>',
    "float": '<path d="M14 3h7v7M21 3l-9 9M10 5H4a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-6"/>',
    "dock": '<path d="M3 10V3h7M3 3l9 9M14 5h6a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1v-6"/>',
    "undo": '<path d="m8 4-5 5 5 5M3 9h11a6 6 0 0 1 0 12H9"/>',
    "redo": '<path d="m16 4 5 5-5 5M21 9H10a6 6 0 0 0 0 12h5"/>',
    "clear": '<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7"/>',
    "close": '<path d="m6 6 12 12M18 6 6 18"/>',
    "stop": '<rect x="5" y="5" width="14" height="14" rx="2"/>',
    "play": '<path d="m7 4 14 8-14 8z"/>',
    "pause": '<path d="M8 5v14M16 5v14"/>',
    "replay": '<path d="M3 11a9 9 0 1 1 2 7M3 4v7h7"/>',
    "save": '<path d="M12 3v12m-5-5 5 5 5-5M4 15v6h16v-6"/>',
    "mic": '<rect x="9" y="2" width="6" height="13" rx="3"/><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3M8 22h8"/>',
    "file": '<path d="M14 2H5v20h14V7zM14 2v5h5"/>',
    "attach": '<path d="m21.4 11.1-9.2 9.2a6 6 0 0 1-8.5-8.5l9.2-9.2a4 4 0 0 1 5.7 5.7l-9.2 9.2a2 2 0 0 1-2.8-2.8l8.5-8.5"/>',
}


def icon(name: str, color="#dce3df") -> QIcon:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" '
        f'fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" '
        f'stroke-linejoin="round">{_PATHS[name]}</svg>'
    )
    pixmap = QPixmap(48, 48)
    pixmap.fill(Qt.GlobalColor.transparent)
    renderer = QSvgRenderer(QByteArray(svg.encode()))
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)


def icon_button(name: str, title: str) -> QPushButton:
    button = QPushButton()
    button.setObjectName("iconButton")
    button.setIcon(icon(name))
    button.setIconSize(QSize(20, 20))
    button.setFixedSize(36, 36)
    button.setAccessibleName(title)
    button.setToolTip(title)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button
