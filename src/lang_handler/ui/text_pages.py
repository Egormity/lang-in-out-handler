"""A simple translation workspace with pronunciation beside each passage."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QSplitter, QVBoxLayout, QWidget

from .common import TextPane, button, label, selection_combo
from .icons import icon_button
from .tool_settings import ToolSettings, ToolSettingsDialog


class TranslatePage(QWidget):
    requested = Signal(str)
    settings_saved = Signal(object)
    options_changed = Signal(object)
    speech_requested = Signal(str)
    stop_requested = Signal()
    replay_requested = Signal(str)

    def __init__(self, settings):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(20)
        heading = QHBoxLayout()
        title = label("Translate")
        title.setObjectName("title")
        heading.addWidget(title, 1)
        self.settings_button = icon_button("settings", "Translation settings")
        heading.addWidget(self.settings_button)
        layout.addLayout(heading)
        self.tool_settings = ToolSettings("translate", settings)
        self.tool_settings.saved.connect(self.settings_saved)
        self.settings_dialog = ToolSettingsDialog(self.tool_settings, "Translation", self)
        self.settings_button.clicked.connect(self.settings_dialog.show_settings)
        controls = QHBoxLayout()
        controls.addWidget(label("Translate into", True))
        self.target = selection_combo(["English", "Japanese", "Russian", "Spanish", "French", "German"], settings.target_language)
        self.target.setFixedWidth(180)
        self.target.setAccessibleName("Translation language")
        controls.addWidget(self.target)
        controls.addStretch()
        layout.addLayout(controls)
        self.splitter = QSplitter()
        self.splitter.setChildrenCollapsible(False)
        self.source = TextPane("Original", "Type or paste text…", False)
        self.result = TextPane("Translation", "Your translation appears here.", False)
        self.speak_original, self.speak_translation = self.source.speak, self.result.speak
        self.source.speech_requested.connect(self.speech_requested)
        self.result.speech_requested.connect(self.speech_requested)
        self.splitter.addWidget(self.source)
        self.splitter.addWidget(self.result)
        self.splitter.setSizes([450, 450])
        layout.addWidget(self.splitter, 1)
        footer = QHBoxLayout()
        footer.addStretch()
        self.run = button("Translate", True)
        self.run.clicked.connect(lambda: self.requested.emit(self.source.text.toPlainText()))
        footer.addWidget(self.run)
        layout.addLayout(footer)
        self.apply_settings(settings)
        self.target.currentTextChanged.connect(lambda value: self.options_changed.emit({"target_language": value}))

    def set_result(self, result, source_text=None, target_language=None):
        if source_text is not None and self.source.text.toPlainText() != source_text:
            return False
        if target_language is not None and self.target.currentText() != target_language:
            return False
        self.result.text.setPlainText(result.translation)
        self.source.set_pronunciation(result.source_pronunciation)
        self.result.set_pronunciation(result.translation_pronunciation)
        return True

    def apply_settings(self, settings):
        self.tool_settings.update_settings(settings)
        self.target.blockSignals(True)
        if self.target.findText(settings.target_language) < 0:
            self.target.addItem(settings.target_language)
        self.target.setCurrentText(settings.target_language)
        self.target.blockSignals(False)
        self.result.heading.setText(settings.target_language)
