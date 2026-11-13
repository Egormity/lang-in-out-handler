"""Floating captions with independently visible transcript and translation panes."""

from dataclasses import replace

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QSplitter, QVBoxLayout, QWidget

from ..window_pin import WindowPin
from .common import TextPane, button, label
from .theme import STYLE


class CaptionOverlay(QWidget):
    settings_changed = Signal(object)
    stop_requested = Signal()

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.setWindowTitle("Lang In/Out · Captions")
        self.setWindowFlags(Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setStyleSheet(STYLE)
        self.resize(900, 330)
        self.setMinimumSize(460, 200)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        toolbar = QHBoxLayout()
        self.transcript_toggle = QCheckBox("Transcript")
        self.translation_toggle = QCheckBox("Translation")
        for toggle in (self.transcript_toggle, self.translation_toggle):
            toggle.setFocusPolicy(Qt.FocusPolicy.TabFocus)
            toolbar.addWidget(toggle)
        self.translation_toggle.setToolTip("Show translated captions.")
        toolbar.addStretch()
        self.pin = QCheckBox("On top")
        toolbar.addWidget(self.pin)
        hide = button("Hide")
        hide.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        hide.clicked.connect(self.hide)
        stop = button("Stop")
        stop.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        stop.clicked.connect(self.stop_requested)
        toolbar.addWidget(hide)
        toolbar.addWidget(stop)
        layout.addLayout(toolbar)
        self.pin_status = QLabel()
        self.pin_status.setObjectName("muted")
        self.pin_status.setWordWrap(True)
        self.pin_status.hide()
        layout.addWidget(self.pin_status)
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
        self.status.setWordWrap(True)
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
        self.pin_control = WindowPin(self)
        self.pin_control.changed.connect(self._pin_state)
        self.pin_control.message.connect(self._pin_message)
        self.pin.toggled.connect(lambda enabled: self.pin_control.request(enabled, activate=True))
        self.pin_control.request(True)

    def _pin_state(self, enabled):
        with QSignalBlocker(self.pin):
            self.pin.setChecked(enabled)

    def _pin_message(self, message):
        self.pin_status.setText(message)
        self.pin_status.setVisible(bool(message))

    def showEvent(self, event):
        super().showEvent(event)
        self.pin_control.on_show()

    def _changed(self):
        self.settings = replace(
            self.settings,
            transcript_visible=self.transcript_toggle.isChecked(),
            translation_visible=self.translation_toggle.isChecked(),
            translation_enabled=self.translation_toggle.isChecked(),
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
        self.pin_control.stop()
        self.hide()
        event.ignore()
