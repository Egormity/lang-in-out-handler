"""Floating captions with independently visible transcript and translation panes."""

from dataclasses import replace

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QSplitter, QVBoxLayout, QWidget

from .common import TextPane, button, label
from .theme import STYLE


class CaptionOverlay(QWidget):
    settings_changed = Signal(object)
    stop_requested = Signal()

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.setWindowTitle("Lang In/Out · Captions")
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setStyleSheet(STYLE)
        self.resize(900, 330)
        self.setMinimumSize(460, 200)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        toolbar = QHBoxLayout()
        self.transcript_toggle = QCheckBox("Transcript")
        self.translation_toggle = QCheckBox("Translation")
        self.generate_toggle = QCheckBox("Translate audio")
        for toggle in (self.transcript_toggle, self.translation_toggle, self.generate_toggle):
            toggle.setFocusPolicy(Qt.FocusPolicy.TabFocus)
            toolbar.addWidget(toggle)
        self.transcript_toggle.setToolTip(
            "Show or hide the transcript pane. Recognition continues because translation uses the transcript."
        )
        self.translation_toggle.setToolTip("Show or hide the translated text pane.")
        self.generate_toggle.setToolTip(
            "Enable translation requests. Hiding a pane does not disable translation."
        )
        toolbar.addStretch()
        hide = button("Hide")
        hide.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        hide.clicked.connect(self.hide)
        stop = button("Stop")
        stop.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        stop.clicked.connect(self.stop_requested)
        toolbar.addWidget(hide)
        toolbar.addWidget(stop)
        layout.addLayout(toolbar)
        self.splitter = QSplitter()
        self.transcript = TextPane("TRANSCRIPT", "Listening for speech…")
        self.translation = TextPane("TRANSLATION", "Translated captions will appear here.")
        self.transcript.text.document().setMaximumBlockCount(100)
        self.translation.text.document().setMaximumBlockCount(100)
        self.splitter.addWidget(self.transcript)
        self.splitter.addWidget(self.translation)
        self.splitter.setSizes([450, 450])
        layout.addWidget(self.splitter, 1)
        self.empty = label("Both panes are hidden. Turn on Transcript or Translation above.", True)
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty, 1)
        self.status = QLabel("Ready")
        self.status.setObjectName("muted")
        footer = QHBoxLayout()
        footer.addWidget(self.status, 1)
        self.clear_button = button("Clear view")
        self.clear_button.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.clear_button.setToolTip(
            "Clear the visible captions. Recording and saved history continue."
        )
        self.clear_button.clicked.connect(self.clear)
        footer.addWidget(self.clear_button)
        layout.addLayout(footer)
        self.update_settings(settings)
        self.transcript_toggle.toggled.connect(self._changed)
        self.translation_toggle.toggled.connect(self._changed)
        self.generate_toggle.toggled.connect(self._changed)

    def _changed(self):
        self.settings = replace(
            self.settings,
            transcript_visible=self.transcript_toggle.isChecked(),
            translation_visible=self.translation_toggle.isChecked(),
            translation_enabled=self.generate_toggle.isChecked(),
        )
        self._visibility()
        self.settings_changed.emit(self.settings)

    def _visibility(self):
        self.transcript.setVisible(self.settings.transcript_visible)
        self.translation.setVisible(self.settings.translation_visible)
        any_visible = self.settings.transcript_visible or self.settings.translation_visible
        self.splitter.setVisible(any_visible)
        self.empty.setVisible(not any_visible)

    def update_settings(self, settings):
        self.settings = settings
        for toggle, checked in [
            (self.transcript_toggle, settings.transcript_visible),
            (self.translation_toggle, settings.translation_visible),
            (self.generate_toggle, settings.translation_enabled),
        ]:
            toggle.blockSignals(True)
            toggle.setChecked(checked)
            toggle.blockSignals(False)
        self._visibility()
        self.setWindowOpacity(settings.overlay_opacity)
        for pane in (self.transcript, self.translation):
            font = pane.text.font()
            font.setPixelSize(settings.font_size)
            pane.text.setFont(font)
            pane.text.setStyleSheet(f"QPlainTextEdit {{ font-size: {settings.font_size}px; }}")

    def append_caption(self, text: str, translation: str = ""):
        self.transcript.append(text)
        self.translation.append(translation)

    def set_status(self, text: str):
        self.status.setText(text)

    def clear(self):
        self.transcript.text.clear()
        self.translation.text.clear()

    def closeEvent(self, event):
        # Closing hides the overlay; the running session is controlled by Stop.
        self.hide()
        event.ignore()
