"""Coordinate desktop controls, audio capture, background API work, and history."""

import subprocess
import sys
from copy import deepcopy
from dataclasses import replace
from uuid import uuid4

from PySide6.QtCore import QObject

from .api import OpenAIService
from .audio import AudioCapture
from .desktop import clipboard_text
from .dictation import DictationDelivery
from .handwriting import Handwriting
from .jobs import Jobs
from .pipeline import CaptionPipeline
from .recording_cues import RecordingCues
from .results import TranslationResult
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
        self.pipeline.update_settings(self.settings)
        self.workflows = Workflows(self)
        self.dictation = DictationDelivery(self)
        self.handwriting = Handwriting(self)
        self.shortcuts = GlobalShortcuts()
        self.applied_shortcuts = None
        self.accept_audio = {"input": True, "output": True}
        self.caption_history = {}
        self.history_sessions = {}
        self.captures = {mode: AudioCapture(self) for mode in ("input", "output")}
        self.recording_cues = RecordingCues(self)
        self.captures["input"].started.connect(self.recording_cues.recording_started)
        self.captures["input"].stopped.connect(self.recording_cues.recording_stopped)
        for mode, capture in self.captures.items():
            capture.chunk.connect(lambda audio, m=mode: self._audio(m, audio))
            capture.error.connect(lambda message, m=mode: self._capture_error(m, message))
            capture.stopped.connect(lambda m=mode: self._stopped(m))
            capture.level.connect(lambda value, m=mode: self.window.set_level(m, value)
                                  if hasattr(self.window, "set_level") else None)
        self.pipeline.transcript.connect(self._transcript)
        self.pipeline.revisions.connect(self._revisions)
        self.pipeline.source_ready.connect(self.remember_segment)
        self.pipeline.error.connect(self._pipeline_error)
        self.pipeline.pending_changed.connect(self._pending)
        window.capture_requested.connect(self.start)
        window.stop_requested.connect(self.stop)
        window.file_requested.connect(self.workflows.import_file)
        window.translate_requested.connect(self.workflows.translate)
        window.speech_requested.connect(self.workflows.speak)
        window.audio_requested.connect(self.workflows.speak)
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
        overlay.stop_requested.connect(lambda: self.stop("output"))
        overlay.cleared.connect(self.clear_captions)
        window.pages["output"].cleared.connect(self.clear_captions)
        overlay.audio_requested.connect(self.workflows.speak)
        overlay.speech_stop_requested.connect(self.workflows.stop_speech)
        self.workflows.speech_active_changed.connect(window.set_speech_active)
        self.workflows.speech_active_changed.connect(overlay.set_speech_active)
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
        if any(not 2 <= value <= 30 for value in (settings.input_chunk_seconds, settings.output_chunk_seconds)):
            self.fail("Chunk length must be between 2 and 30 seconds.")
            return
        self.settings = deepcopy(settings)
        self.pipeline.update_settings(self.settings)
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
        self.pipeline.update_settings(self.settings)
        self.store.save_settings(self.settings)
        # Commit this connection field without applying other pending preferences.
        self.window.settings = replace(
            self.window.settings, api_proxy_url=self.settings.api_proxy_url
        )
        self.window.pages["preferences"].update_settings(self.window.settings)
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
        if self.pipeline_busy(mode):
            self.status("Finishing the previous recording. Please wait before starting another.")
            return
        self.pipeline.begin_session(mode)
        self.history_sessions[mode] = uuid4().hex
        try:
            source = self.settings.microphone_source if mode == "input" else self.settings.output_source or "@DEFAULT_MONITOR@"
            self.accept_audio[mode] = True
            if mode == "input":
                self.dictation.reset()
            capture.start(source, chunked, getattr(self.settings, f"{mode}_chunk_seconds"))
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

    def _transcript(self, mode, text, segment_id=None):
        self.window.append_result(mode, text, segment_id=segment_id)
        if mode == "output":
            self.overlay.append_caption(text, segment_id=segment_id)
        else:
            self.dictation.enqueue(text, self.settings.input_delivery)

    def pipeline_busy(self, mode):
        names = (mode, "translation") if mode == "output" else (mode,)
        return any(self.pipeline.busy[name] or self.pipeline.queues[name] for name in names)

    def remember_segment(self, mode, segment_id, text, model, *, session_id=None):
        record_id = self.store.add_history(
            mode, text, "", model,
            session_id=self.history_sessions.get(mode, "") if session_id is None else session_id,
        )
        if mode == "output":
            self.caption_history[segment_id] = record_id
            # Only the rolling context can be revised; keep a generous bounded map.
            while len(self.caption_history) > 512:
                self.caption_history.pop(next(iter(self.caption_history)))
        self.refresh_history()

    def _revisions(self, revisions):
        for revision in revisions:
            result = revision.result
            self.window.annotate_translation("output", revision.segment_id, result)
            self.overlay.annotate_translation(revision.segment_id, result)
            record_id = self.caption_history.get(revision.segment_id)
            if record_id is not None:
                self.store.update_history_translation(
                    record_id, result.translation, result.source_pronunciation,
                    result.translation_pronunciation,
                )
        self.refresh_history()

    def _pending(self, mode, count):
        if mode == "output" and self.accept_audio[mode]:
            self.overlay.set_status(f"Processing {count} audio segment(s)…" if count else
                                    "Listening…" if self.captures[mode].is_running else "Capture stopped.")
        if (not count and not self.captures[mode].is_running
                and not self.window.status.property("error")):
            self.window.set_status("Capture stopped. Recognized text is available in history.")

    def remember(self, mode, text, translation="", model=""):
        result = translation if isinstance(translation, TranslationResult) else TranslationResult(translation)
        self.store.add_history(
            mode, text, result.translation, model,
            source_pronunciation=result.source_pronunciation,
            translation_pronunciation=result.translation_pronunciation,
        )
        self.refresh_history()

    def refresh_history(self):
        self.window.set_history(self.store.list_history())

    def delete_history(self):
        self.caption_history.clear()
        self.store.delete_history()
        self.refresh_history()
        self.status("History deleted.")

    def show_overlay(self):
        self.overlay.show()
        self.overlay.raise_()

    def clear_captions(self):
        self.pipeline.clear_translation_context()
        self.workflows.files.context_epoch += 1
        page = self.window.pages["output"]
        for pane in (page.results, page.translations, self.overlay.transcript, self.overlay.translation):
            pane.clear()

    def action(self, action):
        if action in {"input", "output", "translate"}:
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
            self.workflows.speak(text, self.window.pages["translate"].source.audio)

    def shutdown(self):
        self.recording_cues.close()
        self.pipeline.shutdown()
        self.dictation.close()
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
