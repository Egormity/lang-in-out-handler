"""Google routes work without a key and preserve continuous captions/history."""

import threading
from dataclasses import replace

import pytest
from PySide6.QtCore import QPointF

from lang_handler.errors import ServiceError
from lang_handler.ink import InkSnapshot
from lang_handler.results import CaptionRevision, TranslationResult
from lang_handler.text_utils import flowing_text

pytest_plugins = ("test_controller",)


class Google:
    def __init__(self, **kwargs):
        pass

    def translate(self, text, target_language):
        return TranslationResult("translated " + text, "source guide", "target guide")

    def recognize_handwriting(self, ink, language):
        assert isinstance(ink, InkSnapshot)
        assert ink.strokes and language == "ja"
        return ["わ", "れ"]

    def revise_translation(self, segments, target_language):
        result = self.translate(flowing_text(text for _, text in segments), target_language)
        return [CaptionRevision(i, text, result if n == 0 else TranslationResult(""))
                for n, (i, text) in enumerate(segments)]

    def close(self):
        pass


def google_settings(c):
    c.save_settings(replace(c.settings, drawing_provider="google", translation_provider="google",
                            drawing_language="ja", drawing_auto_send=False))


def test_drawing_signal_exports_strokes_and_history_without_openai_key(controller, qtbot, monkeypatch):
    c = controller
    google_settings(c)
    c.key = ""
    monkeypatch.setattr("lang_handler.handwriting.GoogleService", Google)
    monkeypatch.setattr(c, "require_key", lambda: (_ for _ in ()).throw(AssertionError("OpenAI key requested")))
    page = c.window.pages["drawing"]
    page.canvas.begin_stroke(QPointF(30, 30))
    page.canvas.end_stroke(QPointF(70, 80))
    page.send()
    qtbot.waitUntil(lambda: c.handwriting.job is None)
    rows = c.store.list_history()
    assert {row["source_text"] for row in rows} == {"わ", "れ"}
    assert {row["model"] for row in rows} == {"google-handwriting"}


def test_translate_without_openai_key_preserves_guides(controller, qtbot, monkeypatch):
    c = controller
    google_settings(c)
    c.key = ""
    monkeypatch.setattr("lang_handler.workflows.GoogleService", Google)
    monkeypatch.setattr(c, "require_key", lambda: (_ for _ in ()).throw(AssertionError("OpenAI key requested")))
    c.window.set_source_text("translate", "ともだち")
    c.workflows.translate("ともだち")
    qtbot.waitUntil(lambda: c.workflows.translation_job is None)
    assert c.window.pages["translate"].result.text.toPlainText() == "translated ともだち"
    row = c.store.list_history()[0]
    assert row["model"] == "google-translate"
    assert row["source_pronunciation"] == "source guide"


def test_google_failure_does_not_fall_back_to_paid_openai(controller, qtbot, monkeypatch):
    class Denied(Google):
        def translate(self, *args):
            raise ServiceError("Google rate limit reached. Try again later.")

    c = controller
    google_settings(c)
    monkeypatch.setattr("lang_handler.workflows.GoogleService", Denied)
    monkeypatch.setattr("lang_handler.workflows.OpenAIService", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("fallback")))
    errors = []
    monkeypatch.setattr(c, "fail", errors.append)
    c.workflows.translate("hello")
    qtbot.waitUntil(lambda: c.workflows.translation_job is None)
    assert errors and "rate limit" in errors[0]
    assert c.store.list_history() == []


def test_google_caption_batches_do_not_duplicate_overlap(controller, qtbot, monkeypatch):
    c = controller
    google_settings(c)
    monkeypatch.setattr("lang_handler.pipeline.GoogleService", Google)
    c.start("output", True)
    for number in range(1, 9):
        c.pipeline.enqueue("output", str(number).encode(), c.settings, c.key)
        qtbot.waitUntil(lambda: not c.pipeline_busy("output"))
    c.stop("output")
    expected = "translated 1 2 3 4 5 6 translated 7 8"
    assert c.window.pages["output"].translations.toPlainText() == expected
    assert c.overlay.translation.toPlainText() == expected
    rows = c.store.list_history()
    assert len(rows) == 1
    assert rows[0]["translated_text"] == expected
    assert rows[0]["source_text"] == "1 2 3 4 5 6 7 8"


@pytest.mark.parametrize("view", ["main", "floating"])
def test_clear_google_captions_starts_a_fresh_anchor_without_stopping_capture(
    controller, qtbot, monkeypatch, view,
):
    c = controller
    google_settings(c)
    monkeypatch.setattr("lang_handler.pipeline.GoogleService", Google)
    c.start("output", True)
    c.pipeline.enqueue("output", b"first", c.settings, c.key)
    qtbot.waitUntil(lambda: not c.pipeline_busy("output"))
    page = c.window.pages["output"]
    target = page if view == "main" else c.overlay
    target.clear_button.click()
    assert c.captures["output"].is_running
    c.pipeline.enqueue("output", b"second", c.settings, c.key)
    qtbot.waitUntil(lambda: not c.pipeline_busy("output"))
    cleared_translation = page.translations if view == "main" else c.overlay.translation
    assert cleared_translation.toPlainText() == "translated second"
    assert page.results.toPlainText() == "second"
    assert c.overlay.transcript.toPlainText() == "second"
    assert page.translations.toPlainText() == "translated second"
    assert c.overlay.translation.toPlainText() == "translated second"
    saved = c.store.list_history()
    assert len(saved) == 1
    assert saved[0]["source_text"] == "first second"
    assert saved[0]["translated_text"] == "translated first translated second"
    c.stop("output")


def test_file_translation_uses_same_google_batch_contract(controller, qtbot, monkeypatch):
    c = controller
    google_settings(c)
    monkeypatch.setattr("lang_handler.file_import.GoogleService", Google)
    monkeypatch.setattr("lang_handler.file_import.audio_file_chunks", lambda *a: iter([b"one", b"two"]))
    c.workflows.import_file("output", "synthetic.wav", True)
    qtbot.waitUntil(lambda: not c.workflows.imports)
    assert c.store.list_history()[0]["translated_text"] == "translated one two"
    assert c.window.pages["output"].translations.toPlainText() == "translated one two"


def test_provider_change_during_translation_does_not_display_old_result(controller, qtbot, monkeypatch):
    started, release = threading.Event(), threading.Event()

    class Slow(Google):
        def translate(self, *args):
            started.set()
            assert release.wait(3)
            return TranslationResult("outdated")

    c = controller
    google_settings(c)
    monkeypatch.setattr("lang_handler.workflows.GoogleService", Slow)
    c.window.set_source_text("translate", "hello")
    try:
        c.workflows.translate("hello")
        qtbot.waitUntil(started.is_set)
        c.save_settings(replace(c.settings, translation_provider="openai"))
        release.set()
        qtbot.waitUntil(lambda: c.workflows.translation_job is None)
        assert c.window.pages["translate"].result.text.toPlainText() == ""
        assert c.store.list_history()[0]["translated_text"] == "outdated"
    finally:
        release.set()
