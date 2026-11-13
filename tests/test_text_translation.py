"""Real Qt workers keep one active translation and only the newest queued edit."""

import threading
from dataclasses import replace

import pytest

from lang_handler.errors import ServiceError
from lang_handler.results import TranslationResult

pytest_plugins = ("test_controller",)


def google_settings(controller, *, automatic=False):
    controller.save_settings(replace(controller.settings, translation_provider="google",
                                     translation_auto_send=automatic, translation_debounce_ms=1000))
    controller.key = ""
    controller.window.show_page("translate")


def editor(controller, text):
    controller.window.set_source_text("translate", text)


def controlled_google(monkeypatch, *, fail_first=False):
    started, release = threading.Event(), threading.Event()
    state = {"calls": [], "active": 0, "maximum": 0, "closed": 0}
    lock = threading.Lock()

    class Service:
        def __init__(self, **kwargs):
            pass

        def translate(self, text, target):
            with lock:
                state["calls"].append((text, target))
                state["active"] += 1
                state["maximum"] = max(state["maximum"], state["active"])
                first = len(state["calls"]) == 1
            try:
                if first:
                    started.set()
                    assert release.wait(4)
                    if fail_first:
                        raise ServiceError("Outdated request failed")
                return TranslationResult("translated " + text)
            finally:
                with lock:
                    state["active"] -= 1

        def close(self):
            state["closed"] += 1

    monkeypatch.setattr("lang_handler.text_translation.GoogleService", Service)
    return started, release, state


@pytest.mark.parametrize("fail_first", [False, True])
def test_only_latest_pending_edit_runs_and_stale_result_or_failure_stays_offscreen(
    controller, qtbot, monkeypatch, fail_first
):
    c = controller
    google_settings(c)
    started, release, state = controlled_google(monkeypatch, fail_first=fail_first)
    errors, statuses = [], []
    monkeypatch.setattr(c, "fail", errors.append)
    monkeypatch.setattr(c, "status", statuses.append)
    editor(c, "first")
    c.workflows.translate("first")
    try:
        qtbot.waitUntil(started.is_set)
        assert c.window.pages["translate"].run.isEnabled()
        for text in ("second", "third", "latest", "latest"):
            editor(c, text)
            c.workflows.translate(text)
        assert c.workflows.translation.pending.text == "latest"
        assert c.workflows.translation_job is not None
        release.set()
        qtbot.waitUntil(lambda: c.workflows.translation_job is None)
        assert state["calls"] == [("first", "English"), ("latest", "English")]
        assert state["maximum"] == 1 and state["closed"] == 2
        assert c.window.pages["translate"].result.text.toPlainText() == "translated latest"
        assert not errors
        assert statuses == ["Translating…", "Translating…", "Translation ready."]
        sources = {row["source_text"] for row in c.store.list_history()}
        assert sources == ({"latest"} if fail_first else {"first", "latest"})
    finally:
        release.set()


def test_blank_edit_discards_pending_without_aborting_active_http(controller, qtbot, monkeypatch):
    c = controller
    google_settings(c)
    started, release, state = controlled_google(monkeypatch)
    editor(c, "running")
    c.workflows.translate("running")
    try:
        qtbot.waitUntil(started.is_set)
        editor(c, "queued")
        c.workflows.translate("queued")
        editor(c, "")
        c.workflows.translate("", automatic=True)
        assert c.workflows.translation.pending is None
        assert not c.workflows.translation_job.cancelled.is_set()
        release.set()
        qtbot.waitUntil(lambda: c.workflows.translation_job is None)
        assert state["calls"] == [("running", "English")]
        assert c.window.pages["translate"].result.text.toPlainText() == ""
        assert c.store.list_history()[0]["source_text"] == "running"
    finally:
        release.set()


def test_returning_to_active_text_reuses_request_and_replaces_other_pending_edit(
    controller, qtbot, monkeypatch
):
    c = controller
    google_settings(c)
    started, release, state = controlled_google(monkeypatch)
    editor(c, "same")
    c.workflows.translate("same")
    try:
        qtbot.waitUntil(started.is_set)
        editor(c, "abandoned")
        c.workflows.translate("abandoned")
        editor(c, "same")
        c.workflows.translate("same")
        assert c.workflows.translation.pending is None
        release.set()
        qtbot.waitUntil(lambda: c.workflows.translation_job is None)
        assert state["calls"] == [("same", "English")]
        assert c.window.pages["translate"].result.text.toPlainText() == "translated same"
    finally:
        release.set()


