from __future__ import annotations

from pathlib import Path

import pytest

from pyqt6_linguistic_tools import (
    BackendCapabilities,
    BackendMetadata,
    BackendOperationError,
    DictionaryMetadata,
    DictionaryRegistry,
    DictionarySourcePriority,
    DirectoryDictionaryProvider,
    LinguisticService,
    PersonalDictionaryStore,
    SpellBackendResolver,
    SpellCheckerBackend,
    ThesaurusBackend,
    ThesaurusBackendResolver,
    ThesaurusEntry,
    ThesaurusMeaning,
)


def _spelling(root: Path, locale: str, words: tuple[str, ...]) -> Path:
    dictionary = root / locale
    dictionary.with_suffix(".aff").write_text(
        "SET UTF-8\nTRY abcdefghijklmnopqrstuvwxyz\n",
        encoding="utf-8",
    )
    dictionary.with_suffix(".dic").write_text(
        f"{len(words)}\n" + "\n".join(words) + "\n",
        encoding="utf-8",
    )
    return dictionary


def _thesaurus(root: Path, locale: str) -> Path:
    path = root / f"th_{locale}_v2.dat"
    path.write_text(
        "UTF-8\n"
        "bright|2\n"
        "adj|shining|radiant|luminous\n"
        "quality|intelligent|clever|radiant\n",
        encoding="utf-8",
    )
    return path


def _registry(root: Path) -> DictionaryRegistry:
    return DictionaryRegistry(
        (
            DirectoryDictionaryProvider(
                root,
                source="test",
                priority=DictionarySourcePriority.MANAGED,
            ),
        )
    )


def test_service_unifies_spelling_suggestions_and_thesaurus(tmp_path: Path):
    dictionaries = tmp_path / "dicts"
    dictionaries.mkdir()
    _spelling(dictionaries, "en_US", ("hello", "world", "spelling"))
    _thesaurus(dictionaries, "en_US")
    service = LinguisticService(
        "en-us",
        registry=_registry(dictionaries),
        personal_store=PersonalDictionaryStore(tmp_path / "personal"),
    )

    assert service.language == "en_US"
    assert service.available_languages() == ("en_US",)
    capabilities = service.capabilities()
    assert capabilities.locale == "en_US"
    assert capabilities.spell_check
    assert capabilities.suggestions
    assert capabilities.thesaurus
    assert capabilities.spelling_source == "test"
    assert capabilities.thesaurus_source == "test"
    assert capabilities.any_dictionary
    assert len(service.resolution_diagnostics()) == 2

    assert service.check_word("hello")
    assert not service.check_word("hellp")
    assert service.suggestions("hellp", limit=1) == ("hello",)
    assert service.suggestions("hello") == ()
    assert service.synonyms("bright") == (
        "shining",
        "radiant",
        "luminous",
        "intelligent",
        "clever",
    )
    entry = service.thesaurus_entry("bright")
    assert entry is not None and entry.word == "bright"
    # Repeated operations reuse the two lazy backend instances.
    assert len(service.resolution_diagnostics()) == 2
    service.close()


def test_personal_and_ignored_words_precede_official_spelling(tmp_path: Path):
    dictionaries = tmp_path / "dicts"
    dictionaries.mkdir()
    _spelling(dictionaries, "es_EC", ("hola",))
    service = LinguisticService(
        "es_EC",
        registry=_registry(dictionaries),
        personal_store=PersonalDictionaryStore(tmp_path / "personal"),
    )

    assert not service.check_word("requinto")
    assert service.add_to_personal_dictionary("requinto")
    assert service.check_word("requinto")
    assert service.personal_words() == ("requinto",)
    assert not service.suggestions("requinto")
    assert service.remove_from_personal_dictionary("requinto")
    assert not service.check_word("requinto")

    assert service.ignore_once(
        "requinto", document_id="song", occurrence_id=(5, 13)
    )
    assert service.check_word(
        "requinto", document_id="song", occurrence_id=(5, 13)
    )
    assert not service.check_word(
        "requinto", document_id="song", occurrence_id=(20, 28)
    )
    assert service.clear_ignored_once(
        document_id="song", occurrence_id=(5, 13)
    )
    assert not service.check_word(
        "requinto", document_id="song", occurrence_id=(5, 13)
    )

    assert service.ignore_for_document("requinto", document_id="song")
    assert service.check_word("requinto", document_id="song")
    assert not service.check_word("requinto", document_id="other")
    assert service.ignore_for_session("requinto")
    assert service.check_word("requinto", document_id="other")
    assert service.clear_ignored_session()
    assert service.clear_ignored_document("song")
    assert not service.check_word("requinto", document_id="song")


