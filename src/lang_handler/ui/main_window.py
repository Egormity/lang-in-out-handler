"""Desktop workbench shell; all IO is supplied by the application controller."""

from dataclasses import replace

from PySide6.QtCore import QSize, QTimer, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from lang_handler.results import TranslationResult
from lang_handler.settings import Settings

from .capture_page import CapturePage
from .common import button, label
from .drawing_page import DrawingPage
from .history import HistoryPage
from .icons import icon, icon_button
from .preferences import PreferencesPage
from .speech_controls import SpeechControls
from .text_pages import TranslatePage
from .theme import STYLE


class MainWindow(QMainWindow):
    capture_requested = Signal(str, bool)
    stop_requested = Signal(str)
    file_requested = Signal(str, str, bool)
    translate_requested = Signal(str)
    speech_requested = Signal(str)
    speech_stop_requested = Signal()
    speech_replay_requested = Signal(str)
    drawing_requested = Signal(bytes, int)
    drawing_cancel_requested = Signal()
    overlay_requested = Signal()
    settings_saved = Signal(object)
    key_saved = Signal(str)
    key_test_requested = Signal(str)
    models_requested = Signal(str)
    history_delete_requested = Signal()
    history_refresh_requested = Signal()

    def __init__(self, settings: Settings, api_key_present: bool = False):
        super().__init__()
        self.settings = settings
        self._reset_all_pending = False
        self.setWindowTitle("Lang In/Out")
        self.resize(1120, 780)
        self.setMinimumSize(850, 620)
        self.setStyleSheet(STYLE)
        central = QWidget()
        shell = QVBoxLayout(central)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        content = QHBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(0)
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(180)
        nav = QVBoxLayout(sidebar)
        nav.setContentsMargins(14, 24, 14, 16)
        brand = QLabel("Lang In/Out")
        brand.setObjectName("brand")
        nav.addWidget(brand)
        nav.addSpacing(26)
        self.navigation = QButtonGroup(self)
        self.navigation.setExclusive(True)
        self.stack = QStackedWidget()
        self.pages = {
            "input": CapturePage("input", settings),
            "output": CapturePage("output", settings),
            "translate": TranslatePage(settings),
            "drawing": DrawingPage(settings),
            "history": HistoryPage(),
            "preferences": PreferencesPage(settings, api_key_present),
        }
        self.nav_buttons = {}
        titles = {
            "input": "Dictate",
            "output": "Captions",
            "translate": "Translate",
            "drawing": "Draw",
            "history": "History",
            "preferences": "Preferences",
        }
        for mode, page in self.pages.items():
            if mode == "history":
                nav.addStretch()
            item = button(titles[mode])
            item.setObjectName("nav")
            nav_icons = {"input": "mic", "output": "captions", "translate": "translate",
                         "drawing": "draw", "history": "history", "preferences": "settings"}
            item.setIcon(icon(nav_icons[mode]))
            item.setIconSize(QSize(18, 18))
            item.setCheckable(True)
            item.clicked.connect(lambda checked=False, key=mode: self.show_page(key))
            self.navigation.addButton(item)
            self.nav_buttons[mode] = item
            nav.addWidget(item)
            self.stack.addWidget(page)
        nav.addSpacing(14)
        self.connection_badge = label("Key saved" if api_key_present else "API key needed")
        self.connection_badge.setObjectName("badge")
        nav.addWidget(self.connection_badge)
        self.connection_badge.setVisible(not api_key_present)
        content.addWidget(sidebar)
        content.addWidget(self.stack, 1)
        shell.addLayout(content, 1)
        self.status = QLabel("Add your OpenAI API key in Preferences." if not api_key_present else "")
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        self.speech_controls = SpeechControls()
        self.speech_controls.layout().setContentsMargins(16, 6, 16, 6)
        self.speech_controls.stop_requested.connect(self.speech_stop_requested)
        self.speech_controls.replay_requested.connect(self.speech_replay_requested)
        self.speech_controls.hide()
        self.pages["preferences"].attach_speech_controls(self.speech_controls)
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 12, 0)
        footer.addWidget(self.status, 1)
        self.stop_audio = icon_button("stop", "Stop speech")
        self.stop_audio.clicked.connect(self.speech_stop_requested)
        self.stop_audio.hide()
        footer.addWidget(self.stop_audio)
        shell.addLayout(footer)
        self.status.setVisible(not api_key_present)
        self.status_timer = QTimer(self)
        self.status_timer.setSingleShot(True)
        self.status_timer.timeout.connect(self.status.hide)
        self.setCentralWidget(central)
        for editor in self.findChildren(QPlainTextEdit):
            editor.setTabChangesFocus(True)
        self._connect_pages()
        self.show_page("input" if api_key_present else "preferences")

    def _connect_pages(self):
        for mode in ("input", "output"):
            page = self.pages[mode]
            page.capture_requested.connect(lambda chunked, key=mode: self._capture(key, chunked))
            page.stop_requested.connect(lambda key=mode: self.stop_requested.emit(key))
            page.file_requested.connect(
                lambda path, chunked, key=mode: self._file(key, path, chunked)
            )
            page.options_changed.connect(self._apply_settings_patch)
            page.speech_requested.connect(self._speak)
        self.pages["output"].overlay_requested.connect(self.overlay_requested)
        self.pages["translate"].requested.connect(self._translate)
        self.pages["translate"].speech_requested.connect(self._speak)
        self.pages["drawing"].requested.connect(self._drawing)
        self.pages["drawing"].cancel_requested.connect(self.drawing_cancel_requested)
        self.pages["drawing"].speech_requested.connect(self._speak)
        self.pages["drawing"].speech_stop_requested.connect(self.speech_stop_requested)
        self.pages["history"].speech_requested.connect(self._speak)
        for mode in ("input", "output", "translate", "drawing"):
            self.pages[mode].settings_saved.connect(self._apply_settings_patch)
        self.pages["translate"].options_changed.connect(self._apply_settings_patch)
        preferences = self.pages["preferences"]
        preferences.reset_all_requested.connect(self._stage_all_defaults)
        preferences.saved.connect(self._save_preferences)
        preferences.key_saved.connect(self.key_saved)
        preferences.key_test_requested.connect(self.key_test_requested)
        preferences.models_requested.connect(self.models_requested)
        self.pages["history"].delete_requested.connect(self.history_delete_requested)
        self.pages["history"].refresh_requested.connect(self.history_refresh_requested)

    def sync_mode_settings(self):
        """Quick controls save immediately; settings dialogs keep drafts until Save."""
        return self.settings

    def _apply_settings_patch(self, patch):
        settings = replace(self.settings, **patch)
        self.update_settings(settings)
        self.settings_saved.emit(settings)

    def _stage_all_defaults(self):
        self._reset_all_pending = True
        for mode in ("input", "output", "translate", "drawing"):
            self.pages[mode].tool_settings.reset_section()

    def _capture(self, mode, chunked):
        self.sync_mode_settings()
        self.capture_requested.emit(mode, chunked)

    def _file(self, mode, path, chunked):
        self.sync_mode_settings()
        self.file_requested.emit(mode, path, chunked)

    def _translate(self, text):
        self.sync_mode_settings()
        self.translate_requested.emit(text)

    def _speak(self, text):
        self.speech_requested.emit(text)

    def _drawing(self, image, revision):
        self.drawing_requested.emit(image, revision)

    def _save_preferences(self, patch):
        if self._reset_all_pending:
            patch = {**Settings().to_dict(), **patch}
            self._reset_all_pending = False
        self._apply_settings_patch(patch)

    def show_page(self, mode: str):
        mode = "translate" if mode == "tts" else mode
        if mode not in self.pages:
            return
        self.stack.setCurrentWidget(self.pages[mode])
        self.nav_buttons[mode].setChecked(True)
        if mode == "history":
            self.history_refresh_requested.emit()

    def set_status(self, text: str, error: bool = False):
        self.status_timer.stop()
        self.status.setText(text)
        self.status.setVisible(bool(text))
        if text and not error:
            self.status_timer.start(6000)
        self.status.setProperty("error", error)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    def set_recording(self, mode: str, active: bool):
        if mode in ("input", "output"):
            self.pages[mode].set_recording(active)
            self.nav_buttons[mode].setText(
                ("●  " if active else "") + ("Dictate" if mode == "input" else "Captions")
            )

    def append_result(self, mode: str, text: str, translation="", *, segment_id=None):
        if mode not in ("input", "output"):
            return
        page = self.pages[mode]
        result = translation if isinstance(translation, TranslationResult) else TranslationResult(translation)
        page.results.append(text, result.source_pronunciation, segment_id=segment_id)
        if page.translations:
            page.translations.append(result.translation, result.translation_pronunciation, segment_id=segment_id)

    def annotate_translation(self, mode, segment_id, result):
        page = self.pages[mode]
        if page.results.contains(segment_id):
            page.results.revise(segment_id, pronunciation=result.source_pronunciation)
            if page.translations:
                page.translations.upsert(segment_id, result.translation, result.translation_pronunciation)

    def set_translation(self, result, source_text=None, target_language=None):
        if isinstance(result, str):
            result = TranslationResult(result)
        return self.pages["translate"].set_result(result, source_text, target_language)

    def set_speech(self, path: str):
        self.speech_controls.set_audio(path)
        self.speech_controls.show()

    def set_speech_active(self, active):
        self.speech_controls.stop.setEnabled(active)
        self.stop_audio.setVisible(active)
        if active:
            self.speech_controls.show()
        self.pages["drawing"].set_speech_active(active)

    def set_source_text(self, mode: str, text: str):
        if mode in ("translate", "tts"):
            self.pages["translate"].source.text.setPlainText(text)

    def set_drawing_result(self, items: list[str], revision: int):
        self.pages["drawing"].set_result(items, revision)

    def set_drawing_busy(self, busy: bool):
        self.pages["drawing"].set_busy(busy)

    def drawing_revision(self) -> int:
        return self.pages["drawing"].canvas.revision

    def drawing_snapshot(self) -> bytes:
        return self.pages["drawing"].canvas.snapshot()

    def set_models(self, model_ids: list[str]):
        self.pages["preferences"].set_models(model_ids)
        for mode in ("input", "output", "translate", "drawing"):
            self.pages[mode].tool_settings.set_models(model_ids)

    def set_sources(self, sources: list[dict]):
        for mode in ("input", "output"):
            self.pages[mode].tool_settings.set_sources(sources)

    def set_level(self, mode: str, value: float):
        if mode in ("input", "output"):
            self.pages[mode].level.set_level(value)

    def set_history(self, history: list[dict]):
        self.pages["history"].set_entries(history)

    def set_key_status(self, text: str):
        self.pages["preferences"].key_status.setText(text)
        status = text.casefold()
        if "no api key" in status or "removed" in status or "not saved" in status:
            badge = "API key needed"
        elif "connected" in status or "verified" in status:
            badge = "Connection checked"
        else:
            badge = "Key saved"
        self.connection_badge.setText(badge)
        self.connection_badge.setVisible(badge == "API key needed")
        self.pages["preferences"].remove_key_button.setEnabled(badge != "API key needed")

    def key_saved_successfully(self):
        self.pages["preferences"].api_key.clear()

    def connection_proxy_url(self) -> str:
        return self.pages["preferences"].api_proxy_url.text().strip()

    def update_settings(self, settings):
        self.settings = settings
        self.pages["input"].apply_settings(settings)
        self.pages["output"].apply_settings(settings)
        self.pages["translate"].apply_settings(settings)
        self.pages["drawing"].update_settings(settings)
        self.pages["preferences"].update_settings(settings)
