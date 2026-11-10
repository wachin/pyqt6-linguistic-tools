from __future__ import annotations

import os
from pathlib import Path

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6", reason="PyQt6 is an optional dependency")

from PyQt6.QtCore import QSettings, QThreadPool, Qt
from PyQt6.QtWidgets import QApplication, QVBoxLayout

from pyqt6_linguistic_tools import (
    DictionaryCatalog,
    DictionaryCatalogEntry,
    DictionaryRegistry,
    DictionarySourcePriority,
    DirectoryDictionaryProvider,
    LinguisticService,
    ManagedDictionaryProvider,
    PersonalDictionaryStore,
    UserDictionaryProvider,
)
from pyqt6_linguistic_tools.qt import (
    DictionaryDownloadManagerDialog,
    DictionaryManagerDialog,
    DictionaryManagerWidget,
)


@pytest.fixture(scope="module")
def application():
    return QApplication.instance() or QApplication([])


def _spelling_bundle(root: Path, locale: str) -> Path:
    bundle = root / locale
    bundle.mkdir(parents=True)
    (bundle / f"{locale}.aff").write_text("SET UTF-8\n", encoding="utf-8")
    (bundle / f"{locale}.dic").write_text("1\nword\n", encoding="utf-8")
    return bundle


def _service(tmp_path: Path):
    system_root = tmp_path / "system"
    managed = ManagedDictionaryProvider(tmp_path / "managed")
    user = UserDictionaryProvider(tmp_path / "user")
    _spelling_bundle(system_root, "es_EC")
    _spelling_bundle(user.root, "en_US")
    system = DirectoryDictionaryProvider(
        system_root,
        source="system",
        priority=DictionarySourcePriority.SYSTEM,
    )
    registry = DictionaryRegistry((system, managed, user))
    service = LinguisticService(
        "es_EC",
        registry=registry,
        personal_store=PersonalDictionaryStore(tmp_path / "personal"),
    )
    return service, managed, user


def _group(dialog: DictionaryManagerDialog, index: int):
    return dialog.entries_tree.topLevelItem(index)


def _child(group, column: int, value: str):
    for index in range(group.childCount()):
        item = group.child(index)
        if item.text(column) == value:
            return item
    raise AssertionError(f"no child with column {column} == {value!r}")


def _visible_children(dialog: DictionaryManagerDialog):
    visible = []
    for group_index in range(dialog.entries_tree.topLevelItemCount()):
        group = dialog.entries_tree.topLevelItem(group_index)
        if group.isHidden():
            continue
        for index in range(group.childCount()):
            item = group.child(index)
            if not item.isHidden():
                visible.append(item)
    return visible


def test_lists_sources_statuses_and_advanced_paths(application, tmp_path):
    service, managed, user = _service(tmp_path)
    manager = DictionaryManagerDialog(
        service,
        managed_provider=managed,
        user_provider=user,
    )

    installed = _group(manager, 0)
    assert installed.childCount() == 2
    english = _child(installed, 1, "en_US")
    manager.entries_tree.setCurrentItem(english)

    assert manager.selected_dictionary is not None
    assert manager.selected_dictionary.locale == "en_US"
    assert english.text(2) == "Yes"
    assert english.text(3) == "No"
    assert "user" in english.text(6)
    assert "en_US.aff" in manager.details.toPlainText()
    assert manager.remove_button.isEnabled()


def test_system_dictionary_cannot_be_removed_but_user_bundle_can(application, tmp_path):
    service, managed, user = _service(tmp_path)
    manager = DictionaryManagerDialog(
        service,
        managed_provider=managed,
        user_provider=user,
    )
    installed = _group(manager, 0)
    system_item = _child(installed, 1, "es_EC")
    user_item = _child(installed, 1, "en_US")

    manager.entries_tree.setCurrentItem(system_item)
    assert not manager.remove_button.isEnabled()
    assert not manager.remove_selected(confirm=False)
    assert (tmp_path / "system" / "es_EC").is_dir()

    manager.entries_tree.setCurrentItem(user_item)
    assert manager.remove_selected(confirm=False)
    assert not (user.root / "en_US").exists()
    assert (tmp_path / "system" / "es_EC").is_dir()


