"""Reusable, source-aware dictionary manager for PyQt6 applications."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from pyqt6_linguistic_tools.catalog import DictionaryCatalog, DictionaryCatalogEntry
from pyqt6_linguistic_tools.locales import locale_display_name
from pyqt6_linguistic_tools.models import DictionaryImportResult, DictionaryInfo
from pyqt6_linguistic_tools.providers import (
    ManagedDictionaryProvider,
    UserDictionaryProvider,
)
from pyqt6_linguistic_tools.service import LinguisticService
from pyqt6_linguistic_tools.qt._compat import require_pyqt6


require_pyqt6()

from PyQt6.QtCore import (  # noqa: E402
    QCoreApplication,
    QObject,
    QRunnable,
    QThreadPool,
    Qt,
    pyqtSignal,
)
from PyQt6.QtWidgets import (  # noqa: E402
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


_TRANSLATION_CONTEXT = "PyQt6LinguisticTools.DictionaryManager"
_VALUE_ROLE = int(Qt.ItemDataRole.UserRole)


def _tr(text: str) -> str:
    return QCoreApplication.translate(_TRANSLATION_CONTEXT, text)


class _ImportSignals(QObject):
    completed = pyqtSignal(object, object)


class _ImportTask(QRunnable):
    def __init__(
        self,
        provider: UserDictionaryProvider,
        files: tuple[Path, ...],
        bundle_name: str | None,
    ) -> None:
        super().__init__()
        self._provider = provider
        self._files = files
        self._bundle_name = bundle_name
        self.signals = _ImportSignals()

    def run(self) -> None:
        result: DictionaryImportResult | None = None
        error: Exception | None = None
        try:
            result = self._provider.import_validated_files(
                self._files,
                bundle_name=self._bundle_name,
            )
        except Exception as caught:  # Report engine and filesystem errors to Qt.
            error = caught
        self.signals.completed.emit(result, error)


class DictionaryManagerDialog(QDialog):
    """Inspect dictionaries and manage only application-owned bundles."""

    dictionaries_changed = pyqtSignal(object)
    import_started = pyqtSignal()
    import_finished = pyqtSignal(object)
    operation_failed = pyqtSignal(str, object)
    busy_changed = pyqtSignal(bool)
    download_requested = pyqtSignal(object)

    def __init__(
        self,
        service: LinguisticService,
        *,
        user_provider: UserDictionaryProvider | None = None,
        managed_provider: ManagedDictionaryProvider | None = None,
        catalog: DictionaryCatalog | None = None,
        thread_pool: QThreadPool | None = None,
        parent: QWidget | None = None,
    ) -> None:
        if not isinstance(service, LinguisticService):
            raise TypeError("service must be a LinguisticService")
        if user_provider is not None and not isinstance(
            user_provider, UserDictionaryProvider
        ):
            raise TypeError("user_provider must be a UserDictionaryProvider")
        if managed_provider is not None and not isinstance(
            managed_provider, ManagedDictionaryProvider
        ):
            raise TypeError("managed_provider must be a ManagedDictionaryProvider")
        if catalog is not None and not isinstance(catalog, DictionaryCatalog):
            raise TypeError("catalog must be a DictionaryCatalog or None")
        if thread_pool is not None and not isinstance(thread_pool, QThreadPool):
            raise TypeError("thread_pool must be a QThreadPool or None")

        super().__init__(parent)
        self._service = service
        providers = service.registry.providers()
        self._user_provider = user_provider or next(
            (item for item in providers if isinstance(item, UserDictionaryProvider)),
            None,
        )
        self._managed_provider = managed_provider or next(
            (
                item
                for item in providers
                if isinstance(item, ManagedDictionaryProvider)
            ),
            None,
        )
        self._catalog = catalog
        selected_pool = thread_pool or QThreadPool.globalInstance()
        if selected_pool is None:
            raise RuntimeError("Qt did not provide a global thread pool")
        self._thread_pool: QThreadPool = selected_pool
        self._entries: dict[str, DictionaryInfo] = {}
        self._catalog_entries: dict[str, DictionaryCatalogEntry] = {}
        self._workers: set[_ImportTask] = set()
        self._busy = False

        self.setWindowTitle(_tr("Dictionary Manager"))
        self.resize(820, 560)
        self._create_widgets()
        self._populate_installed(
            self._service.registry.discover(tolerate_provider_errors=True)
        )
        self._populate_catalog()

    @property
    def service(self) -> LinguisticService:
        return self._service

    @property
    def busy(self) -> bool:
        return self._busy

    @property
    def selected_dictionary(self) -> DictionaryInfo | None:
        item = self.installed_tree.currentItem()
        if item is None:
            return None
        key = item.data(0, _VALUE_ROLE)
        return self._entries.get(key) if isinstance(key, str) else None

    @property
    def selected_catalog_entry(self) -> DictionaryCatalogEntry | None:
        item = self.catalog_tree.currentItem()
        if item is None:
            return None
        code = item.data(0, _VALUE_ROLE)
        return self._catalog_entries.get(code) if isinstance(code, str) else None

    def refresh(self) -> tuple[DictionaryInfo, ...]:
        """Rediscover providers, clear obsolete backends, and rebuild the view."""
        self._service.refresh_dictionaries()
        entries = self._service.registry.discover(tolerate_provider_errors=True)
        self._populate_installed(entries)
        self.dictionaries_changed.emit(entries)
        return entries

    def import_files(
        self,
        files: Sequence[str | Path],
        *,
        bundle_name: str | None = None,
    ) -> bool:
        """Validate and import files in a worker, never on the GUI thread."""
        if self._user_provider is None:
            raise RuntimeError("no user dictionary provider is configured")
        if self._busy:
            return False
        paths = tuple(Path(path).expanduser().resolve() for path in files)
        if not paths:
            return False
        worker = _ImportTask(self._user_provider, paths, bundle_name)
        self._workers.add(worker)
        worker.signals.completed.connect(
            lambda result, error, task=worker: self._on_import_completed(
                task, result, error
            )
        )
        self._set_busy(True)
        self.import_started.emit()
        self._thread_pool.start(worker)
        return True

    def remove_selected(self, *, confirm: bool = True) -> bool:
        """Remove selected managed/user bundles after an optional confirmation."""
        if not isinstance(confirm, bool):
            raise TypeError("confirm must be a boolean")
        info = self.selected_dictionary
        if info is None:
            return False
        bundles = self._owned_bundles(info)
        if not bundles:
            return False
        if confirm:
            names = ", ".join(sorted(name for _provider, name in bundles))
            answer = QMessageBox.question(
                self,
                _tr("Remove Dictionary"),
                _tr("Remove the selected application-owned bundle(s): %1?").replace(
                    "%1", names
                ),
            )
            if answer != QMessageBox.StandardButton.Yes:
                return False
        try:
            changed = False
            for provider, bundle_name in bundles:
                changed = provider.remove_bundle(bundle_name) or changed
            if changed:
                self.refresh()
            return changed
        except Exception as error:
            self._report_error(_tr("Dictionary removal failed"), error)
            return False

    def _create_widgets(self) -> None:
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget(self)
        layout.addWidget(self.tabs, 1)

        installed_page = QWidget(self)
        installed_layout = QVBoxLayout(installed_page)
        self.installed_tree = QTreeWidget(installed_page)
        self.installed_tree.setHeaderLabels(
            (
                _tr("Language"),
                _tr("Locale"),
                _tr("Spelling"),
                _tr("Thesaurus"),
                _tr("Source"),
            )
        )
        self.installed_tree.setRootIsDecorated(False)
        installed_layout.addWidget(self.installed_tree, 1)
        self.details = QPlainTextEdit(installed_page)
        self.details.setReadOnly(True)
        self.details.setVisible(False)
        installed_layout.addWidget(self.details)
        installed_actions = QHBoxLayout()
        self.refresh_button = QPushButton(_tr("Refresh"), installed_page)
        self.import_button = QPushButton(_tr("Import Files…"), installed_page)
        self.remove_button = QPushButton(_tr("Remove Selected"), installed_page)
        self.details_button = QPushButton(_tr("Show Details"), installed_page)
        self.details_button.setCheckable(True)
        installed_actions.addWidget(self.refresh_button)
        installed_actions.addWidget(self.import_button)
        installed_actions.addWidget(self.remove_button)
        installed_actions.addStretch(1)
        installed_actions.addWidget(self.details_button)
        installed_layout.addLayout(installed_actions)
        self.tabs.addTab(installed_page, _tr("Installed"))

        catalog_page = QWidget(self)
        catalog_layout = QVBoxLayout(catalog_page)
        self.catalog_notice = QLabel(catalog_page)
        self.catalog_notice.setWordWrap(True)
        catalog_layout.addWidget(self.catalog_notice)
        self.catalog_tree = QTreeWidget(catalog_page)
        self.catalog_tree.setHeaderLabels(
            (_tr("Language"), _tr("Code"), _tr("Size"), _tr("Verification"))
        )
        self.catalog_tree.setRootIsDecorated(False)
        catalog_layout.addWidget(self.catalog_tree, 1)
        catalog_actions = QHBoxLayout()
        catalog_actions.addStretch(1)
        self.download_button = QPushButton(_tr("Download…"), catalog_page)
        catalog_actions.addWidget(self.download_button)
        catalog_layout.addLayout(catalog_actions)
        self.tabs.addTab(catalog_page, _tr("Available Downloads"))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.refresh_button.clicked.connect(self._refresh_from_ui)
        self.import_button.clicked.connect(self._choose_import_files)
        self.remove_button.clicked.connect(
            lambda _checked=False: self.remove_selected()
        )
        self.details_button.toggled.connect(self._toggle_details)
        self.installed_tree.itemSelectionChanged.connect(
            self._update_installed_selection
        )
        self.catalog_tree.itemSelectionChanged.connect(self._update_catalog_selection)
        self.download_button.clicked.connect(self._request_download)

        self.import_button.setEnabled(self._user_provider is not None)
        self.remove_button.setEnabled(False)
        self.download_button.setEnabled(False)

    def _populate_installed(self, entries: tuple[DictionaryInfo, ...]) -> None:
        self.installed_tree.clear()
        rows: list[tuple[str, DictionaryInfo, bool]] = [
            (f"effective:{entry.locale}", entry, True) for entry in entries
        ]
        rows.extend(self._hidden_owned_entries(entries))
        self._entries = {key: entry for key, entry, _active in rows}
        for key, entry, active in rows:
            spelling_failure = (
                self._service.component_failure(entry.locale, "spelling")
                if active
                else None
            )
            thesaurus_failure = (
                self._service.component_failure(entry.locale, "thesaurus")
                if active
                else None
            )
            sources = []
            if entry.spelling_source:
                sources.append(f"{_tr('Spelling')}: {entry.spelling_source}")
            if entry.thesaurus_source:
                sources.append(f"{_tr('Thesaurus')}: {entry.thesaurus_source}")
            item = QTreeWidgetItem(
                (
                    (
                        entry.display_name
                        if active
                        else f"{entry.display_name} ({_tr('Inactive')})"
                    ),
                    entry.locale,
                    (
                        _tr("Failed")
                        if spelling_failure is not None
                        else (
                            _tr("Available")
                            if entry.has_spelling
                            else _tr("Missing")
                        )
                    ),
                    (
                        _tr("Failed")
                        if thesaurus_failure is not None
                        else (
                            _tr("Available")
                            if entry.has_thesaurus
                            else _tr("Missing")
                        )
                    ),
                    "; ".join(sources),
                )
            )
            item.setData(0, _VALUE_ROLE, key)
            self.installed_tree.addTopLevelItem(item)
        for column in range(self.installed_tree.columnCount()):
            self.installed_tree.resizeColumnToContents(column)
        self._update_installed_selection()

    def _hidden_owned_entries(
        self, effective: tuple[DictionaryInfo, ...]
    ) -> list[tuple[str, DictionaryInfo, bool]]:
        active_paths = {
            path.absolute()
            for entry in effective
            for path in (
                entry.aff_path,
                entry.dic_path,
                entry.thesaurus_dat,
                entry.thesaurus_idx,
            )
            if path is not None
        }
        rows: list[tuple[str, DictionaryInfo, bool]] = []
        position = 0
        for provider in (self._managed_provider, self._user_provider):
            if provider is None:
                continue
            try:
                candidates = provider.discover()
            except Exception:
                continue
            for candidate in candidates:
                paths = tuple(
                    path
                    for path in (
                        candidate.aff_path,
                        candidate.dic_path,
                        candidate.thesaurus_dat,
                        candidate.thesaurus_idx,
                    )
                    if path is not None
                )
                if paths and all(path.absolute() in active_paths for path in paths):
                    continue
                entry = DictionaryInfo(
                    locale=candidate.locale,
                    display_name=locale_display_name(candidate.locale),
                    aff_path=candidate.aff_path,
                    dic_path=candidate.dic_path,
                    thesaurus_dat=candidate.thesaurus_dat,
                    thesaurus_idx=candidate.thesaurus_idx,
                    spelling_source=(
                        candidate.source if candidate.has_spelling else None
                    ),
                    thesaurus_source=(
                        candidate.source if candidate.has_thesaurus else None
                    ),
                    spelling_locale=(
                        candidate.locale if candidate.has_spelling else None
                    ),
                    thesaurus_locale=(
                        candidate.locale if candidate.has_thesaurus else None
                    ),
                )
                key = f"inactive:{candidate.source}:{candidate.locale}:{position}"
                rows.append((key, entry, False))
                position += 1
        return rows

    def _populate_catalog(self) -> None:
        self.catalog_tree.clear()
        self._catalog_entries.clear()
        if self._catalog is None:
            self.catalog_notice.setText(_tr("No download catalog is configured."))
            return
        for entry in self._catalog.dictionaries:
            self._catalog_entries[entry.code] = entry
            item = QTreeWidgetItem(
                (
                    entry.name,
                    entry.code,
                    self._format_size(entry.size),
                    _tr("SHA-256") if entry.sha256 else _tr("Unverified"),
                )
            )
            item.setData(0, _VALUE_ROLE, entry.code)
            self.catalog_tree.addTopLevelItem(item)
        self.catalog_notice.setText(
            _tr(
                "Downloads are delegated to the host application and require "
                "a catalog SHA-256 checksum before installation."
            )
        )
        for column in range(self.catalog_tree.columnCount()):
            self.catalog_tree.resizeColumnToContents(column)

    def _update_installed_selection(self) -> None:
        info = self.selected_dictionary
        removable = bool(info is not None and self._owned_bundles(info))
        self.remove_button.setEnabled(removable and not self._busy)
        if info is None:
            self.details.clear()
            return
        lines = [
            f"{_tr('Language')}: {info.display_name}",
            f"{_tr('Locale')}: {info.locale}",
            f"{_tr('Spelling source')}: {info.spelling_source or '-'}",
            f"{_tr('Spelling .aff')}: {info.aff_path or '-'}",
            f"{_tr('Spelling .dic')}: {info.dic_path or '-'}",
            f"{_tr('Thesaurus source')}: {info.thesaurus_source or '-'}",
            f"{_tr('Thesaurus .dat')}: {info.thesaurus_dat or '-'}",
            f"{_tr('Thesaurus .idx')}: {info.thesaurus_idx or '-'}",
        ]
        for component in ("spelling", "thesaurus"):
            failure = self._service.component_failure(info.locale, component)
            if failure is not None:
                lines.append(
                    f"{_tr('Failure')} ({component}): "
                    f"{failure.diagnostic.message}"
                )
        self.details.setPlainText("\n".join(lines))

    def _update_catalog_selection(self) -> None:
        entry = self.selected_catalog_entry
        verified = entry is not None and entry.sha256 is not None
        self.download_button.setEnabled(verified and not self._busy)
        self.download_button.setToolTip(
            ""
            if verified
            else _tr("Downloads require a SHA-256 checksum in the catalog.")
        )

    def _owned_bundles(
        self, info: DictionaryInfo
    ) -> tuple[tuple[ManagedDictionaryProvider | UserDictionaryProvider, str], ...]:
        owned: set[
            tuple[ManagedDictionaryProvider | UserDictionaryProvider, str]
        ] = set()
        components = (
            (info.spelling_source, info.aff_path),
            (info.spelling_source, info.dic_path),
            (info.thesaurus_source, info.thesaurus_dat),
            (info.thesaurus_source, info.thesaurus_idx),
        )
        for provider in (self._managed_provider, self._user_provider):
            if provider is None:
                continue
            for source, path in components:
                if source != provider.source or path is None:
                    continue
                try:
                    relative = path.absolute().relative_to(provider.root.absolute())
                except ValueError:
                    continue
                if len(relative.parts) >= 2:
                    owned.add((provider, relative.parts[0]))
        return tuple(sorted(owned, key=lambda item: (item[0].source, item[1])))

    def _choose_import_files(self) -> None:
        filenames, _selected_filter = QFileDialog.getOpenFileNames(
            self,
            _tr("Import Dictionary Files"),
            "",
            _tr("Dictionary files (*.aff *.dic *.dat *.idx)"),
        )
        if filenames:
            self.import_files(filenames)

    def _on_import_completed(
        self,
        worker: _ImportTask,
        result: object,
        error: object,
    ) -> None:
        self._workers.discard(worker)
        self._set_busy(False)
        if isinstance(error, Exception):
            self._report_error(_tr("Dictionary import failed"), error)
            return
        if not isinstance(result, DictionaryImportResult):
            self._report_error(
                _tr("Dictionary import failed"),
                RuntimeError("dictionary import returned no result"),
            )
            return
        self.refresh()
        self.import_finished.emit(result)

    def _refresh_from_ui(self) -> None:
        try:
            self.refresh()
        except Exception as error:
            self._report_error(_tr("Dictionary refresh failed"), error)

    def _report_error(self, title: str, error: Exception) -> None:
        self.operation_failed.emit(title, error)
        QMessageBox.warning(self, title, str(error))

    def _set_busy(self, busy: bool) -> None:
        if busy == self._busy:
            return
        self._busy = busy
        self.refresh_button.setEnabled(not busy)
        self.import_button.setEnabled(not busy and self._user_provider is not None)
        self._update_installed_selection()
        self._update_catalog_selection()
        self.busy_changed.emit(busy)

    def _toggle_details(self, visible: bool) -> None:
        self.details.setVisible(visible)
        self.details_button.setText(
            _tr("Hide Details") if visible else _tr("Show Details")
        )

    def _request_download(self) -> None:
        entry = self.selected_catalog_entry
        if entry is not None and entry.sha256 is not None:
            self.download_requested.emit(entry)

    @staticmethod
    def _format_size(size: int) -> str:
        value = float(size)
        for unit in ("B", "KiB", "MiB", "GiB"):
            if value < 1024 or unit == "GiB":
                if unit == "B":
                    return f"{value:.0f} {unit}"
                return f"{value:.1f} {unit}"
            value /= 1024
        return f"{size} B"


__all__ = ["DictionaryManagerDialog"]
