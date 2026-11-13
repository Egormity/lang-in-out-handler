"""Scoped, draft-preserving settings editor embedded in a tool page."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from . import tool_setting_sections
from .common import button, label
from .model_choices import update_model_choices
from .preference_controls import PreferenceFields


class ToolSettings(QWidget):
    saved = Signal(object)

    def __init__(self, mode, settings):
        super().__init__()
        self.mode = mode
        self.settings = settings
        self.fields = PreferenceFields()
        self.reset_buttons = self.fields.reset_buttons
        self.models = {}
        self.instructions = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        if mode in ("input", "output"):
            tool_setting_sections.capture(self, settings, layout)
        elif mode == "translate":
            tool_setting_sections.translation(self, settings, layout)
        elif mode == "drawing":
            tool_setting_sections.handwriting(self, settings, layout)
        else:
            raise ValueError(f"Unknown settings section: {mode}")
        actions = QHBoxLayout()
        self.reset_button = button("Reset section")
        self.reset_button.clicked.connect(self.reset_section)
        self.save_hint = label("Save to apply changes.", True)
        self.save_button = button("Save settings", True)
        self.save_button.clicked.connect(lambda: self.saved.emit(self.collect()))
        actions.addWidget(self.reset_button)
        actions.addWidget(self.save_hint, 1)
        actions.addWidget(self.save_button)
        layout.addLayout(actions)
        self.update_settings(settings)

    def collect(self):
        """Return only owned fields so another page's edits cannot be overwritten."""
        return self.fields.collect()

    def update_settings(self, settings):
        self.settings = settings
        self.fields.update(settings)
        if self.mode == "drawing":
            self.drawing_delay.setEnabled(self.drawing_auto_send.isChecked())
        self.save_hint.setText(
            "Unsaved changes. Save to apply." if self.fields.has_pending else "Save to apply changes."
        )

    def reset_section(self):
        self.fields.reset_all()
        self.save_hint.setText("Defaults restored. Save to apply.")

    def set_models(self, model_ids):
        update_model_choices(self.models, model_ids)

    def set_sources(self, sources):
        for key in ("microphone_source", "output_source"):
            widget = getattr(self, key, None)
            if widget is not None:
                widget.set_sources(sources)
