import threading

pytest_plugins = ("test_controller",)


def test_pasted_key_and_proxy_are_used_by_connection_test(controller, qtbot, monkeypatch):
    c = controller
    calls = []
    saved = []
    monkeypatch.setattr(c.credentials, "set", saved.append, raising=False)

    class Service:
        def __init__(self, key, *, proxy=None):
            calls.append((key, proxy))

        def list_models(self):
            return ["gpt-transcribe"]

        def close(self):
            pass

    monkeypatch.setattr("lang_handler.controller.OpenAIService", Service)
    preferences = c.window.pages["preferences"]
    preferences.api_key.setText("fresh-test-key")
    preferences.api_proxy_url.setText("http://127.0.0.1:7897")
    c.test_key("fresh-test-key")
    qtbot.waitUntil(lambda: "accepted" in c.window.status.text())
    assert calls == [("fresh-test-key", "http://127.0.0.1:7897")]
    assert saved == ["fresh-test-key"]
    assert c.key == "fresh-test-key"
    assert preferences.api_key.text() == ""
    assert c.store.load_settings().api_proxy_url == "http://127.0.0.1:7897"


def test_failed_key_storage_keeps_candidate_and_does_not_test_old_key(controller, monkeypatch):
    c = controller
    c.window.pages["preferences"].api_key.setText("fresh-test-key")

    def denied(key):
        raise RuntimeError("Credential storage is locked.")

    monkeypatch.setattr(c.credentials, "set", denied, raising=False)
    monkeypatch.setattr(c.jobs, "submit", lambda *a, **kw: (_ for _ in ()).throw(
        AssertionError("Must not test the old key after a failed replacement")))
    c.test_key("fresh-test-key")
    assert c.key == "test-key"
    assert c.window.pages["preferences"].api_key.text() == "fresh-test-key"
    assert "locked" in c.window.status.text()


def test_stale_key_failure_cannot_overwrite_new_connection(controller, qtbot, monkeypatch):
    c = controller
    started, release = threading.Event(), threading.Event()

    class Service:
        def __init__(self, key, *, proxy=None):
            pass

        def list_models(self):
            started.set()
            assert release.wait(3)
            raise RuntimeError("Old credential failed")

        def close(self):
            pass

    monkeypatch.setattr("lang_handler.controller.OpenAIService", Service)
    c.test_key()
    try:
        qtbot.waitUntil(started.is_set)
        c.key = "replacement-test-key"
        c.status("New key saved.")
        release.set()
        qtbot.waitUntil(lambda: not c.jobs.active)
        assert c.window.status.text() == "New key saved."
    finally:
        release.set()
