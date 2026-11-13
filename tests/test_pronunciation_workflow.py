"""Pronunciation guides stay paired with their originals across every translation path."""

from lang_handler.results import TranslationResult

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
    page = c.window.pages["output"]
    for source in (page.results, c.overlay.transcript):
        assert [row.text for row in source.entries] == ["first", "second"]
        assert [row.pronunciation for row in source.entries] == ["source reading"] * 2
    for target in (page.translations, c.overlay.translation):
        assert [row.text for row in target.entries] == ["translation: first", "translation: second"]
        assert [row.pronunciation for row in target.entries] == ["target reading"] * 2
    assert all(row["source_pronunciation"] == "source reading" for row in c.store.list_history())


def test_file_import_keeps_both_pronunciations(controller, qtbot, monkeypatch):
    monkeypatch.setattr("lang_handler.workflows.audio_file_chunks", lambda *args: iter([b"file"]))
    c = controller
    c.workflows.import_file("output", "synthetic.wav", True)
    qtbot.waitUntil(lambda: not c.workflows.imports)
    row = c.store.list_history()[0]
    assert row["source_text"] == "file"
    assert row["translated_text"] == "translation: file"
    assert row["source_pronunciation"] == "source reading"
    assert c.overlay.transcript.entries[0].pronunciation == "source reading"
    assert c.overlay.translation.entries[0].pronunciation == "target reading"


def test_repeated_phrases_and_clear_cannot_receive_another_chunks_guide(controller):
    c = controller
    result = TranslationResult("bridge", "hashi", "/brɪdʒ/")
    c._transcript("output", "はし", 10)
    c._transcript("output", "はし", 11)
    c._translation("output", 11, result)
    for pane in (c.window.pages["output"].results, c.overlay.transcript):
        assert [row.pronunciation for row in pane.entries] == ["", "hashi"]
    c.window.pages["output"].clear()
    c.overlay.clear()
    c._transcript("output", "はし", 12)
    c._translation("output", 10, result)
    for pane in (c.window.pages["output"].results, c.overlay.transcript):
        assert pane.entries[0].pronunciation == ""
    assert c.window.pages["output"].translations.entries == []
    assert c.overlay.translation.entries == []
