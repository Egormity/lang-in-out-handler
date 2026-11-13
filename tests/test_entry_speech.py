"""Per-result speech reaches the shared workflow without losing preference edits."""

import threading

from test_controller import FakeService

from lang_handler.errors import ServiceError

pytest_plugins = ("test_controller",)


def test_every_entry_uses_saved_voice_and_instructions(controller, qtbot, monkeypatch):
    calls = []

    class Service(FakeService):
        def synthesize(self, text, model, voice, instructions):
            calls.append((text, model, voice, instructions))
            return super().synthesize(text)

    monkeypatch.setattr("lang_handler.workflows.OpenAIService", Service)
    c = controller
    preferences = c.window.pages["preferences"]
    preferences.voice.setCurrentText("alloy")
    preferences.instructions["tts_instructions"].setPlainText("Speak slowly.")
    preferences.save_preferences.click()
    c.window.append_result("input", "microphone")
    c.window.append_result("output", "output", "translated output")
    c.overlay.append_caption("floating source", "floating translation")
    drawing = c.window.pages["drawing"]
    drawing.set_result(["first candidate", "second candidate"], drawing.canvas.revision)
    c.window.set_source_text("translate", "original")
    c.window.set_translation("translation")
    buttons = [
        (c.window.pages["input"].results.speak, "microphone"),
        (c.window.pages["output"].results.speak, "output"),
        (c.window.pages["output"].translations.speak, "translated output"),
        (c.overlay.transcript.speak, "floating source"),
        (c.overlay.translation.speak, "floating translation"),
        (drawing.result.rows[1].speak, "second candidate"),
        (c.window.pages["translate"].speak_original, "original"),
        (c.window.pages["translate"].speak_translation, "translation"),
    ]
    # Automatic recognition or Speak must not discard edits waiting for Save.
    preferences.instructions["tts_instructions"].setPlainText("An unsaved draft.")
    for button, text in buttons:
        button.click()
        qtbot.waitUntil(lambda: c.workflows.speech_job is None)
        assert calls[-1] == (text, c.settings.tts_model, "alloy", "Speak slowly.")
        assert preferences.instructions["tts_instructions"].toPlainText() == "An unsaved draft."
    assert len(calls) == len(buttons)
    assert not c.window.speech_controls.isHidden()
    # History selection offers speech too, without combining the two languages.
    c.remember("output", "stored original", "stored translation", "test")
    history = c.window.pages["history"]
    history.table.selectRow(0)
    history.translation.speak.click()
    qtbot.waitUntil(lambda: c.workflows.speech_job is None)
    assert calls[-1][0] == "stored translation"


def test_floating_stop_cancels_pending_speech_without_playback(controller, qtbot, monkeypatch):
    started, release = threading.Event(), threading.Event()

    class Service(FakeService):
        def synthesize(self, text, *args):
            started.set()
            assert release.wait(3)
            return super().synthesize(text)

    monkeypatch.setattr("lang_handler.workflows.OpenAIService", Service)
    c = controller
    c.overlay.append_caption("sample")
    c.overlay.transcript.speak.click()
    try:
        qtbot.waitUntil(started.is_set)
        assert not c.overlay.stop_audio_button.isHidden()
        assert not c.window.pages["drawing"].result.stop.isHidden()
        c.overlay.stop_audio_button.click()
        release.set()
        qtbot.waitUntil(lambda: c.workflows.speech_job is None)
        assert c.overlay.stop_audio_button.isHidden()
        assert not c.window.speech_controls.stop.isEnabled()
        assert c.workflows.player is None
        assert c.workflows.audio_files == []
        assert c.store.list_history() == []
    finally:
        release.set()


def test_speech_failure_resets_all_stop_controls(controller, qtbot, monkeypatch):
    class Service(FakeService):
        def synthesize(self, text, *args):
            raise ServiceError("Speech service unavailable.")

    monkeypatch.setattr("lang_handler.workflows.OpenAIService", Service)
    c = controller
    c.workflows.speak("sample")
    qtbot.waitUntil(lambda: c.workflows.speech_job is None)
    assert c.overlay.stop_audio_button.isHidden()
    assert c.window.pages["drawing"].result.stop.isHidden()
    assert not c.window.speech_controls.stop.isEnabled()
    assert c.window.status.property("error")
    assert "unavailable" in c.window.status.text()
