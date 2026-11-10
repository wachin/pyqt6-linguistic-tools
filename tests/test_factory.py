from __future__ import annotations

from pathlib import Path

import pytest

from pyqt6_linguistic_tools import (
    DictionarySourcePriority,
    DirectoryDictionaryProvider,
    LinuxSystemDictionaryProvider,
    ManagedDictionaryProvider,
    UserDictionaryProvider,
    create_service,
)


def _bundle(root: Path, locale: str = "es_EC") -> None:
    root.mkdir(parents=True)
    (root / f"{locale}.aff").write_text("SET UTF-8\n", encoding="utf-8")
    (root / f"{locale}.dic").write_text("1\nword\n", encoding="utf-8")


def test_create_service_builds_standard_providers(tmp_path: Path):
    service = create_service(
        language="es_EC",
        namespace="factory-test",
    )
    providers = service.registry.providers()

    assert service.language == "es_EC"
    assert any(
        isinstance(provider, LinuxSystemDictionaryProvider) for provider in providers
    )
    assert any(
        isinstance(provider, ManagedDictionaryProvider) for provider in providers
    )
    assert any(isinstance(provider, UserDictionaryProvider) for provider in providers)


def test_create_service_adds_an_explicit_corpus(tmp_path: Path):
    corpus = tmp_path / "dicts"
    _bundle(corpus / "es_EC")

    service = create_service(
        language="es_EC",
        namespace="factory-test",
        corpus_path=corpus,
    )
    corpus_provider = next(
        provider
        for provider in service.registry.providers()
        if isinstance(provider, DirectoryDictionaryProvider)
        and provider.source == "corpus"
    )

    assert corpus_provider.priority == DictionarySourcePriority.MANAGED
    assert corpus_provider.discover()


def test_create_service_rejects_a_missing_corpus(tmp_path: Path):
    with pytest.raises(ValueError, match="corpus does not exist"):
        create_service(
            namespace="factory-test",
            corpus_path=tmp_path / "missing",
        )


def test_create_service_can_disable_linux_system_provider():
    service = create_service(
        language="en_US",
        namespace="factory-test",
        include_linux_system=False,
    )

    assert not any(
        isinstance(provider, LinuxSystemDictionaryProvider)
        for provider in service.registry.providers()
    )


def test_system_dictionaries_work_without_a_corpus():
    roots = (
        Path("/usr/share/hunspell"),
        Path("/usr/share/myspell"),
        Path("/usr/share/myspell/dicts"),
    )
    if not any((root / "es_EC.aff").is_file() for root in roots):
        pytest.skip("no system es_EC Hunspell dictionary available")

    service = create_service(
        language="es_EC",
        namespace="factory-system-test",
        corpus_path=None,
    )
    capabilities = service.capabilities("es_EC")

    assert capabilities.spell_check
    assert capabilities.spelling_source == "system"
    assert service.check_word("mundo")
    assert not service.check_word("mundoerror")
