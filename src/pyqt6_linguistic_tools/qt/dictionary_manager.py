"""Embeddable, source-aware dictionary manager for PyQt6 applications."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
import unicodedata

from pyqt6_linguistic_tools.catalog import DictionaryCatalog, DictionaryCatalogEntry
from pyqt6_linguistic_tools.locales import locale_display_name
from pyqt6_linguistic_tools.models import DictionaryImportResult, DictionaryInfo
from pyqt6_linguistic_tools.providers import (
    ManagedDictionaryProvider,
    UserDictionaryProvider,
)
from pyqt6_linguistic_tools.qt._compat import require_pyqt6
from pyqt6_linguistic_tools.service import LinguisticService


require_pyqt6()

from PyQt6.QtCore import (  # noqa: E402
    QObject,
    QRunnable,
    QThreadPool,
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import QFont, QKeySequence, QShortcut  # noqa: E402
from PyQt6.QtWidgets import (  # noqa: E402
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


_ROW_ROLE = int(Qt.ItemDataRole.UserRole)


def _fold(value: str) -> str:
    """Case- and accent-insensitive comparison text."""
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_text = decomposed.encode("ascii", "ignore").decode("ascii")
    return ascii_text.casefold()


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


@dataclass(slots=True)
class _ManagerRow:
    key: str
    info: DictionaryInfo | None = None
    catalog_entry: DictionaryCatalogEntry | None = None
    installed: bool = False
    installed_locales: tuple[str, ...] = ()


class DictionaryManagerWidget(QWidget):
    """Embeddable dictionary manager with search, filters and details.

    The widget can be placed in any layout, settings page, tab or dialog. It
    never performs network access or archive extraction: verified downloads are
    requested through :attr:`download_requested`; the host publishes the bundle
    and then calls :meth:`refresh`.
    """

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
            (item for item in providers if isinstance(item, ManagedDictionaryProvider)),
            None,
        )
        self._catalog = catalog
        selected_pool = thread_pool or QThreadPool.globalInstance()
        if selected_pool is None:
            raise RuntimeError("Qt did not provide a global thread pool")
        self._thread_pool: QThreadPool = selected_pool
        self._workers: set[_ImportTask] = set()
        self._entries: dict[str, DictionaryInfo] = {}
        self._catalog_entries: dict[str, DictionaryCatalogEntry] = {}
        self._installed_group: QTreeWidgetItem | None = None
        self._catalog_group: QTreeWidgetItem | None = None
        self._busy = False

        self.setMinimumSize(880, 520)
        self._create_widgets()
        self._populate()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def service(self) -> LinguisticService:
        return self._service

    @property
    def busy(self) -> bool:
        return self._busy

    @property
    def selected_dictionary(self) -> DictionaryInfo | None:
        row = self._selected_row()
        return row.info if row is not None else None

    @property
    def selected_catalog_entry(self) -> DictionaryCatalogEntry | None:
        row = self._selected_row()
        return row.catalog_entry if row is not None else None

    @property
    def catalog(self) -> DictionaryCatalog | None:
        return self._catalog

    def set_catalog(self, catalog: DictionaryCatalog | None) -> None:
        """Replace the download catalog and rebuild the available list."""
        if catalog is not None and not isinstance(catalog, DictionaryCatalog):
            raise TypeError("catalog must be a DictionaryCatalog or None")
        self._catalog = catalog
        self._populate()

    def refresh(self) -> tuple[DictionaryInfo, ...]:
        """Rediscover providers, clear obsolete backends, and rebuild the view."""
        self._service.refresh_dictionaries()
        entries = self._service.registry.discover(tolerate_provider_errors=True)
        self._populate(entries)
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
                self.tr("Remove Dictionary"),
                self.tr("Remove the selected application-owned bundle(s): %1?").replace(
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
            self._report_error(self.tr("Dictionary removal failed"), error)
            return False

    # ------------------------------------------------------------------
    # Widget construction
    # ------------------------------------------------------------------

    def _create_widgets(self) -> None:
        self._text = {
            "title": self.tr("Dictionary Manager"),
            "subtitle": self.tr(
                "Download, import and remove spelling and thesaurus bundles."
            ),
            "refresh": self.tr("Refresh"),
            "import": self.tr("Import Files…"),
            "search": self.tr("Search language, code or locale…"),
            "show": self.tr("Show:"),
            "all": self.tr("All dictionaries"),
            "only_installed": self.tr("Installed"),
            "only_available": self.tr("Not installed"),
            "all_components": self.tr("All components"),
            "both": self.tr("Spelling + thesaurus"),
            "spelling_only": self.tr("Spelling only"),
            "thesaurus_only": self.tr("Thesaurus only"),
            "none": self.tr("No components"),
            "installed_group": self.tr("Installed dictionaries"),
            "available_group": self.tr("Available downloads"),
            "language": self.tr("Language"),
            "code": self.tr("Code"),
            "spelling": self.tr("Spelling"),
            "thesaurus": self.tr("Thesaurus"),
            "size": self.tr("Size"),
            "status": self.tr("Status"),
            "source": self.tr("Source"),
            "install": self.tr("Install"),
            "remove": self.tr("Remove"),
            "close": self.tr("Close"),
            "details": self.tr("Details"),
            "yes": self.tr("Yes"),
            "no": self.tr("No"),
            "unknown": self.tr("Unknown"),
            "available": self.tr("Available"),
            "installed": self.tr("Installed"),
            "inactive": self.tr("Inactive"),
            "unverified": self.tr("Unverified"),
            "no_components": self.tr("No components"),
            "verified": self.tr("SHA-256 verified"),
            "catalog": self.tr("Catalog"),
            "ready": self.tr("Select a dictionary to see its details."),
        }

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        header = QHBoxLayout()
        heading = QVBoxLayout()
        title = QLabel(self._text["title"], self)
        title_font = QFont(title.font())
        title_font.setPointSizeF(title_font.pointSizeF() + 4)
        title_font.setBold(True)
        title.setFont(title_font)
        heading.addWidget(title)
        subtitle = QLabel(self._text["subtitle"], self)
        subtitle.setWordWrap(True)
        heading.addWidget(subtitle)
        header.addLayout(heading, 1)
        self.refresh_button = QPushButton(self._text["refresh"], self)
        self.import_button = QPushButton(self._text["import"], self)
        header.addWidget(self.refresh_button)
        header.addWidget(self.import_button)
        layout.addLayout(header)

        search_row = QHBoxLayout()
        self.search_edit = QLineEdit(self)
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setPlaceholderText(self._text["search"])
        search_row.addWidget(self.search_edit, 1)
        search_row.addWidget(QLabel(self._text["show"], self))
        self.status_filter = QComboBox(self)
        self.status_filter.addItem(self._text["all"], "all")
        self.status_filter.addItem(self._text["only_installed"], "installed")
        self.status_filter.addItem(self._text["only_available"], "available")
        self.component_filter = QComboBox(self)
        self.component_filter.addItem(self._text["all_components"], "all")
        self.component_filter.addItem(self._text["both"], "both")
        self.component_filter.addItem(self._text["spelling_only"], "spelling")
        self.component_filter.addItem(self._text["thesaurus_only"], "thesaurus")
        self.component_filter.addItem(self._text["none"], "none")
        search_row.addWidget(self.status_filter)
        search_row.addWidget(self.component_filter)
        layout.addLayout(search_row)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.entries_tree = QTreeWidget(splitter)
        self.entries_tree.setHeaderLabels(
            (
                self._text["language"],
                self._text["code"],
                self._text["spelling"],
                self._text["thesaurus"],
                self._text["size"],
                self._text["status"],
                self._text["source"],
            )
        )
        self.entries_tree.setRootIsDecorated(True)
        self.entries_tree.setAlternatingRowColors(True)
        self.entries_tree.setUniformRowHeights(True)
        self.entries_tree.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        splitter.addWidget(self.entries_tree)

        details_panel = QWidget(splitter)
        details_layout = QVBoxLayout(details_panel)
        details_layout.setContentsMargins(12, 0, 0, 0)
        self.details_title = QLabel(details_panel)
        details_title_font = QFont(self.details_title.font())
        details_title_font.setBold(True)
        details_title_font.setPointSizeF(details_title_font.pointSizeF() + 2)
        self.details_title.setFont(details_title_font)
        self.details_title.setWordWrap(True)
        details_layout.addWidget(self.details_title)
        self.details_subtitle = QLabel(details_panel)
        self.details_subtitle.setWordWrap(True)
        details_layout.addWidget(self.details_subtitle)
        self.details = QPlainTextEdit(details_panel)
        self.details.setReadOnly(True)
        details_layout.addWidget(self.details, 1)
        self.progress_bar = QProgressBar(details_panel)
        self.progress_bar.setVisible(False)
        details_layout.addWidget(self.progress_bar)
        self.status_label = QLabel(self._text["ready"], details_panel)
        self.status_label.setWordWrap(True)
        details_layout.addWidget(self.status_label)
        actions = QHBoxLayout()
        self.install_button = QPushButton(self._text["install"], details_panel)
        self.remove_button = QPushButton(self._text["remove"], details_panel)
        actions.addWidget(self.install_button)
        actions.addWidget(self.remove_button)
        actions.addStretch(1)
        details_layout.addLayout(actions)
        splitter.addWidget(details_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([720, 400])
        layout.addWidget(splitter, 1)

        self.summary_label = QLabel(self)
        layout.addWidget(self.summary_label)

        self.install_button.clicked.connect(self._request_install)
        self.remove_button.clicked.connect(
            lambda _checked=False: self.remove_selected()
        )
        self.refresh_button.clicked.connect(self._refresh_from_ui)
        self.import_button.clicked.connect(self._choose_import_files)
        self.entries_tree.currentItemChanged.connect(self._update_selection)
        self.search_edit.textChanged.connect(self._apply_filters)
        self.status_filter.currentIndexChanged.connect(self._apply_filters)
        self.component_filter.currentIndexChanged.connect(self._apply_filters)

        find_shortcut = QShortcut(QKeySequence.StandardKey.Find, self)
        find_shortcut.activated.connect(self.search_edit.setFocus)
        self._find_shortcut = find_shortcut

        self.import_button.setEnabled(self._user_provider is not None)
        self.install_button.setEnabled(False)
        self.remove_button.setEnabled(False)

    # ------------------------------------------------------------------
    # Population
    # ------------------------------------------------------------------

    def _populate(
        self,
        entries: tuple[DictionaryInfo, ...] | None = None,
    ) -> None:
        if entries is None:
            entries = self._service.registry.discover(tolerate_provider_errors=True)
        self.entries_tree.clear()
        installed_rows: list[tuple[str, DictionaryInfo, bool]] = [
            (f"effective:{entry.locale}", entry, True) for entry in entries
        ]
        installed_rows.extend(self._hidden_owned_entries(entries))
        self._entries = {key: info for key, info, _active in installed_rows}

        self._installed_group = QTreeWidgetItem((self._text["installed_group"],))
        self._installed_group.setFirstColumnSpanned(True)
        self._installed_group.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self._bold(self._installed_group, 0)
        for key, info, active in installed_rows:
            item = self._installed_item(key, info, active)
            self._installed_group.addChild(item)
        self._installed_group.sortChildren(0, Qt.SortOrder.AscendingOrder)
        self.entries_tree.addTopLevelItem(self._installed_group)

        self._catalog_group = QTreeWidgetItem((self._text["available_group"],))
        self._catalog_group.setFirstColumnSpanned(True)
        self._catalog_group.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self._bold(self._catalog_group, 0)
        self._catalog_entries.clear()
        if self._catalog is not None:
            for entry in self._catalog.dictionaries:
                self._catalog_entries[entry.code] = entry
                item = self._catalog_item(entry)
                self._catalog_group.addChild(item)
        self._catalog_group.sortChildren(0, Qt.SortOrder.AscendingOrder)
        self.entries_tree.addTopLevelItem(self._catalog_group)

        for column, width in enumerate((220, 70, 70, 85, 70, 120)):
            self.entries_tree.setColumnWidth(column, width)
        header = self.entries_tree.header()
        if header is not None:
            header.setStretchLastSection(True)
        self._installed_group.setExpanded(True)
        self._catalog_group.setExpanded(True)
        self._update_summary()
        self._apply_filters()
        self._clear_details()

    def _installed_item(
        self,
        key: str,
        info: DictionaryInfo,
        active: bool,
    ) -> QTreeWidgetItem:
        spelling_failure = (
            self._service.component_failure(info.locale, "spelling") if active else None
        )
        thesaurus_failure = (
            self._service.component_failure(info.locale, "thesaurus")
            if active
            else None
        )
        sources = sorted(
            {value for value in (info.spelling_source, info.thesaurus_source) if value}
        )
        name = info.display_name
        if not active:
            name = f"{name} ({self._text['inactive']})"
        item = QTreeWidgetItem(
            (
                name,
                info.locale,
                (
                    self._text["yes"]
                    if spelling_failure is None and info.has_spelling
                    else self._text["no"]
                ),
                (
                    self._text["yes"]
                    if thesaurus_failure is None and info.has_thesaurus
                    else self._text["no"]
                ),
                "-",
                self._text["installed"] if active else self._text["inactive"],
                "; ".join(sources) or "-",
            )
        )
        row = _ManagerRow(
            key=key,
            info=info,
            installed=True,
            installed_locales=(info.locale,),
        )
        item.setData(0, _ROW_ROLE, row)
        return item

    def _catalog_item(self, entry: DictionaryCatalogEntry) -> QTreeWidgetItem:
        installed_locales = self._installed_locales_for(entry.code)
        if installed_locales:
            status = self._text["installed"]
        elif entry.spelling is False and entry.thesaurus is False:
            status = self._text["no_components"]
        elif entry.sha256 is None:
            status = self._text["unverified"]
        else:
            status = self._text["available"]
        item = QTreeWidgetItem(
            (
                entry.name,
                entry.code,
                self._flag_text(entry.spelling),
                self._flag_text(entry.thesaurus),
                self._format_size(entry.size),
                status,
                self._text["catalog"],
            )
        )
        row = _ManagerRow(
            key=f"catalog:{entry.code}",
            catalog_entry=entry,
            installed_locales=installed_locales,
        )
        item.setData(0, _ROW_ROLE, row)
        return item

    def _flag_text(self, value: bool | None) -> str:
        if value is True:
            return self._text["yes"]
        if value is False:
            return self._text["no"]
        return self._text["unknown"]

    def _installed_locales_for(self, code: str) -> tuple[str, ...]:
        return tuple(
            sorted(
                info.locale
                for info in self._entries.values()
                if info.locale == code or info.locale.startswith(code + "_")
            )
        )

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

    # ------------------------------------------------------------------
    # Selection and details
    # ------------------------------------------------------------------

    def _selected_row(self) -> _ManagerRow | None:
        item = self.entries_tree.currentItem()
        if item is None:
            return None
        row = item.data(0, _ROW_ROLE)
        return row if isinstance(row, _ManagerRow) else None

    def _update_selection(self, *_args: object) -> None:
        row = self._selected_row()
        if row is None:
            self._clear_details()
            return
        if row.info is not None:
            self._show_installed_details(row.info)
        elif row.catalog_entry is not None:
            self._show_catalog_details(row)
        self._update_actions()

    def _clear_details(self) -> None:
        self.details_title.clear()
        self.details_subtitle.clear()
        self.details.clear()
        self.status_label.setText(self._text["ready"])
        self.install_button.setText(self._text["install"])
        self.install_button.setEnabled(False)
        self.install_button.setToolTip("")
        self.remove_button.setEnabled(False)

    def _show_installed_details(self, info: DictionaryInfo) -> None:
        self.details_title.setText(info.display_name)
        self.details_subtitle.setText(info.locale)
        lines = [
            f"{self._text['language']}: {info.display_name}",
            f"{self._text['code']}: {info.locale}",
            f"{self._text['spelling']}: "
            + (self._text["yes"] if info.has_spelling else self._text["no"]),
            f"{self._text['thesaurus']}: "
            + (self._text["yes"] if info.has_thesaurus else self._text["no"]),
            f"{self._text['source']}: "
            + "; ".join(
                value
                for value in (info.spelling_source, info.thesaurus_source)
                if value
            ),
            "",
            f"{self._text['spelling']} .aff: {info.aff_path or '-'}",
            f"{self._text['spelling']} .dic: {info.dic_path or '-'}",
            f"{self._text['thesaurus']} .dat: {info.thesaurus_dat or '-'}",
            f"{self._text['thesaurus']} .idx: {info.thesaurus_idx or '-'}",
        ]
        for component in ("spelling", "thesaurus"):
            failure = self._service.component_failure(info.locale, component)
            if failure is not None:
                lines.append(f"{component}: {failure.diagnostic.message}")
        self.details.setPlainText("\n".join(lines))
        self.install_button.setText(self._text["installed"])
        self.install_button.setEnabled(False)
        self.install_button.setToolTip("")
        self.status_label.setText(self.tr("Installed dictionary."))

    def _show_catalog_details(self, row: _ManagerRow) -> None:
        entry = row.catalog_entry
        if entry is None:
            return
        self.details_title.setText(entry.name)
        self.details_subtitle.setText(entry.code)
        status = self._text["available"]
        if row.installed_locales:
            status = self._text["installed"]
        elif entry.spelling is False and entry.thesaurus is False:
            status = self._text["no_components"]
        elif entry.sha256 is None:
            status = self._text["unverified"]
        checksum_label = (
            self._text["verified"]
            if entry.sha256 is not None
            else self._text["unverified"]
        )
        lines = [
            f"{self._text['code']}: {entry.code}",
            f"{self._text['size']}: {self._format_size(entry.size)}",
            f"{self._text['status']}: {status}",
            f"{self._text['spelling']}: {self._flag_text(entry.spelling)}",
            f"{self._text['thesaurus']}: {self._flag_text(entry.thesaurus)}",
            f"{checksum_label}: {entry.sha256 or '-'}",
            (
                f"{self._text['source']}: "
                f"{self._catalog.source if self._catalog else '-'}"
            ),
        ]
        if row.installed_locales:
            shown = ", ".join(row.installed_locales[:6])
            if len(row.installed_locales) > 6:
                shown += "…"
            lines.insert(
                3,
                self.tr("Installed locales (%1): %2")
                .replace("%1", str(len(row.installed_locales)))
                .replace("%2", shown),
            )
        self.details.setPlainText("\n".join(lines))
        if row.installed_locales:
            self.install_button.setText(self._text["installed"])
            self.install_button.setEnabled(False)
            self.install_button.setToolTip("")
            self.status_label.setText(self.tr("This bundle is already installed."))
        elif entry.spelling is False and entry.thesaurus is False:
            self.install_button.setText(self._text["no_components"])
            self.install_button.setEnabled(False)
            self.install_button.setToolTip(
                self.tr("This bundle has no spelling or thesaurus files.")
            )
            self.status_label.setText(
                self.tr("No spelling or thesaurus files in this bundle.")
            )
        elif entry.sha256 is None:
            self.install_button.setText(self._text["unverified"])
            self.install_button.setEnabled(False)
            self.install_button.setToolTip(
                self.tr("Downloads require a SHA-256 checksum in the catalog.")
            )
            self.status_label.setText(
                self.tr("Download disabled: the catalog has no SHA-256 checksum.")
            )
        else:
            self.install_button.setText(self._text["install"])
            self.install_button.setEnabled(not self._busy)
            self.install_button.setToolTip("")
            self.status_label.setText(self.tr("Ready to install."))

    def _update_actions(self) -> None:
        row = self._selected_row()
        removable = bool(
            row is not None and row.info is not None and self._owned_bundles(row.info)
        )
        self.remove_button.setEnabled(removable and not self._busy)
        if row is not None and row.catalog_entry is not None:
            entry = row.catalog_entry
            if (
                not row.installed_locales
                and entry.sha256 is not None
                and not (entry.spelling is False and entry.thesaurus is False)
            ):
                self.install_button.setEnabled(not self._busy)

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    def _apply_filters(self, *_args: object) -> None:
        query = _fold(self.search_edit.text().strip())
        status_filter = self.status_filter.currentData()
        component_filter = self.component_filter.currentData()
        for group in (self._installed_group, self._catalog_group):
            if group is None:
                continue
            visible = 0
            for index in range(group.childCount()):
                item = group.child(index)
                if item is None:
                    continue
                row = item.data(0, _ROW_ROLE)
                if not isinstance(row, _ManagerRow):
                    item.setHidden(True)
                    continue
                show = self._row_matches(row, query, status_filter, component_filter)
                item.setHidden(not show)
                if show:
                    visible += 1
            group.setHidden(visible == 0)

    def _row_matches(
        self,
        row: _ManagerRow,
        query: str,
        status_filter: object,
        component_filter: object,
    ) -> bool:
        if query:
            values: list[str] = []
            if row.info is not None:
                values.extend((row.info.display_name, row.info.locale))
            if row.catalog_entry is not None:
                values.extend((row.catalog_entry.name, row.catalog_entry.code))
            if query not in _fold(" ".join(values)):
                return False
        if status_filter == "installed" and not row.installed:
            return False
        if status_filter == "available" and (row.installed or row.installed_locales):
            return False
        spelling, thesaurus = self._row_components(row)
        if component_filter == "both":
            return spelling is True and thesaurus is True
        if component_filter == "spelling":
            return spelling is True and thesaurus is False
        if component_filter == "thesaurus":
            return thesaurus is True and spelling is False
        if component_filter == "none":
            return spelling is False and thesaurus is False
        return True

    def _row_components(self, row: _ManagerRow) -> tuple[bool | None, bool | None]:
        if row.info is not None:
            return bool(row.info.has_spelling), bool(row.info.has_thesaurus)
        if row.catalog_entry is not None:
            return row.catalog_entry.spelling, row.catalog_entry.thesaurus
        return None, None

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _request_install(self) -> None:
        row = self._selected_row()
        if row is None or row.catalog_entry is None:
            return
        entry = row.catalog_entry
        if entry.sha256 is None:
            return
        if entry.spelling is False and entry.thesaurus is False:
            return
        if row.installed_locales:
            return
        self.status_label.setText(
            self.tr(
                "Download requested. The host application installs the bundle "
                "and then refreshes this view."
            )
        )
        self.download_requested.emit(entry)

    def _refresh_from_ui(self) -> None:
        try:
            self.refresh()
        except Exception as error:
            self._report_error(self.tr("Dictionary refresh failed"), error)

    def _choose_import_files(self) -> None:
        filenames, _selected_filter = QFileDialog.getOpenFileNames(
            self,
            self.tr("Import Dictionary Files"),
            "",
            self.tr("Dictionary files (*.aff *.dic *.dat *.idx)"),
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
            self._report_error(self.tr("Dictionary import failed"), error)
            return
        if not isinstance(result, DictionaryImportResult):
            self._report_error(
                self.tr("Dictionary import failed"),
                RuntimeError("dictionary import returned no result"),
            )
            return
        self.refresh()
        self.import_finished.emit(result)

    def _report_error(self, title: str, error: Exception) -> None:
        self.operation_failed.emit(title, error)
        QMessageBox.warning(self, title, str(error))

    def _set_busy(self, busy: bool) -> None:
        if busy == self._busy:
            return
        self._busy = busy
        self.refresh_button.setEnabled(not busy)
        self.import_button.setEnabled(not busy and self._user_provider is not None)
        self.progress_bar.setVisible(busy)
        if busy:
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
        self._update_actions()
        self.busy_changed.emit(busy)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _update_summary(self) -> None:
        installed = sum(1 for _info in self._entries.values())
        available = sum(
            1
            for entry in self._catalog_entries.values()
            if not self._installed_locales_for(entry.code)
        )
        with_thesaurus = sum(
            1 for entry in self._catalog_entries.values() if entry.thesaurus
        )
        self.summary_label.setText(
            self.tr("%1 available · %2 installed · %3 with thesaurus")
            .replace("%1", str(available))
            .replace("%2", str(installed))
            .replace("%3", str(with_thesaurus))
        )

    def _owned_bundles(
        self, info: DictionaryInfo
    ) -> tuple[tuple[ManagedDictionaryProvider | UserDictionaryProvider, str], ...]:
        owned: set[tuple[ManagedDictionaryProvider | UserDictionaryProvider, str]] = (
            set()
        )
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

    @staticmethod
    def _bold(item: QTreeWidgetItem, column: int) -> None:
        font = item.font(column)
        font.setBold(True)
        item.setFont(column, font)

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


class DictionaryManagerDialog(QDialog):
    """Dialog wrapper around :class:`DictionaryManagerWidget`."""

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
        super().__init__(parent)
        self._manager = DictionaryManagerWidget(
            service,
            user_provider=user_provider,
            managed_provider=managed_provider,
            catalog=catalog,
            thread_pool=thread_pool,
            parent=self,
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._manager, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setWindowTitle(self.tr("Dictionary Manager"))
        self.resize(1180, 720)
        self.setMinimumSize(960, 600)

        self._manager.dictionaries_changed.connect(self.dictionaries_changed.emit)
        self._manager.import_started.connect(self.import_started.emit)
        self._manager.import_finished.connect(self.import_finished.emit)
        self._manager.operation_failed.connect(self.operation_failed.emit)
        self._manager.busy_changed.connect(self.busy_changed.emit)
        self._manager.download_requested.connect(self.download_requested.emit)

    @property
    def manager(self) -> DictionaryManagerWidget:
        return self._manager

    @property
    def busy(self) -> bool:
        return self._manager.busy

    @property
    def selected_dictionary(self) -> DictionaryInfo | None:
        return self._manager.selected_dictionary

    @property
    def selected_catalog_entry(self) -> DictionaryCatalogEntry | None:
        return self._manager.selected_catalog_entry

    @property
    def entries_tree(self) -> QTreeWidget:
        return self._manager.entries_tree

    @property
    def details(self) -> QPlainTextEdit:
        return self._manager.details

    @property
    def install_button(self) -> QPushButton:
        return self._manager.install_button

    @property
    def download_button(self) -> QPushButton:
        return self._manager.install_button

    @property
    def remove_button(self) -> QPushButton:
        return self._manager.remove_button

    @property
    def refresh_button(self) -> QPushButton:
        return self._manager.refresh_button

    @property
    def import_button(self) -> QPushButton:
        return self._manager.import_button

    @property
    def search_edit(self) -> QLineEdit:
        return self._manager.search_edit

    @property
    def status_filter(self) -> QComboBox:
        return self._manager.status_filter

    @property
    def component_filter(self) -> QComboBox:
        return self._manager.component_filter

    @property
    def summary_label(self) -> QLabel:
        return self._manager.summary_label

    def refresh(self) -> tuple[DictionaryInfo, ...]:
        return self._manager.refresh()

    def set_catalog(self, catalog: DictionaryCatalog | None) -> None:
        self._manager.set_catalog(catalog)

    def import_files(
        self,
        files: Sequence[str | Path],
        *,
        bundle_name: str | None = None,
    ) -> bool:
        return self._manager.import_files(files, bundle_name=bundle_name)

    def remove_selected(self, *, confirm: bool = True) -> bool:
        return self._manager.remove_selected(confirm=confirm)


__all__ = [
    "DictionaryManagerDialog",
    "DictionaryManagerWidget",
]
