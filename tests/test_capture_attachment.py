"""The attachment control routes selected media through the existing import workflow."""

import pytest

pytest_plugins = ("test_controller",)


@pytest.mark.parametrize("mode,chunked", [("input", False), ("output", True)])
def test_attachment_import_reaches_correct_page_and_history(controller, qtbot, monkeypatch, mode, chunked):
    c = controller
    page = c.window.pages[mode]
    decoded = []

    def chunks(path, seconds):
        decoded.append((str(path), seconds))
        yield b"attached audio"

    monkeypatch.setattr("lang_handler.file_import.audio_file_chunks", chunks)
    monkeypatch.setattr("lang_handler.ui.capture_page.QFileDialog.getOpenFileName",
                        lambda *args: ("/tmp/selected-media.mp4", ""))
    page.attach_button.click()
    assert mode in c.workflows.imports
    assert not page.attach_button.isEnabled()
    qtbot.waitUntil(lambda: not c.workflows.imports)
    expected_seconds = getattr(c.settings, f"{mode}_chunk_seconds") if chunked else None
    assert decoded == [("/tmp/selected-media.mp4", expected_seconds)]
    assert page.results.toPlainText() == "attached audio"
    assert page.attach_button.isEnabled()
    row = c.store.list_history()[0]
    assert row["mode"] == mode
    assert row["source_text"] == "attached audio"
    if mode == "output":
        assert row["translated_text"] == "translation: attached audio"


@pytest.mark.parametrize("started_during_picker", [False, True])
def test_cancel_or_capture_start_in_picker_never_submits_file(controller, monkeypatch, started_during_picker):
    c = controller
    page = c.window.pages["input"]
    c.key = ""

    def choose(*args):
        if started_during_picker:
            page.set_capture_state("recording")
            return "/tmp/selected.wav", ""
        return "", ""

    monkeypatch.setattr("lang_handler.ui.capture_page.QFileDialog.getOpenFileName", choose)
    monkeypatch.setattr(c, "require_key", lambda: pytest.fail("No import should request a key"))
    page.attach_button.click()
    assert not c.workflows.imports
    assert not c.jobs.active
