"""Pronunciation guides stay paired with their originals across every translation path."""

from lang_handler.results import CaptionRevision, TranslationResult

pytest_plugins = ("test_controller",)


def test_translation_displays_and_persists_both_guides(controller, qtbot):
    c = controller
    c.window.set_source_text("translate", "日本語")
    c.workflows.translate("日本語")
    qtbot.waitUntil(lambda: c.workflows.translation_job is None)
    page = c.window.pages["translate"]
    assert page.result.text.toPlainText() == "translation: 日本語"
    assert page.source.pronunciation.text.toPlainText() == "source reading"
    assert page.result.pronunciation.text.toPlainText() == "target reading"
    row = c.store.list_history()[0]
    assert row["source_pronunciation"] == "source reading"
    assert row["translation_pronunciation"] == "target reading"
    c.window.pages["history"].table.selectRow(0)
    assert c.window.pages["history"].detail.pronunciation.text.toPlainText() == "source reading"
    page.source.text.setPlainText("new original")
    assert page.source.pronunciation.isHidden()
    c.window.set_translation(TranslationResult("old translation", "stale reading", "target"), "日本語")
    assert page.source.pronunciation.isHidden()
    assert page.result.text.toPlainText() == "translation: 日本語"
    page.source.text.setPlainText("日本語")
    page.target.setCurrentText("Japanese")
    assert not c.window.set_translation(TranslationResult("wrong target", "source", "target"), "日本語", "English")
    assert page.result.text.toPlainText() == "translation: 日本語"


def test_live_pronunciation_attaches_to_correct_chunk(controller, qtbot):
    c = controller
    for audio in (b"first", b"second"):
        c.pipeline.enqueue("output", audio, c.settings, c.key)
    qtbot.waitUntil(lambda: len(c.store.list_history()) == 2)
    qtbot.waitUntil(lambda: not c.pipeline_busy("output"))
    page = c.window.pages["output"]
    for source in (page.results, c.overlay.transcript):
        assert source.toPlainText() == "first second"
        assert source.pronunciation.text.toPlainText() == "source reading source reading"
    for target in (page.translations, c.overlay.translation):
        assert target.toPlainText() == "translation: first translation: second"
        assert target.pronunciation.text.toPlainText() == "target reading target reading"
    assert all(row["source_pronunciation"] == "source reading" for row in c.store.list_history())


def test_file_import_keeps_both_pronunciations(controller, qtbot, monkeypatch):
    monkeypatch.setattr("lang_handler.file_import.audio_file_chunks", lambda *args: iter([b"file"]))
    c = controller
    c.workflows.import_file("output", "synthetic.wav", True)
    qtbot.waitUntil(lambda: not c.workflows.imports)
    row = c.store.list_history()[0]
    assert row["source_text"] == "file"
    assert row["translated_text"] == "translation: file"
    assert row["source_pronunciation"] == "source reading"
    assert c.overlay.transcript.pronunciation.text.toPlainText() == "source reading"
    assert c.overlay.translation.pronunciation.text.toPlainText() == "target reading"


def test_repeated_phrases_and_clear_cannot_receive_another_chunks_guide(controller):
    c = controller
    result = TranslationResult("bridge", "hashi", "/brɪdʒ/")
    c._transcript("output", "はし", 10)
    c._transcript("output", "はし", 11)
    c._revisions([CaptionRevision(11, "はし", result)])
    for pane in (c.window.pages["output"].results, c.overlay.transcript):
        assert pane.pronunciation.text.toPlainText() == "hashi"
        assert pane.toPlainText() == "はしはし"
    c.window.pages["output"].clear()
    c.overlay.clear()
    c._transcript("output", "はし", 12)
    c._revisions([CaptionRevision(10, "はし", result)])
    for pane in (c.window.pages["output"].results, c.overlay.transcript):
        assert pane.pronunciation.text.toPlainText() == ""
    assert c.window.pages["output"].translations.toPlainText() == ""
    assert c.overlay.translation.toPlainText() == ""
