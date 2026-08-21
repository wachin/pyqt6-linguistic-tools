from __future__ import annotations

import os

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6", reason="PyQt6 is an optional dependency")

from PyQt6.QtWidgets import QApplication, QTextEdit

from pyqt6_linguistic_tools import (
    DictionaryRegistry,
    DictionarySourcePriority,
    DirectoryDictionaryProvider,
    LinguisticService,
    PersonalDictionaryStore,
    ThesaurusEntry,
    ThesaurusMeaning,
)
from pyqt6_linguistic_tools.qt import (
    LinguisticTextEditDecorator,
    QtLinguisticSettings,
    ThesaurusDialog,
    preserve_simple_capitalization,
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


def _entry(word: str, **_kwargs) -> ThesaurusEntry | None:
    entries = {
        "bright": ThesaurusEntry(
            word="bright",
            meanings=(
                ThesaurusMeaning(
                    "adjective",
                    "shining",
                    ("radiant", "luminous"),
                ),
                ThesaurusMeaning(
                    "adjective",
                    "intelligent",
                    ("clever",),
                ),
            ),
        ),
        "radiant": ThesaurusEntry(
            word="radiant",
            meanings=(ThesaurusMeaning("adjective", "bright", ("shining",)),),
        ),
        "Bright": ThesaurusEntry(
            word="Bright",
            meanings=(ThesaurusMeaning("adjective", "shining", ("radiant",)),),
        ),
    }
    return entries.get(word)


def test_displays_query_meanings_parts_of_speech_and_synonyms(
    application, service, monkeypatch
):
    monkeypatch.setattr(service, "thesaurus_entry", _entry)
    dialog = ThesaurusDialog(service, "bright")

    assert dialog.query == "bright"
    assert dialog.entry.word == "bright"
    assert dialog.results.topLevelItemCount() == 2
    first = dialog.results.topLevelItem(0)
    assert first.text(0) == "adjective"
    assert first.text(1) == "shining"
    assert [first.child(index).text(1) for index in range(first.childCount())] == [
        "radiant",
        "luminous",
    ]


def test_selects_and_searches_synonyms_with_back_forward_history(
    application, service, monkeypatch
):
    monkeypatch.setattr(service, "thesaurus_entry", _entry)
    dialog = ThesaurusDialog(service, "bright")
    radiant = dialog.results.topLevelItem(0).child(0)
    dialog.results.setCurrentItem(radiant)

    assert dialog.selected_synonym == "radiant"
    assert dialog.search_selected()
    assert dialog.query == "radiant"
    assert dialog.history == ("bright", "radiant")
    assert dialog.back_button.isEnabled()
    assert dialog.go_back()
    assert dialog.query == "bright"
    assert dialog.forward_button.isEnabled()
    assert dialog.go_forward()
    assert dialog.query == "radiant"


def test_new_search_after_back_discards_forward_history(
    application, service, monkeypatch
):
    monkeypatch.setattr(service, "thesaurus_entry", _entry)
    dialog = ThesaurusDialog(service, "bright")
    assert dialog.search("radiant")
    assert dialog.go_back()

    assert not dialog.search("missing")

    assert dialog.history == ("bright", "missing")
    assert not dialog.go_forward()


def test_no_result_state_is_explicit(application, service, monkeypatch):
    monkeypatch.setattr(service, "thesaurus_entry", lambda _word, **_kwargs: None)
    missing: list[str] = []
    dialog = ThesaurusDialog(service, "unknown")
    dialog.no_results.connect(missing.append)

    assert dialog.entry is None
    assert dialog.results.topLevelItemCount() == 0
    assert "unknown" in dialog.status_label.text()
    assert not dialog.replace_button.isEnabled()
    assert not dialog.search_selected_button.isEnabled()
    assert not dialog.replace_selected()


@pytest.mark.parametrize(
    ("source", "replacement", "expected"),
    [
        ("word", "synonym", "synonym"),
        ("Word", "synonym", "Synonym"),
        ("WORD", "two words", "TWO WORDS"),
        ("wOrd", "synonym", "synonym"),
        ("Word", "iPhone", "iPhone"),
    ],
)
def test_preserves_only_safe_simple_capitalization(source, replacement, expected):
    assert preserve_simple_capitalization(source, replacement) == expected


def test_replace_signal_keeps_original_source_after_navigation(
    application, service, monkeypatch
):
    monkeypatch.setattr(service, "thesaurus_entry", _entry)
    dialog = ThesaurusDialog(service, "bright", replacement_source="Bright")
    radiant = dialog.results.topLevelItem(0).child(0)
    dialog.results.setCurrentItem(radiant)
    replacements: list[tuple[str, str]] = []
    dialog.replacement_requested.connect(
        lambda source, replacement: replacements.append((source, replacement))
    )

    assert dialog.replace_selected()

    assert replacements == [("Bright", "Radiant")]


def test_context_dialog_replaces_exact_original_editor_word(
    application, service, monkeypatch
):
    monkeypatch.setattr(service, "thesaurus_entry", _entry)
    editor = QTextEdit("Bright bright")
    integration = LinguisticTextEditDecorator(
        editor,
        service,
        settings=QtLinguisticSettings(highlighting_enabled=False),
    )
    cursor = editor.textCursor()
    cursor.setPosition(2)
    dialog = integration.context_menu.open_thesaurus_dialog("Bright", cursor)
    dialog.results.setCurrentItem(dialog.results.topLevelItem(0).child(0))

    assert dialog.replace_selected()

    assert editor.toPlainText() == "Radiant bright"
    dialog.close()


def test_context_dialog_refuses_stale_editor_replacement(
    application, service, monkeypatch
):
    monkeypatch.setattr(service, "thesaurus_entry", _entry)
    editor = QTextEdit("Bright remains")
    integration = LinguisticTextEditDecorator(
        editor,
        service,
        settings=QtLinguisticSettings(highlighting_enabled=False),
    )
    cursor = editor.textCursor()
    cursor.setPosition(2)
    dialog = integration.context_menu.open_thesaurus_dialog("Bright", cursor)
    editor.setPlainText("Changed remains")
    dialog.results.setCurrentItem(dialog.results.topLevelItem(0).child(0))

    assert dialog.replace_selected()

    assert editor.toPlainText() == "Changed remains"
    dialog.close()
