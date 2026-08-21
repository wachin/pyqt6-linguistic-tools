from __future__ import annotations

import os

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6", reason="PyQt6 is an optional dependency")

from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QApplication, QPlainTextEdit

from pyqt6_linguistic_tools import (
    DictionaryRegistry,
    DictionarySourcePriority,
    DirectoryDictionaryProvider,
    LinguisticService,
    PersonalDictionaryStore,
)
from pyqt6_linguistic_tools.qt import LinguisticTextEditDecorator


class _NoFullTextReadPlainTextEdit(QPlainTextEdit):
    """Fail if cursor lookup copies the complete document."""

    forbid_full_text_read = False

    def toPlainText(self) -> str:  # noqa: N802
        if self.forbid_full_text_read:
            raise AssertionError("cursor lookup must not read the full document")
        return super().toPlainText()


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
        "4\ncanción\nletra\nmúsica\nfinal\n",
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


def _cursor_at_end(editor: QPlainTextEdit) -> QTextCursor:
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    editor.setTextCursor(cursor)
    return cursor


def test_plain_text_editor_has_cursor_operation_parity(application, service):
    editor = QPlainTextEdit("cansion canción")
    decorator = LinguisticTextEditDecorator(editor, service)
    cursor = editor.textCursor()
    cursor.setPosition(2)
    editor.setTextCursor(cursor)

    token = decorator.word_at_cursor()

    assert token is not None and token.text == "cansion"
    assert decorator.check_word_at_cursor() is False
    assert "canción" in decorator.suggestions_at_cursor()
    assert decorator.replace_word_at_cursor("canción", expected_word="cansion")
    assert editor.toPlainText() == "canción canción"


def test_large_document_lookup_tokenizes_only_current_block(application, service):
    editor = _NoFullTextReadPlainTextEdit()
    editor.setPlainText("letra breve\n" * 20_000 + "😀 cansion final")
    decorator = LinguisticTextEditDecorator(editor, service)
    inspected_sources: list[str] = []

    def observe_source(_token, source):
        inspected_sources.append(source)
        return True

    decorator.add_token_filter(observe_source)
    _cursor_at_end(editor)
    editor.forbid_full_text_read = True

    token = decorator.word_at_cursor()

    assert token is not None and token.text == "final"
    assert inspected_sources
    assert set(inspected_sources) == {"😀 cansion final"}


def test_large_document_queries_do_not_edit_or_request_repaint(application, service):
    editor = QPlainTextEdit("letra breve\n" * 10_000 + "canción")
    decorator = LinguisticTextEditDecorator(editor, service)
    _cursor_at_end(editor)
    application.processEvents()
    text_changes: list[None] = []
    update_requests: list[object] = []
    editor.textChanged.connect(lambda: text_changes.append(None))
    editor.updateRequest.connect(lambda *args: update_requests.append(args))
    revision = editor.document().revision()

    assert decorator.word_at_cursor().text == "canción"
    assert decorator.check_word_at_cursor() is True

    assert editor.document().revision() == revision
    assert text_changes == []
    assert update_requests == []


def test_plain_text_replacement_uses_global_utf16_block_offsets(application, service):
    editor = QPlainTextEdit("😀 primera línea\notra cansion final")
    decorator = LinguisticTextEditDecorator(editor, service)
    cursor = editor.document().find("cansion")
    cursor.setPosition(cursor.selectionStart() + 2)
    editor.setTextCursor(cursor)

    token = decorator.word_at_cursor()

    assert token is not None and token.text == "cansion"
    assert decorator.cursor_for_word(token).selectedText() == "cansion"
    assert decorator.replace_word_at_cursor("canción", expected_word="cansion")
    assert editor.toPlainText() == "😀 primera línea\notra canción final"


def test_plain_text_editor_obeys_independent_enable_state(application, service):
    editor = QPlainTextEdit("cansion")
    decorator = LinguisticTextEditDecorator(editor, service)
    cursor = editor.textCursor()
    cursor.setPosition(2)
    editor.setTextCursor(cursor)

    decorator.set_spellcheck_enabled(False)

    assert decorator.word_at_cursor().text == "cansion"
    assert decorator.check_word_at_cursor() is None
    assert decorator.suggestions_at_cursor() == ()
