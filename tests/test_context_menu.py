from __future__ import annotations

import os

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6", reason="PyQt6 is an optional dependency")

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QAction, QContextMenuEvent
from PyQt6.QtWidgets import QApplication, QMenu, QTextEdit

from pyqt6_linguistic_tools import (
    DictionaryRegistry,
    DictionarySourcePriority,
    DirectoryDictionaryProvider,
    LinguisticService,
    PersonalDictionaryStore,
)
from pyqt6_linguistic_tools.qt import (
    LinguisticAction,
    LinguisticTextEditDecorator,
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
        "es_EC",
        registry=registry,
        personal_store=PersonalDictionaryStore(tmp_path / "personal"),
    )


def _integration(editor, service, **settings):
    return LinguisticTextEditDecorator(
        editor,
        service,
        settings=QtLinguisticSettings(highlighting_enabled=False, **settings),
    )


def _place_cursor(editor: QTextEdit, position: int = 2):
    cursor = editor.textCursor()
    cursor.setPosition(position)
    editor.setTextCursor(cursor)
    return cursor


def _all_actions(menu: QMenu):
    result = []
    for action in menu.actions():
        result.append(action)
        if action.menu() is not None:
            result.extend(_all_actions(action.menu()))
    return result


def _action(menu: QMenu, text: str) -> QAction:
    matches = [action for action in _all_actions(menu) if action.text() == text]
    assert matches, f"missing menu action: {text}"
    return matches[0]


def test_preserves_standard_host_and_provider_actions(application, service, monkeypatch):
    monkeypatch.setattr(service, "check_word", lambda _word, **_kwargs: True)
    monkeypatch.setattr(service, "synonyms", lambda _word: ())
    monkeypatch.setattr(service, "available_languages", lambda: ())
    editor = QTextEdit("correcta")
    host_action = QAction("Host action", editor)
    editor.addAction(host_action)
    integration = _integration(editor, service)

    def provider(_editor, _menu, _token):
        return QAction("Provider action", editor)

    integration.add_context_action_provider(provider)
    menu = integration.context_menu.create_menu(_place_cursor(editor))
    texts = [action.text() for action in _all_actions(menu)]

    assert any("Undo" in text for text in texts)
    assert "Host action" in texts
    assert "Provider action" in texts


def test_misspelled_word_gets_bounded_suggestions_and_safe_replacement(
    application, service, monkeypatch
):
    monkeypatch.setattr(service, "check_word", lambda _word, **_kwargs: False)
    monkeypatch.setattr(
        service,
        "suggestions",
        lambda _word, **_kwargs: ("canción", "cansión")[: _kwargs["limit"]],
    )
    monkeypatch.setattr(service, "synonyms", lambda _word: ())
    monkeypatch.setattr(service, "available_languages", lambda: ())
    editor = QTextEdit("cansion final")
    integration = _integration(editor, service, suggestion_limit=1)
    cursor = _place_cursor(editor)
    menu = integration.context_menu.create_menu(cursor)

    assert _action(menu, "canción")
    assert not any(action.text() == "cansión" for action in _all_actions(menu))
    _action(menu, "canción").trigger()

    assert editor.toPlainText() == "canción final"


def test_correct_word_has_thesaurus_and_language_but_no_spelling_actions(
    application, service, monkeypatch
):
    monkeypatch.setattr(service, "check_word", lambda _word, **_kwargs: True)

    def fail_suggestions(*_args, **_kwargs):
        raise AssertionError("correct words must not request spelling suggestions")

    monkeypatch.setattr(service, "suggestions", fail_suggestions)
    monkeypatch.setattr(service, "synonyms", lambda _word: ("tema", "canto"))
    monkeypatch.setattr(service, "available_languages", lambda: ("en_US", "es_EC"))
    editor = QTextEdit("canción")
    integration = _integration(editor, service)
    menu = integration.context_menu.create_menu(_place_cursor(editor))
    texts = [action.text() for action in _all_actions(menu)]

    assert "Synonyms" in texts
    assert "Open Thesaurus…" in texts
    assert "Language" in texts
    assert "Ignore" not in texts
    assert "Add to Dictionary" not in texts


