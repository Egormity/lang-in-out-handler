"""Compact language controls that take the place of a document heading."""

from PySide6.QtCore import QSignalBlocker, Qt

from .common import language_combo


def source_language_selector(value):
    selector = language_combo(value)
    selector.setAccessibleName("Spoken language")
    return _compact(selector)


def target_language_selector(value, *, compact=True):
    selector = language_combo("")
    selector.removeItem(0)  # A translation always needs an explicit target language.
    selector.setAccessibleName("Translation language")
    selector.setToolTip("Choose the translation language.")
    select_language(selector, value)
    return _compact(selector) if compact else selector


def _compact(selector):
    selector.setObjectName("paneLanguage")
    selector.setFixedWidth(180)
    return selector


def select_language(selector, value, *, source=False):
    """Apply saved settings without emitting an additional settings change."""
    with QSignalBlocker(selector):
        index = selector.findData(value) if source else selector.findText(value)
        if index < 0 and value and (not source or value.isalpha() and len(value) in (2, 3)):
            selector.addItem(value, value if source else None)
            index = selector.count() - 1
        selector.setCurrentIndex(max(0, index))


def replace_pane_heading(pane, selector):
    layout = pane.layout()
    previous = layout.replaceWidget(pane.heading, selector)
    pane.heading.hide()
    layout.setAlignment(selector, Qt.AlignmentFlag.AlignLeft)
    del previous
