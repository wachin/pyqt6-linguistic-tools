from __future__ import annotations

import os
from pathlib import Path

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6", reason="PyQt6 is an optional dependency")

from PyQt6.QtCore import QThreadPool
from PyQt6.QtWidgets import QApplication

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
from pyqt6_linguistic_tools.qt import DictionaryManagerDialog


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


def test_lists_sources_statuses_and_advanced_paths(application, tmp_path):
    service, managed, user = _service(tmp_path)
    manager = DictionaryManagerDialog(
        service,
        managed_provider=managed,
        user_provider=user,
    )

    assert manager.installed_tree.topLevelItemCount() == 2
    locales = {
        manager.installed_tree.topLevelItem(index).text(1)
        for index in range(manager.installed_tree.topLevelItemCount())
    }
    assert locales == {"en_US", "es_EC"}

    english = next(
        manager.installed_tree.topLevelItem(index)
        for index in range(manager.installed_tree.topLevelItemCount())
        if manager.installed_tree.topLevelItem(index).text(1) == "en_US"
    )
    manager.installed_tree.setCurrentItem(english)

    assert manager.selected_dictionary.locale == "en_US"
    assert english.text(2) == "Available"
    assert english.text(3) == "Missing"
    assert "user" in english.text(4)
    assert "en_US.aff" in manager.details.toPlainText()
    assert manager.remove_button.isEnabled()


def test_system_dictionary_cannot_be_removed_but_user_bundle_can(
    application, tmp_path
):
    service, managed, user = _service(tmp_path)
    manager = DictionaryManagerDialog(
        service,
        managed_provider=managed,
        user_provider=user,
    )
    by_locale = {
        manager.installed_tree.topLevelItem(index).text(1):
        manager.installed_tree.topLevelItem(index)
        for index in range(manager.installed_tree.topLevelItemCount())
    }

    manager.installed_tree.setCurrentItem(by_locale["es_EC"])
    assert not manager.remove_button.isEnabled()
    assert not manager.remove_selected(confirm=False)
    assert (tmp_path / "system" / "es_EC").is_dir()

    manager.installed_tree.setCurrentItem(by_locale["en_US"])
    assert manager.remove_selected(confirm=False)
    assert not (user.root / "en_US").exists()
    assert (tmp_path / "system" / "es_EC").is_dir()


def test_shadowed_managed_bundle_remains_visible_and_removable(
    application, tmp_path
):
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

    assert manager.installed_tree.topLevelItemCount() == 2
    inactive = next(
        manager.installed_tree.topLevelItem(index)
        for index in range(manager.installed_tree.topLevelItemCount())
        if "Inactive" in manager.installed_tree.topLevelItem(index).text(0)
    )
    manager.installed_tree.setCurrentItem(inactive)

    assert "managed" in inactive.text(4)
    assert manager.remove_selected(confirm=False)
    assert not (managed.root / "es_EC").exists()
    assert (user.root / "es_EC").is_dir()

def test_manual_import_runs_in_worker_and_refreshes_registry(
    application, tmp_path
):
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
        code="es",
        name="Spanish",
        url="https://example.test/es.tar.gz",
        size=2048,
        sha256="a" * 64,
    )
    unverified = DictionaryCatalogEntry(
        code="en",
        name="English",
        url="https://example.test/en.tar.gz",
        size=1024,
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

    manager.catalog_tree.setCurrentItem(manager.catalog_tree.topLevelItem(1))
    assert not manager.download_button.isEnabled()
    manager.catalog_tree.setCurrentItem(manager.catalog_tree.topLevelItem(0))
    assert manager.download_button.isEnabled()
    manager.download_button.click()

    assert requested == [verified]