def test_manual_request_stops_trailing_auto_and_completed_auto_is_deduplicated(
    controller, qtbot, monkeypatch
):
    c = controller
    google_settings(c, automatic=True)
    started, release, state = controlled_google(monkeypatch)
    editor(c, "one request")
    c.workflows.translate("one request")
    try:
        qtbot.waitUntil(started.is_set)
        c.workflows.translate("one request", automatic=True)
        release.set()
        qtbot.waitUntil(lambda: c.workflows.translation_job is None)
        qtbot.wait(1100)
        c.workflows.translate("one request", automatic=True)
        assert len(state["calls"]) == 1
        assert len(c.store.list_history()) == 1
        # Explicit manual regeneration still works after a completed translation.
        c.workflows.translate("one request")
        qtbot.waitUntil(lambda: c.workflows.translation_job is None)
        assert len(state["calls"]) == 2
    finally:
        release.set()


def test_automatic_translation_is_quiet_and_never_requests_openai_key_for_google(
    controller, qtbot, monkeypatch
):
    c = controller
    google_settings(c, automatic=True)
    started, release, state = controlled_google(monkeypatch)
    statuses = []
    monkeypatch.setattr(c, "status", statuses.append)
    monkeypatch.setattr(c, "require_key", lambda: pytest.fail("Google must not request a key"))
    editor(c, "automatic")
    c.workflows.translate("automatic", automatic=True)
    try:
        qtbot.waitUntil(started.is_set)
        release.set()
        qtbot.waitUntil(lambda: c.workflows.translation_job is None)
        assert state["calls"] == [("automatic", "English")]
        assert not statuses
        assert c.window.pages["translate"].result.text.toPlainText() == "translated automatic"
    finally:
        release.set()


def test_editor_debounce_reaches_google_worker_and_history_without_a_key(controller, qtbot, monkeypatch):
    c = controller
    google_settings(c, automatic=True)
    started, release, state = controlled_google(monkeypatch)
    release.set()
    monkeypatch.setattr(c, "require_key", lambda: pytest.fail("Automatic Google needs no key"))
    page = c.window.pages["translate"]
    page.source.text.setPlainText("first draft")
    qtbot.wait(200)
    assert not started.is_set()
    page.source.text.setPlainText("final draft")
    qtbot.waitUntil(lambda: page.result.text.toPlainText() == "translated final draft", timeout=2500)
    qtbot.waitUntil(lambda: c.workflows.translation_job is None)
    assert state["calls"] == [("final draft", "English")]
    row = c.store.list_history()[0]
    assert row["source_text"] == "final draft"
    assert row["translated_text"] == "translated final draft"
    assert row["model"] == "google-translate"


def test_automatic_missing_key_does_not_navigate_or_repeat_manual_key_prompt(controller, monkeypatch):
    c = controller
    c.save_settings(replace(c.settings, translation_provider="openai", translation_auto_send=True))
    c.key = ""
    c.window.show_page("translate")
    errors = []
    monkeypatch.setattr(c, "fail", errors.append)
    editor(c, "text")
    for _ in range(3):
        c.workflows.translate("text", automatic=True)
    assert c.workflows.translation_job is None
    assert c.window.stack.currentWidget() is c.window.pages["translate"]
    assert not errors
    c.workflows.translate("text")
    assert len(errors) == 1 and "API key" in errors[0]
    assert c.window.stack.currentWidget() is c.window.pages["preferences"]


def test_relevant_settings_are_frozen_for_active_request_and_used_by_latest_pending(
    controller, qtbot, monkeypatch
):
    c = controller
    started, release = threading.Event(), threading.Event()
    calls = []

    class Service:
        def __init__(self, key, **options):
            self.key, self.proxy = key, options.get("proxy")

        def translate(self, text, model, target, instructions, reasoning):
            calls.append((self.key, self.proxy, model, target, instructions, reasoning))
            if len(calls) == 1:
                started.set()
                assert release.wait(4)
            return TranslationResult(instructions or "initial")

        def close(self):
            pass

    monkeypatch.setattr("lang_handler.text_translation.OpenAIService", Service)
    editor(c, "source")
    original = c.settings
    c.workflows.translate("source")
    try:
        qtbot.waitUntil(started.is_set)
        c.key = "replacement-test-key"
        c.save_settings(replace(c.settings, target_language="Japanese", translation_model="new-model",
                                translation_reasoning="high", translation_instructions="new style",
                                api_proxy_url="http://localhost:9000"))
        c.workflows.translate("source")
        release.set()
        qtbot.waitUntil(lambda: c.workflows.translation_job is None)
        assert calls[0] == ("test-key", None, original.translation_model, original.target_language,
                            original.translation_instructions, original.translation_reasoning)
        assert calls[1] == ("replacement-test-key", "http://localhost:9000", "new-model",
                            "Japanese", "new style", "high")
        assert c.window.pages["translate"].result.text.toPlainText() == "new style"
    finally:
        release.set()
