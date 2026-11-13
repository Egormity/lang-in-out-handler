"""Language headings are selectable and share the saved language preferences."""

from dataclasses import replace

from PySide6.QtCore import QPoint
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QComboBox

from lang_handler.settings import Settings
from lang_handler.storage import Store
from lang_handler.ui.capture_page import CapturePage
from lang_handler.ui.history import HistoryPage
from lang_handler.ui.main_window import MainWindow
from lang_handler.ui.preferences import PreferencesPage
from lang_handler.ui.text_pages import TranslatePage
from lang_handler.ui.theme import STYLE


def test_caption_language_controls_replace_headings_and_stay_compact(qtbot):
    page = CapturePage("output", Settings())
    qtbot.addWidget(page)
    page.setStyleSheet(STYLE)
    page.resize(650, 580)
    page.show()
    qtbot.wait(20)
    visible = [combo for combo in page.findChildren(QComboBox) if combo.isVisible()]
    assert set(visible) == {page.source_language, page.target}
    assert page.source_language.parentWidget() is page.results
    assert page.target.parentWidget() is page.translations
    assert page.results.heading.isHidden()
    assert page.translations.heading.isHidden()
    for selector in visible:
        assert not selector.isEditable()
        assert selector.width() <= 180
        selector.showPopup()
        qtbot.wait(10)
        assert selector.view().window().width() <= 360
        assert selector.view().window().height() < 400
        selector.hidePopup()
    assert page.source_language.itemText(0) == "Auto detect"
    assert page.target.findText("Auto detect") < 0
    assert [page.source_language.itemText(i) for i in range(1, page.source_language.count())] == [
        page.target.itemText(i) for i in range(page.target.count())
    ]
    assert page.start_button.mapTo(page, QPoint()).y() < page.splitter.y()
    assert page.import_button.mapTo(page, QPoint()).y() < page.splitter.y()


def test_header_choices_save_scoped_changes_and_reload_across_pages(qtbot, tmp_path):
    store = Store(tmp_path)
    window = MainWindow(Settings(), True)
    qtbot.addWidget(window)
    window.settings_saved.connect(store.save_settings)
    captions = window.pages["output"]
    requested = QSignalSpy(captions.options_changed)
    captions.source_language.setCurrentText("Russian")
    captions.target.setCurrentText("Korean")
    assert requested.count() == 2
    assert requested.at(0) == [{"output_language": "ru"}]
    assert requested.at(1) == [{"target_language": "Korean"}]
    assert window.pages["translate"].target.currentText() == "Korean"
    assert captions.tool_settings.output_language.currentData() == "ru"
    assert captions.tool_settings.target_language.findText("Italian") >= 0
    assert window.pages["translate"].tool_settings.target_language.findText("Italian") >= 0
    assert window.settings.input_language == ""
    saved = store.load_settings()
    store.close()
    reloaded = CapturePage("output", saved)
    qtbot.addWidget(reloaded)
    assert reloaded.source_language.currentData() == "ru"
    assert reloaded.target.currentText() == "Korean"


def test_settings_refresh_does_not_emit_feedback_or_drop_custom_languages(qtbot):
    page = CapturePage("output", Settings())
    qtbot.addWidget(page)
    requested = QSignalSpy(page.options_changed)
    page.apply_settings(replace(Settings(), output_language="zu", target_language="Zulu"))
    assert requested.count() == 0
    assert page.source_language.currentData() == "zu"
    assert page.target.currentText() == "Zulu"
    page.apply_settings(Settings(output_language=""))
    assert requested.count() == 0
    assert page.source_language.currentText() == "Auto detect"


def test_dictation_and_translation_keep_language_choices_in_pane_headers(qtbot):
    dictate = CapturePage("input", Settings())
    translate = TranslatePage(Settings())
    qtbot.addWidget(dictate)
    qtbot.addWidget(translate)
    assert dictate.source_language.parentWidget() is dictate.results
    assert translate.target.parentWidget() is translate.result
    assert dictate.results.heading.isHidden()
    assert translate.result.heading.isHidden()
    assert translate.source.heading.text() == "Original"
    translate.resize(650, 580)
    translate.show()
    qtbot.wait(10)
    assert translate.run.mapTo(translate, QPoint()).y() < translate.splitter.y()
    dictated = QSignalSpy(dictate.options_changed)
    translated = QSignalSpy(translate.options_changed)
    dictate.source_language.setCurrentText("Japanese")
    translate.target.setCurrentText("Italian")
    assert dictated.at(0) == [{"input_language": "ja"}]
    assert translated.at(0) == [{"target_language": "Italian"}]
    dictate.set_recording(True)
    assert not dictate.source_language.isEnabled()
    dictate.set_recording(False)
    assert dictate.source_language.isEnabled()


def test_preferences_and_history_actions_are_above_content(qtbot):
    preferences = PreferencesPage(Settings())
    history = HistoryPage()
    for page in (preferences, history):
        qtbot.addWidget(page)
        page.resize(650, 580)
        page.show()
    qtbot.wait(20)
    for action in (preferences.save_preferences, preferences.reset_all_button):
        assert action.mapTo(preferences, QPoint()).y() < preferences.tabs.y()
    for action in (history.refresh_button, history.delete_button):
        assert action.mapTo(history, QPoint()).y() < history.search.y()
