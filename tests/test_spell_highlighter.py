from __future__ import annotations

from collections import Counter
import os

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6", reason="PyQt6 is an optional dependency")

from PyQt6.QtGui import QColor, QTextCharFormat
from PyQt6.QtWidgets import QApplication, QPlainTextEdit, QTextEdit

from pyqt6_linguistic_tools import (
    DictionaryRegistry,
    DictionarySourcePriority,
    DirectoryDictionaryProvider,
    LinguisticService,
    PersonalDictionaryStore,
)
from pyqt6_linguistic_tools.qt import (
    LinguisticTextEditDecorator,
    SpellCheckHighlighter,
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


def _format_ranges(editor):
    ranges = []
    block = editor.document().firstBlock()
    while block.isValid():
        ranges.extend(block.layout().formats())
        block = block.next()
    return ranges


@pytest.mark.parametrize("editor_type", [QTextEdit, QPlainTextEdit])
def test_underlines_only_misspellings_with_red_wave_style(
    application, service, monkeypatch, editor_type
):
    monkeypatch.setattr(
        service,
        "check_word",
        lambda word, **_kwargs: word != "cansion",
    )
    editor = editor_type("canción cansion")
    highlighter = SpellCheckHighlighter(editor.document(), service)

    highlighter.rehighlight()
    ranges = _format_ranges(editor)

    assert len(ranges) == 1
    assert ranges[0].start == 8
    assert ranges[0].length == 7
    assert (
        ranges[0].format.underlineStyle()
        == QTextCharFormat.UnderlineStyle.SpellCheckUnderline
    )
    assert ranges[0].format.underlineColor() == QColor("#d02020")


def test_highlighting_never_requests_suggestions(application, service, monkeypatch):
    monkeypatch.setattr(service, "check_word", lambda _word, **_kwargs: False)

    def fail_suggestions(*_args, **_kwargs):
        raise AssertionError("suggestions must not run while highlighting")

    monkeypatch.setattr(service, "suggestions", fail_suggestions)
    editor = QTextEdit("cansion")
    highlighter = SpellCheckHighlighter(editor.document(), service)

    highlighter.rehighlight()

    assert len(_format_ranges(editor)) == 1


def test_unchanged_words_use_bounded_local_cache(application, service, monkeypatch):
    calls: Counter[str] = Counter()

    def check_word(word, **_kwargs):
        calls[word] += 1
        return word == "bien"

    monkeypatch.setattr(service, "check_word", check_word)
    editor = QTextEdit("mal mal bien")
    highlighter = SpellCheckHighlighter(editor.document(), service, cache_size=2)

    highlighter.rehighlight()
    highlighter.rehighlight()
    stats = highlighter.cache_stats()

    assert calls == Counter({"mal": 1, "bien": 1})
    assert stats.size == 2
    assert stats.max_size == 2
    assert stats.hits >= 4


def test_cache_evicts_when_unique_word_budget_is_exceeded(
    application, service, monkeypatch
):
    monkeypatch.setattr(service, "check_word", lambda _word, **_kwargs: True)
    editor = QTextEdit("uno dos tres")
    highlighter = SpellCheckHighlighter(editor.document(), service, cache_size=2)

    highlighter.rehighlight()
    stats = highlighter.cache_stats()

    assert stats.size == 2
    assert stats.evictions >= 1


def test_invalidate_word_rehighlights_only_affected_blocks(
    application, service, monkeypatch
):
    class TrackingHighlighter(SpellCheckHighlighter):
        def __init__(self, *args, **kwargs):
            self.visited_blocks: list[int] = []
            super().__init__(*args, **kwargs)

        def highlightBlock(self, text):  # noqa: N802
            self.visited_blocks.append(self.currentBlock().blockNumber())
            super().highlightBlock(text)

    monkeypatch.setattr(service, "check_word", lambda _word, **_kwargs: False)
    editor = QPlainTextEdit("error aquí\nbien aquí\notro error")
    highlighter = TrackingHighlighter(editor.document(), service)
    highlighter.rehighlight()
    highlighter.visited_blocks.clear()

    assert highlighter.invalidate_word("error") == 1

    assert highlighter.visited_blocks == [0, 2]


def test_style_and_enable_state_are_independently_configurable(
    application, service, monkeypatch
):
    monkeypatch.setattr(service, "check_word", lambda _word, **_kwargs: False)
    editor = QTextEdit("error")
    highlighter = SpellCheckHighlighter(editor.document(), service)
    custom_format = QTextCharFormat()
    custom_format.setUnderlineColor(QColor("blue"))
    custom_format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.DashUnderline)

    assert highlighter.set_misspelling_format(custom_format)
    assert not highlighter.set_misspelling_format(custom_format)
    assert _format_ranges(editor)[0].format.underlineColor() == QColor("blue")
    assert highlighter.set_enabled(False)
    assert _format_ranges(editor) == []
    assert highlighter.set_enabled(True)
    assert len(_format_ranges(editor)) == 1


def test_decorator_owns_and_coordinates_highlighter(
    application, service, monkeypatch
):
    monkeypatch.setattr(service, "check_word", lambda _word, **_kwargs: False)
    first = QTextEdit("error")
    second = QPlainTextEdit("otro")
    decorator = LinguisticTextEditDecorator(first, service)

    assert decorator.highlighter.parent() is decorator
    assert decorator.highlighter.document() is first.document()
    assert len(_format_ranges(first)) == 1

    decorator.set_highlighting_enabled(False)
    assert _format_ranges(first) == []
    assert decorator.check_word_at_cursor() is False

    decorator.set_highlighting_enabled(True)
    assert len(_format_ranges(first)) == 1
    decorator.detach()
    assert decorator.highlighter.document() is None
    decorator.attach(second)
    assert decorator.highlighter.document() is second.document()


def test_decorator_filters_immediately_refresh_highlighting(
    application, service, monkeypatch
):
    monkeypatch.setattr(service, "check_word", lambda _word, **_kwargs: False)
    editor = QTextEdit("Am letra")
    decorator = LinguisticTextEditDecorator(editor, service)

    assert len(_format_ranges(editor)) == 2
    decorator.add_token_filter(lambda token, _source: token.text != "Am")
    ranges = _format_ranges(editor)

    assert len(ranges) == 1
    assert ranges[0].start == 3