def test_shadowed_managed_bundle_remains_visible_and_removable(application, tmp_path):
    managed = ManagedDictionaryProvider(tmp_path / "managed")
    user = UserDictionaryProvider(tmp_path / "user")
    _spelling_bundle(managed.root, "es_EC")
    _spelling_bundle(user.root, "es_EC")
    service = LinguisticService(
        "es_EC",
        registry=DictionaryRegistry((managed, user)),
        personal_store=PersonalDictionaryStore(tmp_path / "personal"),
    )
    manager = DictionaryManagerDialog(
        service,
        managed_provider=managed,
        user_provider=user,
    )

    installed = _group(manager, 0)
    assert installed.childCount() == 2
    inactive = next(
        installed.child(index)
        for index in range(installed.childCount())
        if "Inactive" in installed.child(index).text(0)
    )
    manager.entries_tree.setCurrentItem(inactive)

    assert "managed" in inactive.text(6)
    assert manager.remove_selected(confirm=False)
    assert not (managed.root / "es_EC").exists()
    assert (user.root / "es_EC").is_dir()


def test_manual_import_runs_in_worker_and_refreshes_registry(application, tmp_path):
    service, managed, user = _service(tmp_path)
    pool = QThreadPool()
    manager = DictionaryManagerDialog(
        service,
        managed_provider=managed,
        user_provider=user,
        thread_pool=pool,
    )
    source = _spelling_bundle(tmp_path / "source", "fr_FR")
    completed = []
    manager.import_finished.connect(completed.append)

    assert manager.import_files(
        [source / "fr_FR.aff", source / "fr_FR.dic"],
        bundle_name="french",
    )
    assert manager.busy
    assert pool.waitForDone(5000)
    application.processEvents()

    assert not manager.busy
    assert len(completed) == 1
    assert completed[0].destination == user.root / "french"
    assert service.dictionary_info("fr_FR").has_spelling


def test_catalog_requires_checksum_and_delegates_verified_downloads(
    application, tmp_path
):
    service, managed, user = _service(tmp_path)
    verified = DictionaryCatalogEntry(
        code="fr",
        name="French",
        url="https://example.test/fr.tar.gz",
        size=2048,
        sha256="a" * 64,
        spelling=True,
        thesaurus=True,
    )
    unverified = DictionaryCatalogEntry(
        code="de",
        name="German",
        url="https://example.test/de.tar.gz",
        size=1024,
        spelling=True,
        thesaurus=False,
    )
    catalog = DictionaryCatalog("test", (verified, unverified))
    manager = DictionaryManagerDialog(
        service,
        managed_provider=managed,
        user_provider=user,
        catalog=catalog,
    )
    requested = []
    manager.download_requested.connect(requested.append)

    downloads = _group(manager, 1)
    german = _child(downloads, 1, "de")
    manager.entries_tree.setCurrentItem(german)
    assert not manager.download_button.isEnabled()

    french = _child(downloads, 1, "fr")
    manager.entries_tree.setCurrentItem(french)
    assert manager.download_button.isEnabled()
    manager.download_button.click()

    assert requested == [verified]


