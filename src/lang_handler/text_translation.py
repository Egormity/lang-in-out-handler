"""Coalesce text translation while keeping only the newest editor request current."""

from copy import deepcopy
from dataclasses import dataclass

from PySide6.QtCore import QObject

from .api import OpenAIService
from .google_api import GoogleService
from .settings import Settings


@dataclass(frozen=True)
class TranslationRequest:
    text: str
    settings: Settings
    key: str
    automatic: bool
    epoch: int
    observed_source: str
    signature: tuple


def request_signature(text, settings, key):
    common = (text, settings.translation_provider, settings.translation_source_language,
              settings.target_language, settings.api_proxy_url)
    if settings.translation_provider == "google":
        return common
    return (*common, key, settings.translation_model, settings.translation_reasoning,
            settings.translation_instructions)


class TextTranslation(QObject):
    """One running HTTP request and one replaceable pending request; no parallel translations."""

    def __init__(self, controller):
        super().__init__(controller)
        self.c = controller
        self.job = None
        self.pending = None
        self._active = None
        self._desired = None
        self._epoch = 0
        self._completed = None
        self._closed = False

    @property
    def page(self):
        return self.c.window.pages["translate"]

    def translate(self, text, *, automatic=False):
        if self._closed:
            return
        if not text.strip():
            self.invalidate()
            if not automatic:
                self.c.fail("Enter or copy some text to translate.")
            return
        # Manual clicks and clipboard commands cancel the editor's trailing
        # debounce timer before a request is queued or key validation can return.
        self.page.request_started(text)
        settings = deepcopy(self.c.settings)
        if automatic and not settings.translation_auto_send:
            return
        google = settings.translation_provider == "google"
        key = "" if google else self.c.key if automatic else self.c.require_key()
        if not google and not key:
            self.invalidate()
            return
        self._epoch += 1
        request = TranslationRequest(
            text, settings, key, automatic, self._epoch,
            self.page.source.text.toPlainText(), request_signature(text, settings, key),
        )
        self._desired = request
        if self.job and self._active.signature == request.signature:
            # If the editor changed away and back, this still-running request can
            # serve the newest intent. Drop a pending request for the abandoned edit.
            self.pending = None
            self.page.set_busy(True)
            return
        if automatic and self._completed and self._completed[0] == request.signature:
            self.pending = None
            if self._is_current(request):
                self.c.window.set_translation(self._completed[1], text, settings.target_language)
            self.page.set_busy(False)
            return
        if self.job:
            self.pending = request
            self.page.set_busy(True)
            return
        self._start(request)

    def _is_current(self, request):
        desired = self._desired
        return (
            not self._closed and desired is not None and desired.epoch == self._epoch
            and desired.signature == request.signature
            and desired.observed_source == self.page.source.text.toPlainText()
            and request.signature == request_signature(request.text, self.c.settings, self.c.key)
        )

    def _start(self, request):
        self._active = request
        settings, text = request.settings, request.text
        google = settings.translation_provider == "google"
        self.page.set_busy(True)
        if not request.automatic:
            self.c.status("Translating…")

        def work(cancel, progress):
            service = (GoogleService(proxy=settings.api_proxy_url or None) if google else
                       OpenAIService(request.key, proxy=settings.api_proxy_url or None))
            try:
                source_options = ({"source_language": settings.translation_source_language}
                                  if settings.translation_source_language else {})
                if google:
                    return service.translate(text, settings.target_language, **source_options)
                return service.translate(
                    text, settings.translation_model, settings.target_language,
                    settings.translation_instructions, settings.translation_reasoning,
                    **source_options,
                )
            finally:
                service.close()

        def success(translated):
            if self._closed:
                return
            self._completed = (request.signature, translated)
            current = self._is_current(request)
            displayed = current and self.c.window.set_translation(
                translated, text, settings.target_language
            )
            self.c.remember("translate", text, translated,
                            "google-translate" if google else settings.translation_model)
            if current and not self._desired.automatic:
                self.c.status("Translation ready." if displayed else
                              "Translation saved in History; the original text or target language changed.")

        def failed(message):
            if self._is_current(request):
                self.c.fail(message)

        def done():
            self.job = None
            self._active = None
            following, self.pending = self.pending, None
            if following and self._is_current(following):
                self._start(following)
            else:
                self.page.set_busy(False)

        self.job = self.c.jobs.submit(work, success, failed, finished=done)

    def invalidate(self):
        """Forget the editor's old intent while allowing active HTTP work to finish."""
        self._epoch += 1
        self._desired = None
        self.pending = None
        self.page.set_busy(False)

    def shutdown(self):
        self._closed = True
        self.invalidate()
        if self.job:
            self.job.cancelled.set()
