"""Debounced, generation-safe background spelling checks for Qt editors."""

from __future__ import annotations

from collections.abc import Iterable
from threading import Event
import unicodedata
import weakref

from pyqt6_linguistic_tools.service import LinguisticService
from pyqt6_linguistic_tools.qt._compat import require_pyqt6
from pyqt6_linguistic_tools.qt.spell_highlighter import SpellCheckHighlighter


require_pyqt6()

from PyQt6 import sip  # noqa: E402
from PyQt6.QtCore import (  # noqa: E402
    QObject,
    QRunnable,
    QThreadPool,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import QTextDocument  # noqa: E402


class _WorkerSignals(QObject):
    completed = pyqtSignal(int, str, object, bool, object, object)


class _SpellCheckBatch(QRunnable):
    """Check one word batch sequentially inside one pooled worker."""

    def __init__(
        self,
        generation: int,
        locale: str,
        words: tuple[str, ...],
        service: LinguisticService,
        cancelled: Event,
        lifetime_guard: object,
    ) -> None:
        super().__init__()
        self.generation = generation
        self.locale = locale
        self.words = words
        self.service = service
        self.cancelled = cancelled
        self.lifetime_guard = lifetime_guard
        self.signals = _WorkerSignals()

    def run(self) -> None:
        results: dict[str, bool] = {}
        error: Exception | None = None
        try:
            for word in self.words:
                if self.cancelled.is_set():
                    break
                results[word] = self.service.check_word(word, locale=self.locale)
        except Exception as caught:
            error = caught
        was_cancelled = self.cancelled.is_set()
        self.signals.completed.emit(
            self.generation,
            self.locale,
            results,
            was_cancelled,
            self.lifetime_guard,
            error,
        )


class AsyncSpellCheckController(QObject):
    """Batch unknown words after typing and ignore obsolete worker results."""

    job_started = pyqtSignal(int, int)
    job_finished = pyqtSignal(int, int)
    job_failed = pyqtSignal(int, object)
    results_discarded = pyqtSignal(int)
    idle_changed = pyqtSignal(bool)

    def __init__(
        self,
        highlighter: SpellCheckHighlighter,
        service: LinguisticService,
        *,
        debounce_ms: int = 300,
        thread_pool: QThreadPool | None = None,
        parent: QObject | None = None,
    ) -> None:
        if not isinstance(highlighter, SpellCheckHighlighter):
            raise TypeError("highlighter must be a SpellCheckHighlighter")
        if not isinstance(service, LinguisticService):
            raise TypeError("service must be a LinguisticService")
        if isinstance(debounce_ms, bool) or not isinstance(debounce_ms, int):
            raise TypeError("debounce_ms must be an integer")
        if debounce_ms < 0:
            raise ValueError("debounce_ms must be zero or greater")
        if thread_pool is not None and not isinstance(thread_pool, QThreadPool):
            raise TypeError("thread_pool must be a QThreadPool or None")

        super().__init__(parent)
        self._highlighter = highlighter
        self._service = service
        self._debounce_ms = debounce_ms
        selected_pool = thread_pool or QThreadPool.globalInstance()
        if selected_pool is None:
            raise RuntimeError("Qt did not provide a global thread pool")
        self._thread_pool: QThreadPool = selected_pool
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.flush)
        self._document: QTextDocument | None = None
        self._pending: set[str] = set()
        self._inflight: set[str] = set()
        self._cancelled: Event | None = None
        self._generation = 0
        self._enabled = True
        self._busy = False
        self._jobs_started = 0
        self._jobs_finished = 0
        self._lifetime_guard_ref: weakref.ReferenceType[QObject] | None = None
        highlighter.unknown_words_found.connect(self.request_words)

    @property
    def debounce_ms(self) -> int:
        return self._debounce_ms

    @property
    def generation(self) -> int:
        return self._generation

    @property
    def busy(self) -> bool:
        return self._busy

    @property
    def jobs_started(self) -> int:
        return self._jobs_started

    @property
    def jobs_finished(self) -> int:
        return self._jobs_finished

    @property
    def pending_word_count(self) -> int:
        return len(self._pending)

    def set_document(self, document: QTextDocument | None) -> bool:
        if document is not None and not isinstance(document, QTextDocument):
            raise TypeError("document must be a QTextDocument or None")
        if document is self._document:
            return False
        if self._document is not None:
            try:
                self._document.contentsChange.disconnect(self._on_document_change)
                self._document.destroyed.disconnect(self._on_document_destroyed)
            except (RuntimeError, TypeError):
                pass
        self.cancel(clear_pending=True)
        self._document = document
        if document is not None:
            document.contentsChange.connect(self._on_document_change)
            document.destroyed.connect(self._on_document_destroyed)
        return True

    def set_lifetime_guard(self, guard: QObject | None) -> None:
        """Retain the editor only inside queued result events, never permanently."""
        if guard is not None and not isinstance(guard, QObject):
            raise TypeError("guard must be a QObject or None")
        self._lifetime_guard_ref = None if guard is None else weakref.ref(guard)

    def set_enabled(self, enabled: bool) -> bool:
        if not isinstance(enabled, bool):
            raise TypeError("enabled must be a boolean")
        if enabled == self._enabled:
            return False
        self._enabled = enabled
        if not enabled:
            self.cancel(clear_pending=True)
        else:
            self._highlighter.rehighlight()
        return True

    def request_words(self, words: Iterable[str]) -> int:
        """Queue normalized unique words and restart the debounce interval."""
        if isinstance(words, (str, bytes)):
            raise TypeError("words must be an iterable of strings")
        normalized: set[str] = set()
        for word in words:
            if not isinstance(word, str):
                raise TypeError("words must contain only strings")
            if word:
                normalized.add(unicodedata.normalize("NFC", word))
        if not normalized or not self._enabled or self._document is None:
            return 0
        self._supersede_active()
        self._pending.update(normalized)
        self._generation += 1
        self._timer.start(self._debounce_ms)
        return len(normalized)

    def flush(self) -> bool:
        """Start one pooled batch immediately when pending work exists."""
        if not self._enabled or self._document is None or not self._pending:
            return False
        words = tuple(sorted(self._pending))
        self._pending.clear()
        generation = self._generation
        locale = self._highlighter.language
        cancelled = Event()
        self._cancelled = cancelled
        self._inflight = set(words)
        worker = _SpellCheckBatch(
            generation,
            locale,
            words,
            self._service,
            cancelled,
            self._lifetime_guard(),
        )
        worker.signals.completed.connect(self._on_completed)
        self._set_busy(True)
        self._jobs_started += 1
        self.job_started.emit(generation, len(words))
        self._thread_pool.start(worker)
        return True

    def cancel(self, *, clear_pending: bool = False) -> bool:
        if not isinstance(clear_pending, bool):
            raise TypeError("clear_pending must be a boolean")
        self._timer.stop()
        had_work = bool(self._pending or self._inflight or self._busy)
        if self._cancelled is not None:
            self._cancelled.set()
        self._generation += 1
        self._inflight.clear()
        if clear_pending:
            self._pending.clear()
        self._set_busy(False)
        return had_work

    def _on_document_change(self, *_change: object) -> None:
        self._supersede_active()
        self._generation += 1
        if self._pending:
            self._timer.start(self._debounce_ms)

    def _on_document_destroyed(self, *_document: object) -> None:
        self.cancel(clear_pending=True)
        self._document = None

    def _supersede_active(self) -> None:
        if self._cancelled is not None and self._busy:
            self._cancelled.set()
            self._pending.update(self._inflight)
            self._inflight.clear()
            self._set_busy(False)

    def _on_completed(
        self,
        generation: int,
        locale: str,
        results: object,
        was_cancelled: bool,
        _lifetime_guard: object,
        error: object,
    ) -> None:
        if (
            was_cancelled
            or generation != self._generation
            or locale != self._highlighter.language
            or self._document is None
            or sip.isdeleted(self._document)
            or sip.isdeleted(self._highlighter)
        ):
            self.results_discarded.emit(generation)
            return
        self._inflight.clear()
        self._cancelled = None
        if error is not None:
            self._jobs_finished += 1
            self.job_failed.emit(generation, error)
            self._set_busy(False)
            if self._pending:
                self._timer.start(self._debounce_ms)
            return
        applied = self._highlighter.apply_statuses(locale, results)
        self._jobs_finished += 1
        self.job_finished.emit(generation, applied)
        self._set_busy(False)
        if self._pending:
            self._timer.start(self._debounce_ms)

    def _lifetime_guard(self) -> object:
        if self._lifetime_guard_ref is None:
            return self._document
        return self._lifetime_guard_ref()

    def _set_busy(self, busy: bool) -> None:
        if busy != self._busy:
            self._busy = busy
            self.idle_changed.emit(not busy)


__all__ = ["AsyncSpellCheckController"]
