"""Compact, collapsible settings and scrollable tab bodies."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QLayout,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class ExpandableSection(QWidget):
    def __init__(self, title: str):
        super().__init__()
        self.toggle = QToolButton()
        self.toggle.setText(title)
        self.toggle.setObjectName("sectionToggle")
        self.toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.toggle.setCheckable(True)
        self.toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.body = QFrame()
        self.body.setObjectName("optionsBody")
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(14, 12, 14, 12)
        self.body_layout.setSpacing(10)
        self.body.hide()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        layout.addWidget(self.toggle)
        layout.addWidget(self.body)
        self.toggle.toggled.connect(self._toggle)

    def _toggle(self, checked):
        self.toggle.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
        self.body.setVisible(checked)


def scrollable_body():
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    body = QWidget()
    layout = QVBoxLayout(body)
    layout.setContentsMargins(4, 18, 14, 10)
    layout.setSpacing(18)
    scroll.setWidget(body)
    return scroll, layout


def tool_layout(page):
    """Fill the page when possible; scroll rather than overlap when options expand."""
    outer = QVBoxLayout(page)
    outer.setContentsMargins(0, 0, 0, 0)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    body = QWidget()
    layout = QVBoxLayout(body)
    layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
    layout.setContentsMargins(24, 24, 24, 20)
    layout.setSpacing(14)
    scroll.setWidget(body)
    outer.addWidget(scroll)
    page.scroll = scroll
    return layout