def test_language_switching_and_per_call_locale_override(tmp_path: Path):
    dictionaries = tmp_path / "dicts"
    dictionaries.mkdir()
    _spelling(dictionaries, "en_US", ("hello",))
    _spelling(dictionaries, "es_EC", ("hola",))
    service = LinguisticService("en_US", registry=_registry(dictionaries))

    assert service.check_word("hello")
    assert service.check_word("hola", locale="es-ec")
    assert not service.check_word("hola")
    assert service.set_language("es-ec")
    assert not service.set_language("ES_EC")
    assert service.language == "es_EC"
    assert service.check_word("hola")
    assert not service.check_word("hello")
    assert service.available_languages() == ("en_US", "es_EC")


def test_spelling_and_thesaurus_can_be_enabled_independently(tmp_path: Path):
    dictionaries = tmp_path / "dicts"
    dictionaries.mkdir()
    _spelling(dictionaries, "en_US", ("hello",))
    _thesaurus(dictionaries, "en_US")
    service = LinguisticService("en_US", registry=_registry(dictionaries))

    assert service.set_thesaurus_enabled(False)
    assert not service.set_thesaurus_enabled(False)
    assert service.check_word("hello")
    assert service.synonyms("bright") == ()
    capabilities = service.capabilities()
    assert capabilities.spell_check and not capabilities.thesaurus

    assert service.set_spell_check_enabled(False)
    assert service.check_word("anything")
    assert service.set_thesaurus_enabled(True)
    assert service.synonyms("bright")
    capabilities = service.capabilities()
    assert not capabilities.spell_check and capabilities.thesaurus


def test_missing_capabilities_have_safe_results(tmp_path: Path):
    empty = DictionaryRegistry()
    service = LinguisticService("es_EC", registry=empty)

    assert service.available_languages() == ()
    assert service.dictionary_info() is None
    capabilities = service.capabilities()
    assert not capabilities.any_dictionary
    assert capabilities.personal_dictionary and capabilities.ignored_words
    assert service.check_word("cualquierpalabra")
    assert service.suggestions("cualquierpalabra") == ()
    assert service.synonyms("cualquierpalabra") == ()
    assert service.diagnostics() == ()


def test_spelling_only_and_thesaurus_only_languages_remain_independent(
    tmp_path: Path,
):
    dictionaries = tmp_path / "dicts"
    dictionaries.mkdir()
    _spelling(dictionaries, "en_US", ("hello",))
    _thesaurus(dictionaries, "fr_FR")
    service = LinguisticService("en_US", registry=_registry(dictionaries))

    english = service.capabilities("en_US")
    assert english.spell_check and not english.thesaurus
    assert service.check_word("hello", locale="en_US")
    assert service.synonyms("bright", locale="en_US") == ()

    french = service.capabilities("fr_FR")
    assert not french.spell_check and french.thesaurus
    assert service.check_word("anything", locale="fr_FR")
    assert service.synonyms("bright", locale="fr_FR") == (
        "shining",
        "radiant",
        "luminous",
        "intelligent",
        "clever",
    )


def test_service_observes_external_personal_dictionary_changes(tmp_path: Path):
    dictionaries = tmp_path / "dicts"
    dictionaries.mkdir()
    _spelling(dictionaries, "es_EC", ("hola",))
    personal = PersonalDictionaryStore(tmp_path / "personal")
    service = LinguisticService(
        "es_EC", registry=_registry(dictionaries), personal_store=personal
    )

    assert not service.check_word("externa")
    other_application = personal.for_locale("es_EC")
    assert other_application.add_word("externa")
    assert service.check_word("externa")
    assert other_application.remove_word("externa")
    assert not service.check_word("externa")


class CountingThesaurusBackend(ThesaurusBackend):
    instances: list["CountingThesaurusBackend"] = []

    def __init__(self, path: Path, locale: str) -> None:
        self.path = path
        self.locale = locale
        self.load_count = 0
        self.instances.append(self)

    @classmethod
    def available(cls) -> bool:
        return True

    @property
    def loaded(self) -> bool:
        return self.load_count > 0

    @property
    def metadata(self) -> BackendMetadata:
        return BackendMetadata(
            name="counting-thesaurus",
            version="test",
            capabilities=BackendCapabilities(thesaurus=True),
            dictionary=DictionaryMetadata(
                locale=self.locale, paths=(self.path,), loaded=self.loaded
            ),
        )

    def load_dictionary(self) -> None:
        if not self.loaded:
            self.load_count += 1

    def unload(self) -> None:
        self.load_count = 0

    def lookup(self, word: str) -> ThesaurusEntry | None:
        self.load_dictionary()
        return ThesaurusEntry(
            word=word,
            meanings=(ThesaurusMeaning("noun", "related", ("similar",)),),
        )


