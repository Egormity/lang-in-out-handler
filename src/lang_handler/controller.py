"""Coordinate desktop controls, audio capture, background API work, and history."""

import subprocess
import sys
from copy import deepcopy

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from .api import OpenAIService
from .audio import AudioCapture
from .desktop import clipboard_text, copy_and_paste
from .handwriting import Handwriting
from .jobs import Jobs
from .pipeline import CaptionPipeline
from .shortcuts import GlobalShortcuts
from .workflows import Workflows


class Controller(QObject):
    def __init__(self, window, overlay, store, credentials):
        super().__init__(window)
        self.window, self.overlay = window, overlay
        self.store, self.credentials = store, credentials
        self.settings = store.load_settings()
        self.settings.translation_enabled = self.settings.translation_visible
        self.key = credentials.get()
        self.jobs = Jobs(self)
        self.pipeline = CaptionPipeline(self.jobs, self)
        self.workflows = Workflows(self)
        self.handwriting = Handwriting(self)
        self.shortcuts = GlobalShortcuts()
        self.applied_shortcuts = None
        self.accept_audio = {"input": True, "output": True}
        self.last_dictation = ""
        self.captures = {mode: AudioCapture(self) for mode in ("input", "output")}
        for mode, capture in self.captures.items():
            capture.chunk.connect(lambda audio, m=mode: self._audio(m, audio))
            capture.error.connect(lambda message, m=mode: self._capture_error(m, message))
            capture.stopped.connect(lambda m=mode: self._stopped(m))
            capture.level.connect(lambda value, m=mode: self.window.set_level(m, value)
                                  if hasattr(self.window, "set_level") else None)
        self.pipeline.transcript.connect(self._transcript)
        self.pipeline.translation.connect(self._translation)
        self.pipeline.completed.connect(self.remember)
        self.pipeline.error.connect(self._pipeline_error)
        self.pipeline.pending_changed.connect(self._pending)
        window.capture_requested.connect(self.start)
        window.stop_requested.connect(self.stop)
        window.file_requested.connect(self.workflows.import_file)
        window.translate_requested.connect(self.workflows.translate)
        window.speech_requested.connect(self.workflows.speak)
        window.speech_stop_requested.connect(self.workflows.stop_speech)
        window.speech_replay_requested.connect(self.workflows.replay)
        window.drawing_requested.connect(self.handwriting.recognize)
        window.drawing_cancel_requested.connect(self.handwriting.cancel)
        window.overlay_requested.connect(self.show_overlay)
        window.settings_saved.connect(self.save_settings)
        window.key_saved.connect(self.save_key)
        window.key_test_requested.connect(self.test_key)
        window.models_requested.connect(self.test_key)
        window.history_refresh_requested.connect(self.refresh_history)
        window.history_delete_requested.connect(self.delete_history)
        overlay.settings_changed.connect(self.save_settings)
        overlay.stop_requested.connect(lambda: self.stop("output"))
        self.refresh_history()
        self.window.set_key_status(self.credentials.backend_label if self.key else "No API key saved.")

    def status(self, message):
        self.window.set_status(message)

    def fail(self, message):
        self.window.set_status(message, True)

    def require_key(self):
        if not self.key:
            self.fail("Add your OpenAI API key in Preferences first.")
            self.window.show_page("preferences")
            self.window.show()
        return self.key

    def apply_shortcuts(self):
        try:
            message = self.shortcuts.apply(self.settings.shortcuts,
                                           [sys.executable, "-m", "lang_handler"])
            self.applied_shortcuts = deepcopy(self.settings.shortcuts)
            self.status(message)
        except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
            self.fail(str(exc))

    def save_settings(self, settings):
        if not 2 <= settings.chunk_seconds <= 30:
            self.fail("Chunk length must be between 2 and 30 seconds.")
            return
        self.settings = deepcopy(settings)
        self.store.save_settings(self.settings)
        self.overlay.update_settings(self.settings)
        self.window.update_settings(self.settings)
        if self.applied_shortcuts != self.settings.shortcuts:
            self.apply_shortcuts()

    def save_key(self, key):
        try:
            if key.strip():
                self.credentials.set(key.strip())
            else:
                self.credentials.delete()
            self.key = key.strip()
            self.window.key_saved_successfully()
            self.window.set_key_status(self.credentials.backend_label if self.key else "API key removed.")
            self.status("API key saved." if self.key else "API key removed.")
            return True
        except (OSError, RuntimeError, ValueError) as exc:
            self.fail(str(exc))
            return False

    def test_key(self, candidate=""):
        if candidate.strip() and not self.save_key(candidate):
            return
        key = self.require_key()
        if not key:
            return
        # Connection buttons apply the proxy being edited without resetting other
        # unsaved model/language controls in the preferences page.
        self.settings.api_proxy_url = self.window.connection_proxy_url()
        self.store.save_settings(self.settings)
        self.status("Checking OpenAI model access…")
        proxy = self.settings.api_proxy_url or None

        def work(cancel, progress):
            service = OpenAIService(key, proxy=proxy)
            try:
                return service.list_models()
            finally:
                service.close()

        def success(models):
            if key != self.key:
                return
            self.window.set_models(models)
            self.window.set_key_status(f"Connected · {len(models)} models · {self.credentials.backend_label}")
            self.status("API key accepted. Model access checked; paid requests also require available API credit.")

        def failed(message):
            if key == self.key:
                self.fail(message)

        self.jobs.submit(work, success, failed)

    def start(self, mode, chunked):
        if mode not in self.captures or not self.require_key():
            return
        if mode in self.workflows.imports:
            self.fail("Stop the file import before recording.")
            return
        capture = self.captures[mode]
        if capture.is_running:
            return
        try:
            source = self.settings.microphone_source if mode == "input" else self.settings.output_source or "@DEFAULT_MONITOR@"
            self.accept_audio[mode] = True
            if mode == "input":
                self.last_dictation = ""
            capture.start(source, chunked, self.settings.chunk_seconds)
            self.window.set_recording(mode, True)
            if mode == "output":
                self.show_overlay()
                self.overlay.set_status("Listening to system audio…")
            self.status("Listening to microphone…" if mode == "input" else "Listening to system audio…")
        except (OSError, RuntimeError, ValueError) as exc:
            self.fail(str(exc))

    def stop(self, mode):
        self.workflows.cancel_import(mode)
        self.captures[mode].stop()
        self.status("Stopping capture; finishing the last audio segment…")
        if mode == "output":
            self.overlay.set_status("Finishing the last audio segment…")

    def _stopped(self, mode):
        self.window.set_recording(mode, False)

    def _capture_error(self, mode, message):
        self.fail(message)
        if mode == "output":
            self.overlay.set_status(message)

    def _audio(self, mode, audio):
        if self.accept_audio[mode]:
            self.pipeline.enqueue(mode, audio, self.settings, self.key)

    def _pipeline_error(self, mode, message):
        self.accept_audio[mode] = False
        self.captures[mode].stop()
        self.fail(message)
        if mode == "output":
            self.overlay.set_status(message)

    def _transcript(self, mode, text):
        self.window.append_result(mode, text)
        if mode == "output":
            self.overlay.append_caption(text)
        else:
            try:
                paste = self.settings.auto_paste and QApplication.activeWindow() is None
                separator = " " if (paste and self.last_dictation and text and
                                     self.last_dictation[-1].isascii() and text[0].isascii()) else ""
                self.status(copy_and_paste(separator + text, paste))
                self.last_dictation = text if paste else ""
            except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
                self.fail("Transcript ready; clipboard insertion failed: " + str(exc))

    def _translation(self, mode, text):
        self.window.append_result(mode, "", text)
        self.overlay.append_caption("", text)

    def _pending(self, mode, count):
        if mode == "output" and self.accept_audio[mode]:
            self.overlay.set_status(f"Processing {count} audio segment(s)…" if count else
                                    "Listening…" if self.captures[mode].is_running else "Capture stopped.")
        if (not count and not self.captures[mode].is_running
                and not self.window.status.property("error")):
            self.window.set_status("Capture stopped. Recognized text is available in history.")

    def remember(self, mode, text, translation="", model=""):
        self.store.add_history(mode, text, translation, model)
        self.refresh_history()

    def refresh_history(self):
        self.window.set_history(self.store.list_history())

    def delete_history(self):
        self.store.delete_history()
        self.refresh_history()
        self.status("History deleted.")

    def show_overlay(self):
        self.overlay.show()
        self.overlay.raise_()

    def action(self, action):
        if action in {"input", "output", "translate", "tts", "drawing"}:
            self.window.sync_mode_settings()
        if action in self.captures:
            if self.captures[action].is_running or action in self.workflows.imports:
                self.stop(action)
            else:
                self.start(action, getattr(self.settings, f"{action}_chunked"))
        elif action in ("translate", "tts"):
            # A Wayland clipboard owner may need our GUI event loop to answer a
            # selection request. Read in a worker so global shortcuts cannot block it.
            self.jobs.submit(lambda cancel, progress: clipboard_text(),
                             lambda text: self._clipboard_action(action, text), self.fail)
        elif action == "drawing":
            self.window.show_page("drawing")
            self.window.pages["drawing"].show_floating()
        else:
            self.window.show()
            self.window.raise_()
            self.window.activateWindow()

    def _clipboard_action(self, action, text):
        self.window.set_source_text(action, text)
        if action == "translate":
            self.window.show_page("translate")
            self.window.show()
            self.workflows.translate(text)
        else:
            self.workflows.speak(text)

    def shutdown(self):
        self.pipeline.shutdown()
        self.overlay.pin_control.stop()
        self.handwriting.cancel()
        self.window.pages["drawing"].shutdown()
        self.jobs.cancel_all()
        self.workflows.shutdown()
        for mode, capture in self.captures.items():
            self.accept_audio[mode] = False
            capture.stop()
        for capture in self.captures.values():
            capture.wait()
