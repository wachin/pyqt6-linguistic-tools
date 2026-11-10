"""Qt worker for verified dictionary downloads."""

from __future__ import annotations

from PyQt6.QtCore import QObject, QRunnable, pyqtSignal

from pyqt6_linguistic_tools.catalog import DictionaryCatalogEntry
from pyqt6_linguistic_tools.download import download_dictionary
from pyqt6_linguistic_tools.errors import DictionaryDownloadCancelled
from pyqt6_linguistic_tools.providers import ManagedDictionaryProvider
from pyqt6_linguistic_tools.qt._compat import require_pyqt6


require_pyqt6()


class DictionaryDownloadSignals(QObject):
    """Signals emitted by :class:`DictionaryDownloadTask`."""

    progress = pyqtSignal(int, int)
    finished = pyqtSignal(object)
    failed = pyqtSignal(str, object)
    cancelled = pyqtSignal()


class DictionaryDownloadTask(QRunnable):
    """Download, verify and install one catalog entry off the GUI thread."""

    def __init__(
        self,
        entry: DictionaryCatalogEntry,
        provider: ManagedDictionaryProvider,
    ) -> None:
        super().__init__()
        self._entry = entry
        self._provider = provider
        self._cancelled = False
        self.signals = DictionaryDownloadSignals()

    @property
    def entry(self) -> DictionaryCatalogEntry:
        return self._entry

    def cancel(self) -> None:
        """Request cancellation at the next download chunk boundary."""
        self._cancelled = True

    def run(self) -> None:
        try:
            result = download_dictionary(
                self._entry,
                self._provider,
                progress=self.signals.progress.emit,
                should_cancel=lambda: self._cancelled,
            )
        except DictionaryDownloadCancelled:
            self.signals.cancelled.emit()
        except Exception as error:  # Report download/validation failures to Qt.
            self.signals.failed.emit(str(error), error)
        else:
            self.signals.finished.emit(result)


__all__ = [
    "DictionaryDownloadSignals",
    "DictionaryDownloadTask",
]
