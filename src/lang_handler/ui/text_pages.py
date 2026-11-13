"""Translation with speech playback for the original and translated text."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QSplitter, QWidget

from .common import TextPane, button, label, selection_combo, title_block
from .sections import tool_layout


class TranslatePage(QWidget):
    requested = Signal(str)
    speech_requested = Signal(str)
    stop_requested = Signal()
    replay_requested = Signal(str)

    def __init__(self, settings):
        super().__init__()
        layout = tool_layout(self)
        layout.addWidget(title_block("Translate", "Translate text, then listen to either version."))
        actions = QHBoxLayout()
        actions.addWidget(label("Translate into"))
        self.target = selection_combo(
            ["English", "Japanese", "Russian", "Spanish", "French", "German"],
            settings.target_language,
        )
        self.target.setMinimumWidth(140)
        actions.addWidget(self.target)
        actions.addStretch()
        self.run = button("Translate text", True)
        self.run.clicked.connect(lambda: self.requested.emit(self.source.text.toPlainText()))
        actions.addWidget(self.run)
        layout.addLayout(actions)
        self.splitter = QSplitter()
        self.splitter.setHandleWidth(12)
        self.splitter.setChildrenCollapsible(False)
        self.source = TextPane("Original", "Type or paste text to translate or read aloud…", False)
        self.result = TextPane("Translation", "Your translation appears here.", False)
        self.speak_original = self.source.speak
        self.speak_translation = self.result.speak
        self.source.speech_requested.connect(self.speech_requested)
        self.result.speech_requested.connect(self.speech_requested)
        self.splitter.addWidget(self.source)
        self.splitter.addWidget(self.result)
        self.splitter.setSizes([450, 450])
        layout.addWidget(self.splitter, 1)
        self.apply_settings(settings)

    def apply_settings(self, settings):
        if self.target.findText(settings.target_language) < 0:
            self.target.addItem(settings.target_language)
        self.target.setCurrentText(settings.target_language)
