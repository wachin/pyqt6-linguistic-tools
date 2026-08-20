from __future__ import annotations

from pathlib import Path

import pytest

from pyqt6_linguistic_tools import (
    DictionaryCandidate,
    DictionaryDiscoveryError,
    DictionaryProvider,
    DictionaryRegistry,
    DictionarySourcePriority,
    DirectoryDictionaryProvider,
    locale_display_name,
    normalize_locale,
)
from pyqt6_linguistic_tools.locales import (
    spelling_locale_from_stem,
    thesaurus_locale_from_stem,
)


def _touch(path: Path, content: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path.resolve()


def _spelling(root: Path, locale: str) -> tuple[Path, Path]:
    return (
        _touch(root / f"{locale}.aff", "SET UTF-8\n"),
        _touch(root / f"{locale}.dic", "1\nword\n"),
    )


def _thesaurus(root: Path, stem: str) -> tuple[Path, Path]:
    return (
        _touch(root / f"{stem}.dat", "UTF-8\n"),
        _touch(root / f"{stem}.idx", "UTF-8\n0\n"),
    )


def test_locale_parsing_preserves_regions_scripts_and_known_variants():
    assert normalize_locale("ES-ec") == "es_EC"
    assert normalize_locale("sr-Latn") == "sr_Latn"
    assert spelling_locale_from_stem("de_DE_frami") == "de_DE"
    assert spelling_locale_from_stem("ca-valencia") == "ca_valencia"
    assert thesaurus_locale_from_stem("th_es_v2") == "es"
    assert thesaurus_locale_from_stem("th_ca_ES_v3") == "ca_ES"
    assert thesaurus_locale_from_stem("th_ru_RU_M_aot_and_v2") == "ru_RU"


def test_directory_provider_discovers_pairs_and_ignores_hyphenation(tmp_path: Path):
    aff, dic = _spelling(tmp_path / "dict-es", "es_EC")
    dat, idx = _thesaurus(tmp_path / "dict-es", "th_es_v2")
    _touch(tmp_path / "dict-es" / "hyph_es.dic")
    _touch(tmp_path / "dict-es" / "orphan.dic")

    provider = DirectoryDictionaryProvider(
        tmp_path,
        source="managed",
        priority=DictionarySourcePriority.MANAGED,
    )
    candidates = provider.discover()

    assert len(candidates) == 2
    spelling = next(candidate for candidate in candidates if candidate.has_spelling)
    thesaurus = next(candidate for candidate in candidates if candidate.has_thesaurus)
    assert (spelling.locale, spelling.aff_path, spelling.dic_path) == (
        "es_EC",
        aff,
        dic,
    )
    assert (thesaurus.locale, thesaurus.thesaurus_dat, thesaurus.thesaurus_idx) == (
        "es",
        dat,
        idx,
    )


def test_registry_pairs_generic_thesaurus_with_regional_spelling(tmp_path: Path):
    aff, dic = _spelling(tmp_path, "es_EC")
    dat, idx = _thesaurus(tmp_path, "th_es_v2")
    registry = DictionaryRegistry(
        (
            DirectoryDictionaryProvider(
                tmp_path,
                source="managed",
                priority=DictionarySourcePriority.MANAGED,
            ),
        )
    )

    ecuador = registry.get("es-EC")
    assert ecuador is not None
    assert ecuador.locale == "es_EC"
    assert ecuador.has_spelling and ecuador.has_thesaurus
    assert (ecuador.aff_path, ecuador.dic_path) == (aff, dic)
    assert (ecuador.thesaurus_dat, ecuador.thesaurus_idx) == (dat, idx)
    assert ecuador.spelling_locale == "es_EC"
    assert ecuador.thesaurus_locale == "es"
    assert ecuador.uses_language_fallback

    strict = registry.get("es_EC", allow_language_fallback=False)
    assert strict is not None
    assert strict.has_spelling
    assert not strict.has_thesaurus


def test_registry_detects_spelling_only_thesaurus_only_and_both(tmp_path: Path):
    _spelling(tmp_path, "en_US")
    _thesaurus(tmp_path, "th_fr_v2")
    _spelling(tmp_path, "de_DE")
    _thesaurus(tmp_path, "th_de_DE_v2")
    registry = DictionaryRegistry(
        (
            DirectoryDictionaryProvider(tmp_path, source="test", priority=1),
        )
    )

    assert registry.get("en_US").has_spelling
    assert not registry.get("en_US").has_thesaurus
    assert not registry.get("fr").has_spelling
    assert registry.get("fr").has_thesaurus
    assert registry.get("de_DE").has_spelling
    assert registry.get("de_DE").has_thesaurus


def test_component_duplicates_use_priority_without_mixing_pairs(tmp_path: Path):
    managed_aff, managed_dic = _spelling(tmp_path / "managed", "es_EC")
    managed_dat, _ = _thesaurus(tmp_path / "managed", "th_es_v2")
    user_aff, user_dic = _spelling(tmp_path / "user", "es_EC")
    registry = DictionaryRegistry(
        (
            DirectoryDictionaryProvider(
                tmp_path / "managed",
                source="managed",
                priority=DictionarySourcePriority.MANAGED,
            ),
            DirectoryDictionaryProvider(
                tmp_path / "user",
                source="user",
                priority=DictionarySourcePriority.USER,
            ),
        )
    )

    selected = registry.get("es_EC")
    assert selected is not None
    assert (selected.aff_path, selected.dic_path) == (user_aff, user_dic)
    assert selected.spelling_source == "user"
    assert selected.thesaurus_dat == managed_dat
    assert selected.thesaurus_source == "managed"
    assert (selected.aff_path, selected.dic_path) != (managed_aff, managed_dic)


class CountingProvider(DictionaryProvider):
    def __init__(self, candidate: DictionaryCandidate):
        self.candidate = candidate
        self.calls = 0

    @property
    def source(self) -> str:
        return self.candidate.source

    @property
    def priority(self) -> int:
        return self.candidate.priority

    def discover(self) -> tuple[DictionaryCandidate, ...]:
        self.calls += 1
        return (self.candidate,)


def test_registry_caches_discovery_and_refreshes_explicitly(tmp_path: Path):
    aff, dic = _spelling(tmp_path, "es_EC")
    provider = CountingProvider(
        DictionaryCandidate(
            locale="es_EC",
            source="counting",
            priority=1,
            aff_path=aff,
            dic_path=dic,
        )
    )
    registry = DictionaryRegistry((provider,))

    assert registry.get("es_EC") is not None
    registry.discover()
    assert provider.calls == 1
    registry.refresh()
    assert provider.calls == 2


def test_equal_priority_keeps_first_registered_provider(tmp_path: Path):
    first_aff, _ = _spelling(tmp_path / "first", "es_EC")
    _spelling(tmp_path / "second", "es_EC")
    registry = DictionaryRegistry(
        (
            DirectoryDictionaryProvider(tmp_path / "first", source="first", priority=1),
            DirectoryDictionaryProvider(tmp_path / "second", source="second", priority=1),
        )
    )

    assert registry.get("es_EC").aff_path == first_aff
    assert registry.get("es_EC").spelling_source == "first"


def test_missing_directory_has_structured_provider_error(tmp_path: Path):
    provider = DirectoryDictionaryProvider(
        tmp_path / "missing",
        source="missing-source",
        priority=1,
    )

    with pytest.raises(DictionaryDiscoveryError) as captured:
        DictionaryRegistry((provider,)).discover()

    assert captured.value.source == "missing-source"
    assert captured.value.path == (tmp_path / "missing").resolve()


def test_display_name_is_human_readable_for_ecuador():
    display_name = locale_display_name("es_EC")

    assert display_name != "es_EC"
    assert "(" in display_name

