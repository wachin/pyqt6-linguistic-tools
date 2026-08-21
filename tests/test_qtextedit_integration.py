from __future__ import annotations

import os

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6", reason="PyQt6 is an optional dependency")

from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QApplication, QTextEdit

from pyqt6_linguistic_tools import (
    DictionaryRegistry,
    DictionarySourcePriority,
    DirectoryDictionaryProvider,
    LinguisticService,
    PersonalDictionaryStore,
)
from pyqt6_linguistic_tools.qt import LinguisticTextEditDecorator


@pytest.fixture(scope="module")
def application():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def service(tmp_path):
    dictionaries = tmp_path / "dictionaries"
    dictionaries.mkdir()
    (dictionaries / "es_EC.aff").write_text(
        "SET UTF-8\nTRY eaosrnidlctumpbgvyqhfzjxkw\n",
        encoding="utf-8",
    )
    (dictionaries / "es_EC.dic").write_text(
        "4\nSeñor\ncanción\nletra\nmúsica\n",
        encoding="utf-8",
    )
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
        "es_EC",
        registry=registry,
        personal_store=PersonalDictionaryStore(tmp_path / "personal"),
    )


def _utf16_position(text: str, python_position: int) -> int:
    return len(text[:python_position].encode("utf-16-le")) // 2


def _cursor_at(editor: QTextEdit, position: int) -> QTextCursor:
    cursor = editor.textCursor()
    cursor.setPosition(position)
    editor.setTextCursor(cursor)
    return cursor


@pytest.mark.parametrize(
    ("needle", "expected"),
    [
        ("Señ", "Señor"),
        ("Art", "d’Artagnan"),
        ("Connor", "O'Connor"),
        ("n-roll", "rock-n-roll"),
    ],
)
def test_detects_unicode_words_at_exact_qt_offsets(
    application, service, needle, expected
):
    text = "😀 Señor d’Artagnan O'Connor rock-n-roll, fin"
    editor = QTextEdit()
    editor.setPlainText(text)
    decorator = LinguisticTextEditDecorator(editor, service)
    python_position = text.index(needle) + 1
    cursor = _cursor_at(editor, _utf16_position(text, python_position))

    token = decorator.word_at_cursor(cursor)

    assert token is not None
    assert token.text == expected
    assert decorator.cursor_for_word(token).selectedText() == expected


def test_cursor_immediately_after_word_resolves_it_but_after_punctuation_does_not(
    application, service
):
    text = "canción, música"
    editor = QTextEdit(text)
    decorator = LinguisticTextEditDecorator(editor, service)

    end_of_word = _utf16_position(text, text.index(","))
    after_comma = _utf16_position(text, text.index(",") + 1)

    assert decorator.word_at_cursor(_cursor_at(editor, end_of_word)).text == "canción"
    assert decorator.word_at_cursor(_cursor_at(editor, after_comma)) is None


def test_domain_filter_excludes_word_under_cursor(application, service):
    editor = QTextEdit("Am canción")
    decorator = LinguisticTextEditDecorator(editor, service)
    decorator.add_token_filter(lambda token, _source: token.text != "Am")

    assert decorator.word_at_cursor(_cursor_at(editor, 1)) is None
    assert decorator.word_at_cursor(_cursor_at(editor, 5)).text == "canción"


def test_cursor_must_belong_to_attached_document(application, service):
    editor = QTextEdit("canción")
    other = QTextEdit("música")
    decorator = LinguisticTextEditDecorator(editor, service)

    with pytest.raises(ValueError, match="attached editor document"):
        decorator.word_at_cursor(other.textCursor())


def test_checks_and_suggests_for_word_at_cursor(application, service):
    editor = QTextEdit("cansion canción")
    decorator = LinguisticTextEditDecorator(editor, service)

    _cursor_at(editor, 2)
    assert decorator.check_word_at_cursor() is False
    assert "canción" in decorator.suggestions_at_cursor()

    _cursor_at(editor, 12)
    assert decorator.check_word_at_cursor() is True
    assert decorator.suggestions_at_cursor() == ()

    decorator.set_spellcheck_enabled(False)
    assert decorator.check_word_at_cursor() is None
    assert decorator.suggestions_at_cursor() == ()


def test_replaces_only_current_word_and_rejects_stale_expectation(
    application, service
):
    text = "😀 cansion y cansion"
    editor = QTextEdit(text)
    decorator = LinguisticTextEditDecorator(editor, service)
    cursor = _cursor_at(editor, _utf16_position(text, text.index("cansion") + 2))

    assert not decorator.replace_word_at_cursor(
        "canción", cursor, expected_word="another"
    )
    assert editor.toPlainText() == text
    assert decorator.replace_word_at_cursor(
        "canción", cursor, expected_word="cansion"
    )
    assert editor.toPlainText() == "😀 canción y cansion"
    assert editor.textCursor().position() == _utf16_position("😀 canción", 9)


def test_replacement_preserves_surrounding_rich_text(application, service):
    editor = QTextEdit()
    editor.setHtml("<p>una <b>cansion</b> final</p>")
    decorator = LinguisticTextEditDecorator(editor, service)
    cursor = _cursor_at(editor, editor.toPlainText().index("cansion") + 2)

    assert decorator.replace_word_at_cursor("canción", cursor)
    assert editor.toPlainText() == "una canción final"
    assert "font-weight:700" in editor.toHtml().replace(" ", "")


def test_read_only_editor_and_invalid_replacements_are_safe(application, service):
    editor = QTextEdit("cansion")
    decorator = LinguisticTextEditDecorator(editor, service)
    _cursor_at(editor, 2)
    editor.setReadOnly(True)

    assert not decorator.replace_word_at_cursor("canción")
    assert editor.toPlainText() == "cansion"
    with pytest.raises(ValueError, match="single line"):
        decorator.replace_word_at_cursor("dos\nlíneas")
    with pytest.raises(ValueError, match="not be empty"):
        decorator.replace_word_at_cursor("")
