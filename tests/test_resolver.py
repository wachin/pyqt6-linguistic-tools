from __future__ import annotations

from pathlib import Path

import pytest

from pyqt6_linguistic_tools import (
    BackendCapabilities,
    BackendMetadata,
    BackendResolutionCode,
    BackendResolutionError,
    DictionaryMetadata,
    PyThesBackend,
    SpellBackendResolver,
    SpellCheckerBackend,
    SpyllsBackend,
    ThesaurusBackendResolver,
)


class RecordingSpellBackend(SpellCheckerBackend):
    def __init__(self, dictionary: Path, locale: str, *, name: str = "recording"):
        self.dictionary = dictionary
        self.locale = locale
        self.name = name

    @classmethod
    def available(cls) -> bool:
        return True

    @property
    def metadata(self) -> BackendMetadata:
        return BackendMetadata(
            name=self.name,
            version="test",
            capabilities=BackendCapabilities(spell_check=True, suggestions=True),
            dictionary=DictionaryMetadata(
                locale=self.locale,
                paths=(self.dictionary,),
                loaded=False,
            ),
        )

    @property
    def loaded(self) -> bool:
        return False

    def load_dictionary(self) -> None:
        pass

    def unload(self) -> None:
        pass

    def check_word(self, word: str) -> bool:
        return True

    def suggest(self, word: str, *, limit: int | None = 8) -> tuple[str, ...]:
        return ()


def _recording_factory(dictionary: Path, locale: str) -> RecordingSpellBackend:
    return RecordingSpellBackend(dictionary, locale)


def test_spell_resolver_selects_lazy_portable_default(tmp_path: Path):
    resolution = SpellBackendResolver().resolve(
        tmp_path / "es_EC",
        locale="es_EC",
    )

    assert isinstance(resolution.backend, SpyllsBackend)
    assert not resolution.backend.loaded
    assert resolution.backend.metadata.dictionary.locale == "es_EC"
    assert resolution.diagnostic.code is BackendResolutionCode.DEFAULT_SELECTED
    assert resolution.diagnostic.requested_backend is None
    assert resolution.diagnostic.selected_backend == "spylls"
    assert not resolution.diagnostic.fallback_used


def test_thesaurus_resolver_selects_lazy_portable_default(tmp_path: Path):
    resolution = ThesaurusBackendResolver().resolve(
        tmp_path / "th_es_v2.dat",
        locale="es",
    )

    assert isinstance(resolution.backend, PyThesBackend)
    assert not resolution.backend.loaded
    assert resolution.diagnostic.code is BackendResolutionCode.DEFAULT_SELECTED
    assert resolution.diagnostic.selected_backend == "pythes"


def test_explicit_available_backend_is_selected(tmp_path: Path):
    resolver = SpellBackendResolver()
    resolver.register("native", _recording_factory, available=lambda: True)

    resolution = resolver.resolve(
        tmp_path / "es_EC",
        locale="es_EC",
        backend=" Native ",
    )

    assert isinstance(resolution.backend, RecordingSpellBackend)
    assert resolution.backend.locale == "es_EC"
    assert resolution.diagnostic.code is BackendResolutionCode.REQUESTED_SELECTED
    assert resolution.diagnostic.requested_backend == "native"
    assert not resolution.diagnostic.fallback_used


@pytest.mark.parametrize(
    ("name", "available", "compatible", "expected_code"),
    [
        ("missing", None, None, BackendResolutionCode.REQUESTED_UNKNOWN),
        ("native", False, None, BackendResolutionCode.REQUESTED_UNAVAILABLE),
        ("native", True, False, BackendResolutionCode.REQUESTED_INCOMPATIBLE),
    ],
)
def test_failed_explicit_selection_falls_back_without_changing_locale(
    tmp_path: Path,
    name: str,
    available: bool | None,
    compatible: bool | None,
    expected_code: BackendResolutionCode,
):
    resolver = SpellBackendResolver()
    if available is not None:
        resolver.register(
            name,
            _recording_factory,
            available=lambda: available,
            compatible=(
                (lambda dictionary, locale: compatible)
                if compatible is not None
                else None
            ),
        )

    resolution = resolver.resolve(
        tmp_path / "es_EC",
        locale="es_EC",
        backend=name,
    )

    assert isinstance(resolution.backend, SpyllsBackend)
    assert resolution.backend.metadata.dictionary.locale == "es_EC"
    assert resolution.diagnostic.locale == "es_EC"
    assert resolution.diagnostic.code is expected_code
    assert resolution.diagnostic.requested_backend == name
    assert resolution.diagnostic.selected_backend == "spylls"
    assert resolution.diagnostic.fallback_used


def test_fallback_can_be_disabled_for_conformance_tests(tmp_path: Path):
    with pytest.raises(BackendResolutionError) as captured:
        SpellBackendResolver().resolve(
            tmp_path / "es_EC",
            locale="es_EC",
            backend="native",
            allow_fallback=False,
        )

    assert captured.value.requested_backend == "native"
    assert captured.value.locale == "es_EC"
    assert captured.value.operation == "resolve_backend"


def test_available_backends_ignores_failed_availability_checks():
    resolver = SpellBackendResolver()
    resolver.register("available", _recording_factory, available=lambda: True)
    resolver.register("unavailable", _recording_factory, available=lambda: False)
    resolver.register(
        "broken-check",
        _recording_factory,
        available=lambda: 1 / 0,
    )

    assert resolver.registered_backends() == (
        "spylls",
        "available",
        "unavailable",
        "broken-check",
    )
    assert resolver.available_backends() == ("spylls", "available")


def test_resolver_rejects_duplicate_registration():
    resolver = SpellBackendResolver()

    with pytest.raises(ValueError, match="already registered"):
        resolver.register("SPYLLS", _recording_factory, available=lambda: True)


def test_resolver_rejects_factory_returning_wrong_backend_type(tmp_path: Path):
    resolver = SpellBackendResolver()
    resolver.register(
        "wrong",
        lambda dictionary, locale: object(),  # type: ignore[return-value]
        available=lambda: True,
    )

    with pytest.raises(BackendResolutionError, match="invalid type"):
        resolver.resolve(tmp_path / "es_EC", locale="es_EC", backend="wrong")

