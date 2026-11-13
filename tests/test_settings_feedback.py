"""Save acknowledgments follow persistence; failures retain drafts and committed runtime state."""

import sqlite3
from copy import deepcopy
from dataclasses import replace

import pytest
from PySide6.QtTest import QSignalSpy

from lang_handler.settings import Settings
from lang_handler.ui.main_window import MainWindow

pytest_plugins = ("test_controller",)


def editor_for(c, scope):
    if scope == "global":
        return c.window.pages["preferences"], "voice", "cedar"
    return c.window.pages["translate"].tool_settings, "target_language", "Russian"


@pytest.mark.parametrize("scope", ["tool", "global"])
def test_saved_feedback_is_shown_only_after_settings_reach_storage(controller, monkeypatch, scope):
    c = controller
    c.applied_shortcuts = deepcopy(c.settings.shortcuts)
    editor, key, value = editor_for(c, scope)
    previous = getattr(c.settings, key)
    getattr(editor, key).setCurrentText(value)
    original_save = c.store.save_settings
    events = []

    def persist(settings):
        assert editor.save_hint.text() != "Saved"
        assert getattr(c.settings, key) == previous
        assert getattr(c.window.settings, key) == previous
        assert editor.fields.committed[key] == previous
        original_save(settings)
        events.append("persisted")

    monkeypatch.setattr(c.store, "save_settings", persist)
    (editor.save_preferences if scope == "global" else editor.save_button).click()
    assert events == ["persisted"]
    assert getattr(c.store.load_settings(), key) == value
    assert editor.save_hint.text() == "Saved"
    assert c.window.status.text() == "Settings saved."
    assert not editor.fields.has_pending
    getattr(editor, key).setCurrentText(previous)
    assert editor.save_hint.text() == "Unsaved changes"


@pytest.mark.parametrize("scope", ["tool", "global"])
def test_failed_save_keeps_draft_and_previous_runtime_settings_until_retry(controller, monkeypatch, scope):
    c = controller
    editor, key, value = editor_for(c, scope)
    before = deepcopy(c.settings)
    original_save = c.store.save_settings
    getattr(editor, key).setCurrentText(value)

    def fail(settings):
        raise sqlite3.OperationalError("database is read-only")

    monkeypatch.setattr(c.store, "save_settings", fail)
    action = editor.save_preferences if scope == "global" else editor.save_button
    action.click()
    assert c.settings == c.window.settings == c.store.load_settings() == before
    assert getattr(editor, key).currentText() == value
    assert editor.fields.has_pending
    assert editor.save_hint.text() == "Not saved. Your changes are kept."
    assert c.window.status.property("error")
    monkeypatch.setattr(c.store, "save_settings", original_save)
    action.click()
    assert getattr(c.store.load_settings(), key) == value
    assert editor.save_hint.text() == "Saved"


def test_quick_changes_stay_silent_and_failed_changes_restore_selection_without_losing_drafts(
    controller, monkeypatch,
):
    c = controller
    c.applied_shortcuts = deepcopy(c.settings.shortcuts)
    page = c.window.pages["output"]
    editor = page.tool_settings
    editor.instructions["output_instructions"].setPlainText("Unsaved vocabulary")
    c.window.set_status("")
    page.target.setCurrentText("Russian")
    assert c.settings.target_language == "Russian"
    assert c.window.status.text() == ""
    assert editor.save_hint.text() != "Saved"

    def fail(settings):
        raise OSError("Disk full")

    monkeypatch.setattr(c.store, "save_settings", fail)
    page.source_language.setCurrentText("English")
    assert page.source_language.currentData() == c.settings.output_language == "ja"
    assert editor.instructions["output_instructions"].toPlainText() == "Unsaved vocabulary"
    assert editor.fields.has_pending


def test_reset_all_failure_remains_staged_and_retry_commits_all_sections(controller, monkeypatch):
    c = controller
    c.save_settings(replace(c.settings, voice="cedar", drawing_pen_width=8))
    preferences = c.window.pages["preferences"]
    original_save = c.store.save_settings
    preferences.reset_all_button.click()

    def fail(settings):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(c.store, "save_settings", fail)
    preferences.save_preferences.click()
    assert c.window._reset_all_pending
    assert c.settings.voice == "cedar"
    assert c.settings.drawing_pen_width == 8
    assert c.window.pages["drawing"].tool_settings.collect()["drawing_pen_width"] == 4
    monkeypatch.setattr(c.store, "save_settings", original_save)
    preferences.save_preferences.click()
    assert c.settings == Settings()
    assert not c.window._reset_all_pending
    assert preferences.save_hint.text() == "Saved"


def test_save_request_without_persistence_acknowledgment_is_not_reported_saved(qtbot):
    window = MainWindow(Settings(), True)
    qtbot.addWidget(window)
    editor = window.pages["translate"].tool_settings
    requested = QSignalSpy(window.settings_saved)
    editor.target_language.setCurrentText("Russian")
    editor.save_button.click()
    assert requested.count() == 1
    assert window.settings.target_language == "English"
    assert editor.fields.committed["target_language"] == "English"
    assert editor.save_hint.text() == "Unsaved changes"
