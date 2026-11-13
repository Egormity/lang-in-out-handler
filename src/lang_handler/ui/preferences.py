"""Application-wide connection, speech, and shortcut preferences."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QTabWidget, QVBoxLayout, QWidget

from . import preference_sections
from .common import button, label
from .model_choices import update_model_choices
from .preference_controls import PreferenceFields
from .sections import scrollable_body


class PreferencesPage(QWidget):
    saved = Signal(object)
    reset_all_requested = Signal()
    discard_requested = Signal()
    key_saved = Signal(str)
    key_test_requested = Signal(str)
    models_requested = Signal(str)

    def __init__(self, settings, api_key_present=False):
        super().__init__()
        self.settings = settings
        self.fields = PreferenceFields()
        self.reset_buttons = self.fields.reset_buttons
        self.instructions = {}
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 20)
        outer.setSpacing(16)
        heading = QHBoxLayout()
        title = label("Preferences")
        title.setObjectName("title")
        heading.addWidget(title)
        outer.addLayout(heading)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().setDrawBase(False)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.addTab(self._connection(settings, api_key_present), "Connection")
        self.models = {}
        for builder, title in [
            (preference_sections.speech, "Shared speech"),
            (preference_sections.shortcuts, "Shortcuts"),
        ]:
            self.tabs.addTab(builder(self, settings), title)
        outer.addWidget(self.tabs, 1)
        self.reset_all_button = button("Reset all")
        self.reset_all_button.setToolTip(
            "Restore all preference defaults. Save to apply; your API key is kept."
        )
        self.reset_all_button.clicked.connect(self.reset_all)
        self.save_hint = label("", True)
        self.fields.changed.connect(self._draft_changed)
        heading.addWidget(self.save_hint, 1)
        heading.addWidget(self.reset_all_button)
        self.discard_button = button("Discard changes")
        self.discard_button.clicked.connect(self.discard_changes)
        heading.addWidget(self.discard_button)
        self.save_preferences = button("Save", True)
        self.save_preferences.clicked.connect(lambda: self.saved.emit(self.collect()))
        heading.addWidget(self.save_preferences)
        self.update_settings(settings)

    def _connection(self, settings, api_key_present):
        scroll, layout = scrollable_body()
        layout.addWidget(label(
            "An OpenAI key is needed for speech features. Google Draw and Translate work without one.",
            True,
        ))
        form = preference_sections.group("OpenAI API key", layout)
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("Paste a new API key")
        form.addRow("API key", self.api_key)
        actions = QHBoxLayout()
        actions.setSpacing(8)
        save_key = button("Save key")
        self.test_key_button = button("Test connection", True)
        self.refresh_models_button = button("Refresh models")
        self.remove_key_button = button("Remove key")
        self.remove_key_button.setObjectName("quiet")
        self.remove_key_button.setEnabled(api_key_present)
        self.remove_key_button.clicked.connect(self._remove_key)
        for item in (save_key, self.test_key_button, self.refresh_models_button):
            actions.addWidget(item)
        form.addRow(actions)
        self.key_status = label("API key saved." if api_key_present else "No API key saved.", True)
        form.addRow(self.key_status)
        remove_row = QHBoxLayout()
        remove_row.addStretch()
        remove_row.addWidget(self.remove_key_button)
        form.addRow(remove_row)
        save_key.clicked.connect(self._save_key)
        self.test_key_button.clicked.connect(
            lambda: self.key_test_requested.emit(self.api_key.text().strip())
        )
        self.refresh_models_button.clicked.connect(
            lambda: self.models_requested.emit(self.api_key.text().strip())
        )
        self.api_key.textChanged.connect(self._update_key_actions)
        form = preference_sections.group("Network", layout)
        self.api_proxy_url = QLineEdit(settings.api_proxy_url)
        self.api_proxy_url.setPlaceholderText("Automatic — use environment or system proxy")
        self.api_proxy_url.setToolTip(
            "Optional override. Leave empty to use your environment proxy or GNOME system proxy automatically. Supports HTTP, HTTPS, and SOCKS5 URLs."
        )
        self.fields.add(form, "Proxy override", "api_proxy_url", self.api_proxy_url)
        form.addRow(
            label(
                "Leave the proxy blank to use your system connection.",
                True,
            )
        )
        layout.addStretch()
        return scroll

    def _save_key(self):
        value = self.api_key.text().strip()
        if value:
            self.key_saved.emit(value)

    def _update_key_actions(self):
        pending = bool(self.api_key.text().strip())
        self.test_key_button.setText("Save and test" if pending else "Test connection")
        self.refresh_models_button.setText("Save and refresh" if pending else "Refresh models")
        hint = "Save and use the key entered above." if pending else "Use the saved API key."
        self.test_key_button.setToolTip(hint)
        self.refresh_models_button.setToolTip(hint)

    def _remove_key(self):
        self.key_saved.emit("")

    def collect(self):
        return self.fields.collect()

    def _draft_changed(self):
        self.save_hint.setText("Unsaved changes" if self.fields.has_pending else "")

    def reset_all(self):
        self.fields.reset_all()
        self.save_hint.setText("All defaults restored. Save to apply.")
        self.reset_all_requested.emit()

    def discard_changes(self):
        self.fields.discard_changes()
        self.api_key.clear()
        self.save_hint.setText("")
        self.discard_requested.emit()

    def set_models(self, model_ids):
        update_model_choices(self.models, model_ids)

    def attach_speech_controls(self, controls):
        """Keep saved-audio actions with the shared voice preferences."""
        body = self.tabs.widget(1).widget().layout()
        body.insertWidget(body.count() - 1, controls)

    def update_settings(self, settings):
        self.settings = settings
        self.fields.update(settings)
        self.save_hint.setText(
            "Unsaved changes"
            if self.fields.has_pending
            else ""
        )

    def set_sources(self, sources):
        # Devices are owned by the Voice input and Live captions settings panels.
        pass
