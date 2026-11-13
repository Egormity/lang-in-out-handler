"""Translation with speech playback for the original and translated text."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QPlainTextEdit, QSplitter, QVBoxLayout, QWidget

from .common import TextPane, button, editable_combo, label, title_block
from .sections import ExpandableSection, tool_layout
from .speech_controls import SpeechControls


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
        self.target = editable_combo(
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
        self.advanced = ExpandableSection("Translation and voice options")
        options = QHBoxLayout()
        translation_options = QVBoxLayout()
        translation_options.addWidget(label("Translation instructions", True))
        self.instructions = QPlainTextEdit(settings.translation_instructions)
        self.instructions.setAccessibleName("Translation instructions")
        self.instructions.setFixedHeight(82)
        translation_options.addWidget(self.instructions)
        speech_options = QVBoxLayout()
        speech_options.addWidget(label("Voice instructions", True))
        self.tts_instructions = QPlainTextEdit(settings.tts_instructions)
        self.tts_instructions.setAccessibleName("Voice instructions")
        self.tts_instructions.setFixedHeight(82)
        speech_options.addWidget(self.tts_instructions)
        options.addLayout(translation_options, 1)
        options.addLayout(speech_options, 1)
        self.advanced.body_layout.addLayout(options)
        self.model_summary = label("", True)
        self.advanced.body_layout.addWidget(self.model_summary)
        layout.addWidget(self.advanced)
        self.splitter = QSplitter()
        self.splitter.setHandleWidth(12)
        self.splitter.setChildrenCollapsible(False)
        self.source = TextPane("Original", "Type or paste text to translate or read aloud…", False)
        self.result = TextPane("Translation", "Your translation appears here.", False)
        self.speak_original = self.source.add_action("Speak original")
        self.speak_translation = self.result.add_action("Speak translation")
        self.speak_original.clicked.connect(
            lambda: self.speech_requested.emit(self.source.text.toPlainText())
        )
        self.speak_translation.clicked.connect(
            lambda: self.speech_requested.emit(self.result.text.toPlainText())
        )
        self.speak_original.setEnabled(False)
        self.speak_translation.setEnabled(False)
        self.source.text.textChanged.connect(
            lambda: self.speak_original.setEnabled(bool(self.source.text.toPlainText().strip()))
        )
        self.result.text.textChanged.connect(
            lambda: self.speak_translation.setEnabled(bool(self.result.text.toPlainText().strip()))
        )
        self.splitter.addWidget(self.source)
        self.splitter.addWidget(self.result)
        self.splitter.setSizes([450, 450])
        layout.addWidget(self.splitter, 1)
        self.speech_controls = SpeechControls()
        self.speech_controls.stop_requested.connect(self.stop_requested)
        self.speech_controls.replay_requested.connect(self.replay_requested)
        self.play = self.speech_controls.play
        self.save = self.speech_controls.save
        layout.addWidget(self.speech_controls)
        self.apply_settings(settings)

    def set_audio(self, path):
        self.speech_controls.set_audio(path)

    def apply_settings(self, settings):
        self.instructions.setPlainText(settings.translation_instructions)
        self.tts_instructions.setPlainText(settings.tts_instructions)
        self.target.setCurrentText(settings.target_language)
        self.model_summary.setText(
            f"Translation: {settings.translation_model}   ·   Voice: {settings.voice}   ·   Models in Preferences"
        )
