from __future__ import annotations

import sys

import pytest

from pyqt6_linguistic_tools import (
    DictionaryRegistry,
    LinguisticService,
    LinuxSystemDictionaryProvider,
)


pytestmark = pytest.mark.platform


def _system_registry() -> DictionaryRegistry:
    if not sys.platform.startswith("linux"):
        pytest.skip("Linux system dictionary test")
    registry = DictionaryRegistry((LinuxSystemDictionaryProvider(),))
    info = registry.get("es_EC", allow_language_fallback=False)
    if info is None or not info.has_spelling or not info.has_thesaurus:
        pytest.skip("complete es_EC Hunspell and MyThes system data is unavailable")
    return registry


def test_portable_engines_read_installed_linux_dictionaries():
    native_modules = {"hunspell", "mythes"} & sys.modules.keys()
    service = LinguisticService("es_EC", registry=_system_registry())

    assert service.check_word("Ecuador")
    assert not service.check_word("Ecuaddor")
    assert "Ecuador" in service.suggestions("Ecuaddor", limit=8)
    assert "dichoso" in service.synonyms("feliz")
    assert {item.selected_backend for item in service.resolution_diagnostics()} == {
        "spylls",
        "pythes",
    }
    assert ({"hunspell", "mythes"} & sys.modules.keys()) == native_modules


def test_default_service_includes_read_only_system_source():
    service = LinguisticService("es_EC")

    assert tuple(provider.source for provider in service.registry.providers()) == (
        "system",
        "managed",
        "user",
    )