def test_synonyms_are_bounded_and_more_action_emits_request(
    application, service, monkeypatch
):
    monkeypatch.setattr(service, "check_word", lambda _word, **_kwargs: True)
    monkeypatch.setattr(service, "synonyms", lambda _word: ("uno", "dos", "tres"))
    monkeypatch.setattr(service, "available_languages", lambda: ())
    editor = QTextEdit("palabra")
    integration = _integration(editor, service, synonym_limit=2)
    requested: list[str] = []
    integration.context_menu.more_synonyms_requested.connect(requested.append)
    menu = integration.context_menu.create_menu(_place_cursor(editor))

    assert _action(menu, "uno")
    assert _action(menu, "dos")
    assert not any(action.text() == "tres" for action in _all_actions(menu))
    _action(menu, "More synonyms…").trigger()

    assert requested == ["palabra"]


def test_ignore_once_and_ignore_all_keep_scopes_separate(
    application, service, monkeypatch
):
    monkeypatch.setattr(service, "check_word", lambda _word, **_kwargs: False)
    monkeypatch.setattr(service, "suggestions", lambda *_args, **_kwargs: ())
    monkeypatch.setattr(service, "synonyms", lambda _word: ())
    monkeypatch.setattr(service, "available_languages", lambda: ())
    editor = QTextEdit("error error")
    integration = _integration(editor, service)
    cursor = _place_cursor(editor)
    token = integration.word_at_cursor(cursor)
    menu = integration.context_menu.create_menu(cursor)

    _action(menu, "Ignore").trigger()
    ignored = service.ignored_words()
    document_id = integration.highlighter.document_id

    assert ignored.is_ignored(
        "error",
        document_id=document_id,
        occurrence_id=token.utf16_start,
    )
    assert not ignored.is_ignored("error", document_id=document_id, occurrence_id=6)

    second_cursor = _place_cursor(editor, 8)
    second_menu = integration.context_menu.create_menu(second_cursor)
    _action(second_menu, "Ignore All").trigger()
    assert ignored.is_ignored("error", document_id=document_id, occurrence_id=6)


def test_add_to_dictionary_updates_personal_words(application, service, monkeypatch):
    monkeypatch.setattr(service, "check_word", lambda _word, **_kwargs: False)
    monkeypatch.setattr(service, "suggestions", lambda *_args, **_kwargs: ())
    monkeypatch.setattr(service, "synonyms", lambda _word: ())
    monkeypatch.setattr(service, "available_languages", lambda: ())
    editor = QTextEdit("ChordFlow")
    integration = _integration(editor, service)
    menu = integration.context_menu.create_menu(_place_cursor(editor))

    _action(menu, "Add to Dictionary").trigger()

    assert service.personal_words() == ("ChordFlow",)


def test_individual_actions_and_custom_policy_remain_host_controlled(
    application, service, monkeypatch
):
    monkeypatch.setattr(service, "check_word", lambda _word, **_kwargs: False)
    monkeypatch.setattr(service, "suggestions", lambda *_args, **_kwargs: ("fixed",))
    monkeypatch.setattr(service, "synonyms", lambda _word: ())
    monkeypatch.setattr(service, "available_languages", lambda: ())
    editor = QTextEdit("error")
    editor.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    integration = _integration(editor, service)
    integration.context_menu.set_action_enabled(LinguisticAction.IGNORE, False)
    menu = integration.context_menu.create_menu(_place_cursor(editor))

    assert not any(action.text() == "Ignore" for action in _all_actions(menu))
    event = QContextMenuEvent(
        QContextMenuEvent.Reason.Mouse,
        QPoint(1, 1),
        QPoint(1, 1),
    )
    assert not integration.context_menu.handle_event(editor.viewport(), event)


def test_language_and_thesaurus_actions_emit_and_update(application, service, monkeypatch):
    monkeypatch.setattr(service, "check_word", lambda _word, **_kwargs: True)
    monkeypatch.setattr(service, "synonyms", lambda _word: ())
    monkeypatch.setattr(service, "available_languages", lambda: ("en_US", "es_EC"))
    editor = QTextEdit("palabra")
    integration = _integration(editor, service)
    thesaurus_requests: list[str] = []
    language_changes: list[str] = []
    integration.context_menu.open_thesaurus_requested.connect(
        thesaurus_requests.append
    )
    integration.context_menu.language_changed.connect(language_changes.append)
    menu = integration.context_menu.create_menu(_place_cursor(editor))

    _action(menu, "Open Thesaurus…").trigger()
    english = next(action for action in _all_actions(menu) if action.data() == "en_US")
    english.trigger()

    assert thesaurus_requests == ["palabra"]
    assert language_changes == ["en_US"]
    assert service.language == "en_US"
