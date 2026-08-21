from __future__ import annotations

from collections import Counter
import os
from threading import Event, get_ident
import time

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6", reason="PyQt6 is an optional dependency")

from PyQt6.QtCore import QTimer
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


def _wait_until(application, predicate, timeout: float = 3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        application.processEvents()
        if predicate():
            return
        time.sleep(0.001)
    raise AssertionError("condition was not reached before timeout")


def _format_count(editor: QTextEdit) -> int:
    count = 0
    block = editor.document().firstBlock()
    while block.isValid():
        count += len(block.layout().formats())
        block = block.next()
    return count


def test_decorator_checks_cache_misses_outside_gui_thread(
    application, service, monkeypatch
):
    gui_thread = get_ident()
    worker_threads: list[int] = []

    def check_word(_word, **_kwargs):
        worker_threads.append(get_ident())
        return False

    monkeypatch.setattr(service, "check_word", check_word)
    editor = QTextEdit("error")
    decorator = LinguisticTextEditDecorator(
        editor,
        service,
        settings=QtLinguisticSettings(debounce_ms=10),
    )

    _wait_until(application, lambda: _format_count(editor) == 1)

    assert worker_threads
    assert all(thread != gui_thread for thread in worker_threads)
    assert decorator.async_controller.jobs_started == 1
    assert decorator.async_controller.jobs_finished == 1


def test_rapid_typing_is_debounced_into_one_batch(application, service, monkeypatch):
    calls: Counter[str] = Counter()

    def check_word(word, **_kwargs):
        calls[word] += 1
        return True

    monkeypatch.setattr(service, "check_word", check_word)
    editor = QTextEdit()
    decorator = LinguisticTextEditDecorator(
        editor,
        service,
        settings=QtLinguisticSettings(debounce_ms=40),
    )

    for text in ("primera", "segunda", "final"):
        editor.setPlainText(text)
        application.processEvents()

    _wait_until(application, lambda: decorator.async_controller.jobs_finished == 1)

    assert decorator.async_controller.jobs_started == 1
    assert calls["final"] == 1


def test_obsolete_running_results_are_cancelled_and_discarded(
    application, service, monkeypatch
):
    first_started = Event()
    release_first = Event()
    calls: list[str] = []

    def check_word(word, **_kwargs):
        calls.append(word)
        if word == "antigua":
            first_started.set()
            release_first.wait(2)
        return False

    monkeypatch.setattr(service, "check_word", check_word)
    editor = QTextEdit("antigua")
    decorator = LinguisticTextEditDecorator(
        editor,
        service,
        settings=QtLinguisticSettings(debounce_ms=0),
    )
    discarded: list[int] = []
    decorator.async_controller.results_discarded.connect(discarded.append)

    _wait_until(application, first_started.is_set)
    editor.setPlainText("nueva")
    application.processEvents()
    release_first.set()

    _wait_until(application, lambda: "nueva" in calls and _format_count(editor) == 1)

    assert discarded
    assert editor.toPlainText() == "nueva"


def test_one_batch_worker_checks_many_words_without_blocking_event_loop(
    application, service, monkeypatch
):
    release_worker = Event()
    worker_started = Event()
    threads: set[int] = set()

    def check_word(_word, **_kwargs):
        threads.add(get_ident())
        worker_started.set()
        release_worker.wait(2)
        return True

    monkeypatch.setattr(service, "check_word", check_word)
    words = " ".join(f"word{letter}" for letter in "abcdefghijklmnopqrstuvwxyz")
    editor = QTextEdit(words)
    decorator = LinguisticTextEditDecorator(
        editor,
        service,
        settings=QtLinguisticSettings(debounce_ms=0),
    )
    gui_event_processed: list[bool] = []

    try:
        _wait_until(application, worker_started.is_set)
        QTimer.singleShot(0, lambda: gui_event_processed.append(True))
        _wait_until(application, lambda: bool(gui_event_processed))
    finally:
        release_worker.set()

    _wait_until(application, lambda: decorator.async_controller.jobs_finished == 1)

    assert decorator.async_controller.jobs_started == 1
    assert len(threads) == 1


def test_deleting_editor_with_running_job_is_safe(application, service, monkeypatch):
    worker_started = Event()
    release_worker = Event()

    def check_word(_word, **_kwargs):
        worker_started.set()
        release_worker.wait(2)
        return False

    monkeypatch.setattr(service, "check_word", check_word)
    editor = QTextEdit("pendiente")
    LinguisticTextEditDecorator(
        editor,
        service,
        settings=QtLinguisticSettings(debounce_ms=0),
    )

    _wait_until(application, worker_started.is_set)
    editor.deleteLater()
    application.processEvents()
    release_worker.set()
    deadline = time.monotonic() + 0.1
    while time.monotonic() < deadline:
        application.processEvents()
        time.sleep(0.001)


def test_long_document_and_long_word_are_processed_as_one_batch(
    application, service, monkeypatch
):
    long_word = "x" * 4_096
    checked: list[str] = []

    def check_word(word, **_kwargs):
        checked.append(word)
        return True

    monkeypatch.setattr(service, "check_word", check_word)
    editor = QPlainTextEdit("letra\n" * 5_000 + long_word)
    decorator = LinguisticTextEditDecorator(
        editor,
        service,
        settings=QtLinguisticSettings(debounce_ms=0),
    )

    _wait_until(application, lambda: decorator.async_controller.jobs_finished == 1)

    assert long_word in checked
    assert decorator.async_controller.jobs_started == 1


def test_worker_failure_returns_to_idle_without_touching_document(
    application, service, monkeypatch
):
    failure = RuntimeError("strict backend failure")
    monkeypatch.setattr(
        service,
        "check_word",
        lambda _word, **_kwargs: (_ for _ in ()).throw(failure),
    )
    editor = QTextEdit("error")
    decorator = LinguisticTextEditDecorator(
        editor,
        service,
        settings=QtLinguisticSettings(debounce_ms=0),
    )
    failures: list[object] = []
    decorator.async_controller.job_failed.connect(
        lambda _generation, error: failures.append(error)
    )

    _wait_until(application, lambda: bool(failures))

    assert failures == [failure]
    assert not decorator.async_controller.busy
    assert _format_count(editor) == 0
