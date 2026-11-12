"""Microphone dictation and system audio capture controls."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QPlainTextEdit,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .audio_controls import AudioLevel
from .common import TextPane, button, label, title_block


class CapturePage(QWidget):
    capture_requested = Signal(bool)
    stop_requested = Signal()
    file_requested = Signal(str, bool)
    overlay_requested = Signal()

    def __init__(self, mode: str, settings):
        super().__init__()
        self.mode = mode
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(14)
        is_input = mode == "input"
        layout.addWidget(
            title_block(
                "Voice input" if is_input else "Live captions",
                "Speak, transcribe, and send text to your active app."
                if is_input
                else "Read the audio playing on your computer, with translation alongside.",
            )
        )
        row = QHBoxLayout()
        self.capture_type = QComboBox()
        self.capture_type.addItem("One recording · transcribe on stop", False)
        self.capture_type.addItem("Continuous · transcribe in chunks", True)
        self.capture_type.setCurrentIndex(int(getattr(settings, f"{mode}_chunked")))
        row.addWidget(self.capture_type, 1)
        self.start_button = button("Start microphone" if is_input else "Start captions", True)
        self.stop_button = button("Stop")
        self.stop_button.setEnabled(False)
        row.addWidget(self.start_button)
        row.addWidget(self.stop_button)
        layout.addLayout(row)
        options = QHBoxLayout()
        self.option = QCheckBox(
            "Paste transcript into active app" if is_input else "Translate captions"
        )
        self.option.setChecked(settings.auto_paste if is_input else settings.translation_enabled)
        options.addWidget(self.option)
        options.addStretch()
        self.import_button = button("Open audio file…")
        options.addWidget(self.import_button)
        if not is_input:
            show = button("Show floating captions")
            show.clicked.connect(self.overlay_requested)
            options.addWidget(show)
        layout.addLayout(options)
        self.level = AudioLevel()
        layout.addWidget(self.level)
        layout.addWidget(label("Instructions / recognition context"))
        self.instructions = QPlainTextEdit(getattr(settings, f"{mode}_instructions"))
        self.instructions.setPlaceholderText(
            "Names, vocabulary, or context to help the model recognize speech…"
        )
        self.instructions.setMaximumHeight(86)
        layout.addWidget(self.instructions)
        self.results = TextPane("Transcript", "Your words will appear here.")
        self.translations = None
        if is_input:
            layout.addWidget(self.results, 1)
        else:
            split = QSplitter()
            split.addWidget(self.results)
            self.translations = TextPane("Translation", "Translations appear when enabled.")
            split.addWidget(self.translations)
            split.setSizes([450, 450])
            layout.addWidget(split, 1)
        clear = button("Clear view")
        clear.clicked.connect(self.clear)
        footer = QHBoxLayout()
        footer.addWidget(
            label("Audio is sent to OpenAI when you start or import a recording.", True), 1
        )
        footer.addWidget(clear)
        layout.addLayout(footer)
        self.start_button.clicked.connect(lambda: self.capture_requested.emit(self.chunked()))
        self.stop_button.clicked.connect(self.stop_requested)
        self.import_button.clicked.connect(self._import)

    def chunked(self) -> bool:
        return bool(self.capture_type.currentData())

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Transcribe audio",
            "",
            "Audio / video (*.wav *.mp3 *.m4a *.ogg *.flac *.webm *.mp4 *.mpeg);;All files (*)",
        )
        if path:
            self.file_requested.emit(path, self.chunked())

    def set_recording(self, active: bool):
        self.start_button.setEnabled(not active)
        self.import_button.setEnabled(not active)
        self.stop_button.setEnabled(active)
        self.capture_type.setEnabled(not active)
        if not active:
            self.level.set_level(0)

    def clear(self):
        self.results.text.clear()
        if self.translations:
            self.translations.text.clear()

    def apply_settings(self, settings):
        self.instructions.setPlainText(getattr(settings, f"{self.mode}_instructions"))
        self.capture_type.setCurrentIndex(int(getattr(settings, f"{self.mode}_chunked")))
        self.option.setChecked(
            settings.auto_paste if self.mode == "input" else settings.translation_enabled
        )
