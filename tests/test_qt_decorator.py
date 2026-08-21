from __future__ import annotations

import os

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6", reason="PyQt6 is an optional dependency")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLabel, QPlainTextEdit, QTextEdit

from pyqt6_linguistic_tools import (
    DictionaryRegistry,
    DictionarySourcePriority,
    DirectoryDictionaryProvider,
    LinguisticService,
    PersonalDictionaryStore,
    UnicodeTokenizer,
)
from pyqt6_linguistic_tools.qt import (
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


@pytest.mark.parametrize("editor_type", [QTextEdit, QPlainTextEdit])
def test_attaches_without_subclassing_and_detaches_cleanly(
    application, service, editor_type
):
    editor = editor_type()
    original_policy = editor.contextMenuPolicy()
    decorator = LinguisticTextEditDecorator(editor, service)

    assert decorator.editor is editor
    assert decorator.parent() is editor
    assert decorator.is_attached
    assert editor.contextMenuPolicy() == original_policy

    assert decorator.detach()
    assert decorator.editor is None
    assert decorator.parent() is None
    assert not decorator.is_attached
    assert not decorator.detach()
    assert editor.contextMenuPolicy() == original_policy


def test_rejects_unsupported_widgets_and_duplicate_decorators(application, service):
    with pytest.raises(TypeError, match="QTextEdit or QPlainTextEdit"):
        LinguisticTextEditDecorator(QLabel(), service)

    editor = QTextEdit()
    first = LinguisticTextEditDecorator(editor, service)
    with pytest.raises(RuntimeError, match="already has"):
        LinguisticTextEditDecorator(editor, service)
    first.detach()


def test_enable_states_are_local_and_independent(application, service):
    editor = QTextEdit()
    settings = QtLinguisticSettings(thesaurus_enabled=False)
    decorator = LinguisticTextEditDecorator(editor, service, settings=settings)
    changes: list[bool] = []
    decorator.spellcheck_enabled_changed.connect(changes.append)

    assert decorator.spellcheck_active
    assert not decorator.thesaurus_active
    assert decorator.set_spellcheck_enabled(False)
    assert not decorator.set_spellcheck_enabled(False)
    assert changes == [False]
    assert not decorator.spellcheck_active
    assert service.spell_check_enabled

    assert decorator.set_thesaurus_enabled(True)
    assert decorator.thesaurus_active
    assert service.thesaurus_enabled
    assert decorator.set_enabled(False)
    assert not decorator.spellcheck_active
    assert not decorator.thesaurus_active
    assert decorator.set_enabled(True)
    assert decorator.thesaurus_active


def test_registered_token_filters_are_composed_without_mutating_base(
    application, service
):
    editor = QPlainTextEdit()

    def retain_not_base(token, _source):
        return token.text != "base"

    def retain_not_chord(token, _source):
        return token.text != "Am"

    base = UnicodeTokenizer(token_filters=(retain_not_base,))
    decorator = LinguisticTextEditDecorator(editor, service, tokenizer=base)
    changes: list[None] = []
    decorator.token_filters_changed.connect(lambda: changes.append(None))

    assert decorator.add_token_filter(retain_not_chord)
    assert not decorator.add_token_filter(retain_not_chord)
    assert [token.text for token in decorator.create_tokenizer().tokenize("base Am song")] == [
        "song"
    ]
    assert [token.text for token in base.tokenize("base Am song")] == ["Am", "song"]
    assert decorator.remove_token_filter(retain_not_chord)
    assert not decorator.remove_token_filter(retain_not_chord)
    assert len(changes) == 2


def test_host_context_action_providers_are_retained_by_identity(application, service):
    editor = QTextEdit()
    decorator = LinguisticTextEditDecorator(editor, service)

    def provider(*_args):
        return ()

    assert decorator.add_context_action_provider(provider)
    assert not decorator.add_context_action_provider(provider)
    assert decorator.context_action_providers == (provider,)
    assert decorator.remove_context_action_provider(provider)
    assert not decorator.remove_context_action_provider(provider)


def test_event_filter_does_not_consume_host_events_or_signals(application, service):
    editor = QTextEdit()
    editor.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    decorator = LinguisticTextEditDecorator(editor, service)
    changes: list[str] = []
    editor.textChanged.connect(lambda: changes.append(editor.toPlainText()))

    editor.setPlainText("preserved")
    application.processEvents()

    assert changes == ["preserved"]
    assert editor.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu
    assert decorator.is_attached


def test_can_reattach_to_another_supported_editor(application, service):
    first = QTextEdit()
    second = QPlainTextEdit()
    decorator = LinguisticTextEditDecorator(first, service)

    with pytest.raises(RuntimeError, match="detach"):
        decorator.attach(second)
    assert decorator.detach()
    assert decorator.attach(second)
    assert decorator.editor is second
    assert not decorator.attach(second)


@pytest.mark.parametrize(
    "method_name",
    [
        "set_enabled",
        "set_spellcheck_enabled",
        "set_highlighting_enabled",
        "set_thesaurus_enabled",
        "set_context_menu_enabled",
    ],
)
def test_enable_methods_require_real_booleans(application, service, method_name):
    decorator = LinguisticTextEditDecorator(QTextEdit(), service)

    with pytest.raises(TypeError, match="boolean"):
        getattr(decorator, method_name)(1)
