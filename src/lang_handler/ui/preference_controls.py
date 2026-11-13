"""Reusable preference fields with clear number controls and individual resets."""

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QWidget,
)

from ..settings import Settings
from .common import button


class NumberInput(QWidget):
    """A keyboard-editable number with large, unambiguous step buttons."""

    def __init__(self, minimum, maximum, step=1, decimals=0, suffix="", name="Value"):
        super().__init__()
        self.spin = QDoubleSpinBox() if decimals else QSpinBox()
        if decimals:
            self.spin.setDecimals(decimals)
        self.spin.setRange(minimum, maximum)
        self.spin.setSingleStep(step)
        self.spin.setSuffix(suffix)
        # Qt 6.12 collapses the editor to 1 px with NoButtons + a stylesheet.
        # Hide its step subcontrols through QSS instead; use the full-size buttons.
        self.spin.setObjectName("preferenceNumber")
        self.spin.lineEdit().setTextMargins(8, 0, 8, 0)
        self.spin.setAccessibleName(name)
        self.spin.setMinimumWidth(105)
        self.spin.setMaximumWidth(190)
        self.decrease = button("−")
        self.increase = button("+")
        for control, action in ((self.decrease, "Decrease"), (self.increase, "Increase")):
            control.setObjectName("numberStep")
            control.setFixedWidth(36)
            control.setMinimumHeight(36)
            control.setAccessibleName(f"{action} {name.lower()}")
            control.setToolTip(f"{action} {name.lower()}")
        self.decrease.clicked.connect(self.spin.stepDown)
        self.increase.clicked.connect(self.spin.stepUp)
        self.spin.valueChanged.connect(self._update_steps)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.decrease)
        layout.addWidget(self.spin)
        layout.addWidget(self.increase)
        layout.addStretch()
        self._update_steps()

    def _update_steps(self):
        self.decrease.setEnabled(self.spin.value() > self.spin.minimum())
        self.increase.setEnabled(self.spin.value() < self.spin.maximum())

    def value(self):
        self.spin.interpretText()
        return self.spin.value()

    def setValue(self, value):
        self.spin.setValue(value)
        self._update_steps()


def editor_accessors(widget):
    """Default codecs; special fields supply explicit reader/writer functions."""
    if isinstance(widget, QCheckBox):
        return widget.isChecked, widget.setChecked
    if isinstance(widget, QPlainTextEdit):
        return widget.toPlainText, widget.setPlainText
    if isinstance(widget, QLineEdit):
        return lambda: widget.text().strip(), widget.setText
    if isinstance(widget, QComboBox):

        def select(value):
            if widget.findText(value) < 0:
                widget.addItem(value)
            widget.setCurrentText(value)

        return widget.currentText, select
    if isinstance(widget, NumberInput):
        return widget.value, widget.setValue
    raise TypeError(f"Unsupported preference field: {type(widget).__name__}")


@dataclass
class PreferenceField:
    read: Callable
    write: Callable
    default: object


class PreferenceFields:
    def __init__(self):
        self.fields = {}
        self.reset_buttons = {}
        self.defaults = Settings()
        self.committed = {}

    def add(self, form, title, key, widget, *, read=None, write=None, default=None):
        if read is None or write is None:
            read, write = editor_accessors(widget)
        if default is None:
            default = getattr(self.defaults, key)
        self.fields[key] = PreferenceField(read, write, default)
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(widget, 1)
        reset = button("↺")
        reset.setObjectName("preferenceReset")
        reset.setAccessibleName(f"Reset {title.lower()}")
        reset.setToolTip(f"Restore the default for {title.lower()}.")
        reset.setFixedSize(32, 32)
        layout.addWidget(reset, 0, Qt.AlignmentFlag.AlignTop)
        reset.clicked.connect(lambda: self.reset(key))
        self.reset_buttons[key] = reset
        form.addRow(title, row)
        return widget

    def reset(self, key):
        field = self.fields[key]
        field.write(field.default)

    def reset_all(self):
        for key in self.fields:
            self.reset(key)

    def discard_changes(self):
        """Restore the latest committed values, including updates received while editing."""
        for key, value in self.committed.items():
            self.fields[key].write(deepcopy(value))

    def update(self, settings):
        # External quick controls and shortcut actions update saved preferences too.
        # Keep edits made in this form until Save while refreshing untouched fields.
        # This baseline must not share the Settings instance that callers can mutate.
        pending = {
            key
            for key, field in self.fields.items()
            if key in self.committed and field.read() != self.committed[key]
        }
        for key, field in self.fields.items():
            if key.startswith("shortcut:"):
                value = settings.shortcuts.get(key.split(":", 1)[1], "")
            else:
                value = getattr(settings, key)
            if key not in pending or field.read() == value:
                field.write(value)
            self.committed[key] = deepcopy(value)

    @property
    def has_pending(self):
        return any(
            key in self.committed and field.read() != self.committed[key]
            for key, field in self.fields.items()
        )

    def collect(self):
        values = {}
        shortcuts = {}
        for key, field in self.fields.items():
            value = field.read()
            if key.startswith("shortcut:"):
                shortcuts[key.split(":", 1)[1]] = value
            else:
                values[key] = value
        if shortcuts:
            values["shortcuts"] = shortcuts
        # The visible translation pane is also the switch for translation requests.
        if "translation_visible" in values:
            values["translation_enabled"] = values["translation_visible"]
        return values