def test_thesaurus_backend_is_created_and_loaded_only_for_thesaurus_use(tmp_path: Path):
    CountingThesaurusBackend.instances.clear()
    dictionaries = tmp_path / "dicts"
    dictionaries.mkdir()
    _spelling(dictionaries, "en_US", ("hello",))
    data = _thesaurus(dictionaries, "en_US")
    resolver = ThesaurusBackendResolver()
    resolver.register(
        "counting",
        lambda path, locale: CountingThesaurusBackend(path, locale),
        available=lambda: True,
    )
    service = LinguisticService(
        "en_US",
        registry=_registry(dictionaries),
        thesaurus_resolver=resolver,
        thesaurus_backend="counting",
        allow_backend_fallback=False,
    )

    assert service.check_word("hello")
    assert CountingThesaurusBackend.instances == []
    assert service.synonyms("word") == ("related", "similar")
    assert len(CountingThesaurusBackend.instances) == 1
    assert CountingThesaurusBackend.instances[0].path == data
    assert CountingThesaurusBackend.instances[0].load_count == 1


class BrokenSpellBackend(SpellCheckerBackend):
    def __init__(self, path: Path, locale: str) -> None:
        self.path = path
        self.locale = locale

    @classmethod
    def available(cls) -> bool:
        return True

    @property
    def loaded(self) -> bool:
        return False

    @property
    def metadata(self) -> BackendMetadata:
        return BackendMetadata(
            name="broken",
            version="test",
            capabilities=BackendCapabilities(spell_check=True, suggestions=True),
            dictionary=DictionaryMetadata(
                locale=self.locale, paths=(self.path,), loaded=False
            ),
        )

    def load_dictionary(self) -> None:
        pass

    def unload(self) -> None:
        pass

    def check_word(self, word: str) -> bool:
        raise BackendOperationError(
            "simulated spelling failure",
            backend="broken",
            operation="check_word",
            path=self.path,
        )

    def suggest(self, word: str, *, limit: int | None = 8) -> tuple[str, ...]:
        raise BackendOperationError(
            "simulated suggestion failure",
            backend="broken",
            operation="suggest",
            path=self.path,
        )


def _broken_resolver() -> SpellBackendResolver:
    resolver = SpellBackendResolver()
    resolver.register(
        "broken",
        lambda path, locale: BrokenSpellBackend(path, locale),
        available=lambda: True,
    )
    return resolver


def test_recoverable_backend_failure_returns_safe_result_and_diagnostic(tmp_path: Path):
    dictionaries = tmp_path / "dicts"
    dictionaries.mkdir()
    _spelling(dictionaries, "en_US", ("hello",))
    received = []
    service = LinguisticService(
        "en_US",
        registry=_registry(dictionaries),
        spell_resolver=_broken_resolver(),
        spell_backend="broken",
        allow_backend_fallback=False,
        diagnostic_handler=received.append,
    )

    assert service.check_word("word")
    diagnostic = service.diagnostics()[-1]
    assert diagnostic.operation == "check_word"
    assert diagnostic.locale == "en_US"
    assert diagnostic.error_type == "BackendOperationError"
    assert diagnostic.backend == "broken"
    assert received == [diagnostic]
    assert service.clear_diagnostics()
    assert not service.clear_diagnostics()


def test_strict_mode_preserves_structured_backend_error(tmp_path: Path):
    dictionaries = tmp_path / "dicts"
    dictionaries.mkdir()
    _spelling(dictionaries, "en_US", ("hello",))
    service = LinguisticService(
        "en_US",
        registry=_registry(dictionaries),
        spell_resolver=_broken_resolver(),
        spell_backend="broken",
        allow_backend_fallback=False,
        strict=True,
    )

    with pytest.raises(BackendOperationError):
        service.check_word("word")
    assert service.diagnostics()[-1].operation == "check_word"


def test_discovery_failure_is_graceful_and_bounded(tmp_path: Path):
    missing = DirectoryDictionaryProvider(
        tmp_path / "missing", source="missing", priority=1
    )
    service = LinguisticService(
        "es_EC",
        registry=DictionaryRegistry((missing,)),
        diagnostic_limit=2,
    )

    assert service.available_languages() == ()
    assert service.available_languages() == ()
    assert service.available_languages() == ()
    assert len(service.diagnostics()) == 2
    assert all(
        item.error_type == "DictionaryDiscoveryError"
        for item in service.diagnostics()
    )


def test_refresh_rediscovers_languages_and_unloads_old_snapshot(tmp_path: Path):
    dictionaries = tmp_path / "dicts"
    dictionaries.mkdir()
    _spelling(dictionaries, "en_US", ("hello",))
    service = LinguisticService("en_US", registry=_registry(dictionaries))
    assert service.check_word("hello")

    _spelling(dictionaries, "es_EC", ("hola",))

    assert service.refresh_dictionaries() == ("en_US", "es_EC")
    assert service.check_word("hola", locale="es_EC")


@pytest.mark.parametrize(
    "method,args",
    [
        ("set_language", ("../../unsafe",)),
        ("check_word", ("two words",)),
        ("suggestions", ("word",)),
    ],
)
def test_invalid_public_inputs_are_not_hidden(method: str, args, tmp_path: Path):
    service = LinguisticService("en_US", registry=DictionaryRegistry())

    if method == "suggestions":
        with pytest.raises(ValueError):
            service.suggestions(*args, limit=-1)
    else:
        with pytest.raises(ValueError):
            getattr(service, method)(*args)
