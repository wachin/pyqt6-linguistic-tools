from __future__ import annotations

import os
from pathlib import Path

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6", reason="PyQt6 is an optional dependency")

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication, QMenu, QTextEdit

from pyqt6_linguistic_tools import (
    DictionaryInfo,
    DictionaryRegistry,
    DictionarySourcePriority,
    DirectoryDictionaryProvider,
    LinguisticService,
    PersonalDictionaryStore,
)
from pyqt6_linguistic_tools.qt import (
    LinguisticTextEditDecorator,
    QtLanguageSettingsStore,
    QtLinguisticSettings,
)


@pytest.fixture(scope="module")
def application():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def service(tmp_path):
    dictionaries = tmp_path / "dictionaries"
    dictionaries.mkdir()
    registry = DictionaryRegistry(
        (
            DirectoryDictionaryProvider(
                dictionaries,
                source="test",
                priority=DictionarySourcePriority.MANAGED,
            ),
        )
    )
    return LinguisticService(
        "en_US",
        registry=registry,
        personal_store=PersonalDictionaryStore(tmp_path / "personal"),
    )


def _integration(editor, service, **kwargs):
    return LinguisticTextEditDecorator(
        editor,
        service,
        settings=QtLinguisticSettings(highlighting_enabled=False),
        **kwargs,
    )


def test_editors_keep_independent_languages_and_pass_them_to_core(
    application, service, monkeypatch
):
    checked: list[str] = []

    def check_word(_word, *, locale=None):
        checked.append(locale)
        return True

    monkeypatch.setattr(service, "check_word", check_word)
    first = _integration(QTextEdit("word"), service, language="es_ES")
    second = _integration(QTextEdit("word"), service, language="de_DE")

    assert first.check_word_at_cursor()
    assert second.check_word_at_cursor()
    for locale in ("de_DE", "ru_RU", "fr_FR", "es_ES"):
        assert first.set_language(locale)
        assert first.highlighter.language == locale
        assert first.check_word_at_cursor()

    assert checked == ["es_ES", "de_DE", "de_DE", "ru_RU", "fr_FR", "es_ES"]
    assert second.language == "de_DE"
    assert service.language == "en_US"


def test_qsettings_remembers_default_and_per_document_language(
    application, service, tmp_path
):
    path = tmp_path / "languages.ini"
    store = QtLanguageSettingsStore(
        QSettings(str(path), QSettings.Format.IniFormat)
    )
    assert store.set_default_language("es-EC")
    assert store.set_document_language("songs/set 1.chord", "pt-BR")

    default_editor = _integration(QTextEdit(), service, language_settings=store)
    document_editor = _integration(
        QTextEdit(),
        service,
        language_settings=store,
        document_key="songs/set 1.chord",
    )

    assert default_editor.language == "es_EC"
    assert document_editor.language == "pt_BR"
    assert document_editor.set_language("es-ES")

    reloaded = QtLanguageSettingsStore(
        QSettings(str(path), QSettings.Format.IniFormat)
    )
    assert reloaded.default_language() == "es_EC"
    assert reloaded.document_language("songs/set 1.chord") == "es_ES"
    assert reloaded.clear_document_language("songs/set 1.chord")
    assert reloaded.document_language("songs/set 1.chord", "es_EC") == "es_EC"


def test_language_menu_shows_exact_variants_and_dictionary_availability(
    application, service, tmp_path, monkeypatch
):
    locales = ("es_EC", "pt_BR", "pt_PT", "zh_Hant_TW")
    monkeypatch.setattr(service, "available_languages", lambda: locales)

    def dictionary_info(locale):
        spelling = locale in {"es_EC", "pt_BR"}
        thesaurus = locale in {"es_EC", "pt_PT"}
        return DictionaryInfo(
            locale=locale,
            display_name=locale,
            aff_path=Path("dictionary.aff") if spelling else None,
            dic_path=Path("dictionary.dic") if spelling else None,
            thesaurus_dat=Path("thesaurus.dat") if thesaurus else None,
        )

    monkeypatch.setattr(service, "dictionary_info", dictionary_info)
    store = QtLanguageSettingsStore(
        QSettings(str(tmp_path / "menu.ini"), QSettings.Format.IniFormat)
    )
    integration = _integration(
        QTextEdit(), service, language="es_EC", language_settings=store
    )
    menu = QMenu()

    assert integration.context_menu.populate_menu(menu, integration.editor.textCursor())
    language_menu = next(action.menu() for action in menu.actions() if action.menu())
    texts = [action.text() for action in language_menu.actions()]

    assert any(
        "[es_EC]" in text and "Spelling" in text and "Thesaurus" in text
        for text in texts
    )
    assert any("[pt_BR]" in text and "Spelling" in text for text in texts)
    assert any("[pt_PT]" in text and "Thesaurus" in text for text in texts)
    assert any("[zh_Hant_TW]" in text and "No dictionaries" in text for text in texts)
    assert "Set Current Language as Default" in texts