def test_search_and_component_filters(application, tmp_path):
    service, managed, user = _service(tmp_path)
    catalog = DictionaryCatalog(
        "test",
        (
            DictionaryCatalogEntry(
                code="fr",
                name="French",
                url="https://example.test/fr.tar.gz",
                size=2048,
                sha256="a" * 64,
                spelling=True,
                thesaurus=True,
            ),
            DictionaryCatalogEntry(
                code="de",
                name="German",
                url="https://example.test/de.tar.gz",
                size=1024,
                sha256="b" * 64,
                spelling=True,
                thesaurus=False,
            ),
            DictionaryCatalogEntry(
                code="zu",
                name="Zulu",
                url="https://example.test/zu.tar.gz",
                size=512,
                sha256="c" * 64,
                spelling=False,
                thesaurus=False,
            ),
        ),
    )
    manager = DictionaryManagerDialog(
        service,
        managed_provider=managed,
        user_provider=user,
        catalog=catalog,
    )

    manager.search_edit.setText("french")
    application.processEvents()
    visible = _visible_children(manager)
    assert {item.text(1) for item in visible} == {"fr"}

    manager.search_edit.clear()
    manager.component_filter.setCurrentIndex(manager.component_filter.findData("both"))
    application.processEvents()
    visible = _visible_children(manager)
    # Installed rows have spelling but no thesaurus in this fixture.
    assert {item.text(1) for item in visible} == {"fr"}

    manager.component_filter.setCurrentIndex(
        manager.component_filter.findData("spelling")
    )
    application.processEvents()
    visible = _visible_children(manager)
    assert "de" in {item.text(1) for item in visible}
    assert "fr" not in {item.text(1) for item in visible}


def test_widget_is_embeddable(application, tmp_path):
    service, managed, user = _service(tmp_path)
    widget = DictionaryManagerWidget(
        service,
        managed_provider=managed,
        user_provider=user,
    )
    layout = QVBoxLayout()
    layout.addWidget(widget)

    assert widget.isWidgetType()
    assert widget.entries_tree.topLevelItemCount() == 2
    assert widget.minimumWidth() >= 680
    assert widget.minimumHeight() >= 420


def test_download_manager_downloads_in_app_and_refreshes(
    application, tmp_path, monkeypatch
):
    service, managed, user = _service(tmp_path)
    source = _spelling_bundle(tmp_path / "source", "fr_FR")
    entry = DictionaryCatalogEntry(
        code="fr",
        name="French",
        url="https://example.test/fr.tar.gz",
        size=1024,
        sha256="a" * 64,
        spelling=True,
        thesaurus=False,
    )
    pool = QThreadPool()
    manager = DictionaryDownloadManagerDialog(
        service,
        managed_provider=managed,
        user_provider=user,
        catalog=DictionaryCatalog("test", (entry,)),
        thread_pool=pool,
    )
    completed = []
    manager.download_finished.connect(completed.append)

    def fake_download(entry, provider, *, progress=None, should_cancel=None):
        if progress is not None:
            progress(1, 1)
        return provider.import_validated_files(
            [source / "fr_FR.aff", source / "fr_FR.dic"],
            bundle_name="dict-fr",
        )

    monkeypatch.setattr(
        "pyqt6_linguistic_tools.qt.dictionary_download.download_dictionary",
        fake_download,
    )

    downloads = _group(manager, 1)
    french = _child(downloads, 1, "fr")
    manager.entries_tree.setCurrentItem(french)
    manager.install_button.click()

    assert pool.waitForDone(5000)
    application.processEvents()

    assert manager.windowTitle() == "Dictionary Download Manager"
    assert completed
    assert (managed.root / "dict-fr").is_dir()
    assert service.dictionary_info("fr_FR").has_spelling


def test_dialog_has_window_controls_and_remembers_geometry(application, tmp_path):
    service, managed, user = _service(tmp_path)
    settings = QSettings(
        str(tmp_path / "geometry.ini"),
        QSettings.Format.IniFormat,
    )
    dialog = DictionaryDownloadManagerDialog(
        service,
        managed_provider=managed,
        user_provider=user,
        settings=settings,
    )

    flags = dialog.windowFlags()
    assert flags & Qt.WindowType.WindowMinimizeButtonHint
    assert flags & Qt.WindowType.WindowMaximizeButtonHint
    assert dialog.isSizeGripEnabled()

    dialog.show()
    application.processEvents()
    dialog.resize(900, 600)
    dialog.move(120, 100)
    dialog.close()
    application.processEvents()
    settings.sync()
    assert settings.value("window/geometry") is not None

    restored = DictionaryDownloadManagerDialog(
        service,
        managed_provider=managed,
        user_provider=user,
        settings=settings,
    )
    assert restored.width() >= 780
    assert restored.height() >= 480
    restored.close()
