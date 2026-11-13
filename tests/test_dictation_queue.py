"""Voice delivery remains ordered, focus-safe, and scoped to its recording session."""

import threading

from lang_handler import desktop

pytest_plugins = ("test_controller",)


def external_focus(monkeypatch):
    monkeypatch.setattr("lang_handler.dictation.QApplication.activeWindow", lambda: None)


def idle(controller):
    return not controller.dictation.busy and not controller.dictation.queue


def test_slow_first_delivery_preserves_fifo(controller, qtbot, monkeypatch):
    external_focus(monkeypatch)
    started, release = threading.Event(), threading.Event()
    calls = []

    def deliver(text, mode, **kwargs):
        calls.append((text, mode))
        if text == "first":
            started.set()
            assert release.wait(3)
        return "Pasted into the active app."

    monkeypatch.setattr("lang_handler.dictation.deliver_transcript", deliver)
    controller.dictation.enqueue("first", "copy_and_paste")
    try:
        qtbot.waitUntil(started.is_set)
        controller.dictation.enqueue("second", "copy_and_paste")
        controller.dictation.enqueue("third", "copy_and_paste")
        qtbot.wait(20)
        assert calls == [("first", "copy_and_paste")]
        release.set()
        qtbot.waitUntil(lambda: idle(controller))
        assert calls == [
            ("first", "copy_and_paste"),
            (" second", "copy_and_paste"),
            (" third", "copy_and_paste"),
        ]
    finally:
        release.set()


def test_each_queued_chunk_retains_its_selected_delivery_mode(controller, qtbot, monkeypatch):
    external_focus(monkeypatch)
    calls = []

    def deliver(text, mode, **kwargs):
        calls.append((text, mode, kwargs["allow_paste"]))
        return "Copied." if mode == "copy" else "Pasted into the active app."

    monkeypatch.setattr("lang_handler.dictation.deliver_transcript", deliver)
    for text, mode in [("one", "copy"), ("two", "paste"), ("three", "copy_and_paste")]:
        controller.dictation.enqueue(text, mode)
    qtbot.waitUntil(lambda: idle(controller))
    assert calls == [
        ("one", "copy", True), ("two", "paste", True), (" three", "copy_and_paste", True)
    ]


def test_own_app_focus_blocks_paste_only_without_touching_clipboard(controller, qtbot, monkeypatch):
    monkeypatch.setattr("lang_handler.dictation.QApplication.activeWindow", lambda: controller.window)
    calls = []

    def deliver(text, mode, **kwargs):
        calls.append(kwargs["allow_paste"])
        return desktop.deliver_transcript(text, mode, **kwargs)

    monkeypatch.setattr("lang_handler.dictation.deliver_transcript", deliver)
    monkeypatch.setattr(desktop, "copy_text", lambda *args: (_ for _ in ()).throw(
        AssertionError("Paste-only while app is focused must leave clipboard untouched")))
    monkeypatch.setattr(desktop, "paste_keys", lambda: (_ for _ in ()).throw(
        AssertionError("Must not paste into this app")))
    controller.dictation.enqueue("private sample", "paste")
    qtbot.waitUntil(lambda: idle(controller))
    assert calls == [False]
    assert "clipboard unchanged" in controller.window.status.text()
    assert controller.dictation.last_pasted == ""


def test_focus_is_rechecked_before_a_waiting_chunk_starts(controller, qtbot, monkeypatch):
    focus = [None]
    monkeypatch.setattr("lang_handler.dictation.QApplication.activeWindow", lambda: focus[0])
    started, release = threading.Event(), threading.Event()
    calls = []

    def deliver(text, mode, **kwargs):
        calls.append((text, kwargs["allow_paste"]))
        if text == "first":
            started.set()
            assert release.wait(3)
        return "Pasted." if kwargs["allow_paste"] else "Transcript ready; clipboard unchanged."

    monkeypatch.setattr("lang_handler.dictation.deliver_transcript", deliver)
    controller.dictation.enqueue("first", "paste")
    try:
        qtbot.waitUntil(started.is_set)
        controller.dictation.enqueue("second", "paste")
        focus[0] = controller.window
        release.set()
        qtbot.waitUntil(lambda: idle(controller))
        assert calls == [("first", True), ("second", False)]
    finally:
        release.set()


def test_new_session_does_not_inherit_pending_previous_session_prefix(controller, qtbot, monkeypatch):
    external_focus(monkeypatch)
    started, release = threading.Event(), threading.Event()
    calls = []

    def deliver(text, mode, **kwargs):
        calls.append(text)
        if text == "old session":
            started.set()
            assert release.wait(3)
        return "Pasted into the active app."

    monkeypatch.setattr("lang_handler.dictation.deliver_transcript", deliver)
    controller.dictation.enqueue("old session", "paste")
    try:
        qtbot.waitUntil(started.is_set)
        controller.dictation.reset()
        controller.dictation.enqueue("new session", "paste")
        release.set()
        qtbot.waitUntil(lambda: idle(controller))
        assert calls == ["old session", "new session"]
        assert controller.dictation.last_pasted == "new session"
    finally:
        release.set()


def test_failed_delivery_clears_previous_prefix_before_next_chunk(controller, qtbot, monkeypatch):
    external_focus(monkeypatch)
    calls = []

    def deliver(text, mode, **kwargs):
        calls.append(text)
        if text.strip() == "failed":
            raise RuntimeError("Clipboard unavailable")
        return "Pasted into the active app."

    monkeypatch.setattr("lang_handler.dictation.deliver_transcript", deliver)
    for text in ("first", "failed", "after failure"):
        controller.dictation.enqueue(text, "paste")
    qtbot.waitUntil(lambda: idle(controller))
    assert calls == ["first", " failed", "after failure"]
