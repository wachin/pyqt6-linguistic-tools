from __future__ import annotations

import logging
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
    logging_diagnostic_handler,
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
        self.lookup_count = 0
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
        self.lookup_count += 1
        if word == "absent":
            return None
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

    assert service.synonyms("word") == ("related", "similar")
    assert service.thesaurus_entry("absent") is None
    assert service.thesaurus_entry("absent") is None
    assert CountingThesaurusBackend.instances[0].lookup_count == 2


class CountingSpellBackend(SpellCheckerBackend):
    instances: list["CountingSpellBackend"] = []

    def __init__(self, path: Path, locale: str) -> None:
        self.path = path
        self.locale = locale
        self.check_count = 0
        self.suggest_count = 0
        self.unload_count = 0
        self.instances.append(self)

    @classmethod
    def available(cls) -> bool:
        return True

    @property
    def loaded(self) -> bool:
        return True

    @property
    def metadata(self) -> BackendMetadata:
        return BackendMetadata(
            name="counting-spell",
            version="test",
            capabilities=BackendCapabilities(spell_check=True, suggestions=True),
            dictionary=DictionaryMetadata(
                locale=self.locale, paths=(self.path,), loaded=True
            ),
        )

    def load_dictionary(self) -> None:
        pass

    def unload(self) -> None:
        self.unload_count += 1

    def check_word(self, word: str) -> bool:
        self.check_count += 1
        return word == "known"

    def suggest(self, word: str, *, limit: int | None = 8) -> tuple[str, ...]:
        self.suggest_count += 1
        values = ("first", "second", "third")
        return values if limit is None else values[:limit]


def _counting_spell_resolver() -> SpellBackendResolver:
    resolver = SpellBackendResolver()
    resolver.register(
        "counting",
        lambda path, locale: CountingSpellBackend(path, locale),
        available=lambda: True,
    )
    return resolver


def test_service_caches_backend_results_and_slices_cached_suggestions(tmp_path: Path):
    CountingSpellBackend.instances.clear()
    dictionaries = tmp_path / "dicts"
    dictionaries.mkdir()
    _spelling(dictionaries, "en_US", ("placeholder",))
    service = LinguisticService(
        "en_US",
        registry=_registry(dictionaries),
        spell_resolver=_counting_spell_resolver(),
        spell_backend="counting",
        allow_backend_fallback=False,
        result_cache_size=8,
    )

    assert not service.check_word("unknown")
    assert not service.check_word("unknown")
    assert service.suggestions("unknown", limit=1) == ("first",)
    assert service.suggestions("unknown", limit=2) == ("first", "second")

    backend = CountingSpellBackend.instances[0]
    assert backend.check_count == 1
    assert backend.suggest_count == 1
    stats = service.result_cache_stats()
    assert stats.spelling.hits >= 2
    assert stats.suggestions.hits == 1
    assert stats.spelling.size == 1
    assert stats.suggestions.size == 1


def test_personal_changes_invalidate_cached_spelling_and_suggestions(tmp_path: Path):
    CountingSpellBackend.instances.clear()
    dictionaries = tmp_path / "dicts"
    dictionaries.mkdir()
    _spelling(dictionaries, "es_EC", ("placeholder",))
    service = LinguisticService(
        "es_EC",
        registry=_registry(dictionaries),
        spell_resolver=_counting_spell_resolver(),
        spell_backend="counting",
        allow_backend_fallback=False,
        personal_store=PersonalDictionaryStore(tmp_path / "personal"),
    )

    assert not service.check_word("regionalismo")
    assert service.suggestions("regionalismo")
    assert service.add_to_personal_dictionary("regionalismo")
    assert service.result_cache_stats().spelling.size == 0
    assert service.result_cache_stats().suggestions.size == 0
    assert service.check_word("regionalismo")

    assert service.remove_from_personal_dictionary("regionalismo")
    assert not service.check_word("regionalismo")
    assert CountingSpellBackend.instances[0].check_count == 2


def test_language_change_clears_every_result_cache(tmp_path: Path):
    dictionaries = tmp_path / "dicts"
    dictionaries.mkdir()
    _spelling(dictionaries, "en_US", ("hello",))
    _thesaurus(dictionaries, "en_US")
    _spelling(dictionaries, "es_EC", ("hola",))
    service = LinguisticService("en_US", registry=_registry(dictionaries))

    assert service.check_word("hello")
    assert not service.check_word("misspelled")
    service.suggestions("misspelled")
    assert service.thesaurus_entry("absent") is None
    stats = service.result_cache_stats()
    assert stats.spelling.size and stats.suggestions.size and stats.thesaurus.size

    assert service.set_language("es_EC")
    stats = service.result_cache_stats()
    assert stats.spelling.size == 0
    assert stats.suggestions.size == 0
    assert stats.thesaurus.size == 0


def test_external_registry_refresh_invalidates_results_and_loaded_backend(
    tmp_path: Path,
):
    dictionaries = tmp_path / "dicts"
    dictionaries.mkdir()
    root = _spelling(dictionaries, "en_US", ("hello",))
    registry = _registry(dictionaries)
    service = LinguisticService("en_US", registry=registry)

    assert not service.check_word("newword")
    root.with_suffix(".dic").write_text(
        "2\nhello\nnewword\n", encoding="utf-8"
    )
    registry.refresh()

    assert service.check_word("newword")


def test_result_caches_are_bounded_at_service_level(tmp_path: Path):
    CountingSpellBackend.instances.clear()
    dictionaries = tmp_path / "dicts"
    dictionaries.mkdir()
    _spelling(dictionaries, "en_US", ("placeholder",))
    service = LinguisticService(
        "en_US",
        registry=_registry(dictionaries),
        spell_resolver=_counting_spell_resolver(),
        spell_backend="counting",
        allow_backend_fallback=False,
        result_cache_size=2,
    )

    for word in ("one", "two", "three"):
        assert not service.check_word(word)

    stats = service.result_cache_stats().spelling
    assert stats.size == 2
    assert stats.evictions == 1


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


def _broken_resolver(
    created: list[BrokenSpellBackend] | None = None,
) -> SpellBackendResolver:
    resolver = SpellBackendResolver()

    def factory(path, locale):
        backend = BrokenSpellBackend(path, locale)
        if created is not None:
            created.append(backend)
        return backend

    resolver.register(
        "broken",
        factory,
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
    assert diagnostic.component == "spelling"
    assert diagnostic.disabled
    assert service.component_failure("en_US", "spelling").diagnostic == diagnostic
    assert received == [diagnostic]
    assert service.clear_diagnostics()
    assert not service.clear_diagnostics()


def test_component_circuit_breaker_avoids_repeated_failures_and_can_retry(
    tmp_path: Path,
):
    dictionaries = tmp_path / "dicts"
    dictionaries.mkdir()
    _spelling(dictionaries, "en_US", ("hello",))
    created: list[BrokenSpellBackend] = []
    service = LinguisticService(
        "en_US",
        registry=_registry(dictionaries),
        spell_resolver=_broken_resolver(created),
        spell_backend="broken",
        allow_backend_fallback=False,
    )

    assert service.check_word("first")
    assert service.check_word("second")
    assert len(created) == 1
    assert len(service.diagnostics()) == 1
    assert len(service.disabled_components()) == 1

    assert service.retry_component("en_US", "spelling")
    assert not service.retry_component("en_US", "spelling")
    assert service.check_word("third")
    assert len(created) == 2
    assert len(service.diagnostics()) == 2


def test_malformed_thesaurus_disables_only_that_component_and_locale(
    tmp_path: Path,
):
    dictionaries = tmp_path / "dicts"
    dictionaries.mkdir()
    _spelling(dictionaries, "en_US", ("hello",))
    _spelling(dictionaries, "es_EC", ("hola",))
    thesaurus = dictionaries / "th_en_US_v2.dat"
    thesaurus.write_text("NOT-A-CODEC\nbroken", encoding="utf-8")
    service = LinguisticService("en_US", registry=_registry(dictionaries))

    assert not service.check_word("wrong", locale="en_US")
    assert service.thesaurus_entry("bright", locale="en_US") is None
    assert service.component_failure("en_US", "thesaurus") is not None
    assert service.component_failure("en_US", "spelling") is None
    assert not service.check_word("wrong", locale="en_US")
    assert service.check_word("hola", locale="es_EC")
    assert service.component_failure("es_EC", "thesaurus") is None

    thesaurus.write_text(
        "UTF-8\nbright|1\nadj|shining|radiant\n",
        encoding="utf-8",
    )
    assert service.retry_component("en_US", "thesaurus")
    assert service.thesaurus_entry("bright", locale="en_US") is not None


def test_malformed_hunspell_disables_only_spelling_for_its_locale(tmp_path: Path):
    dictionaries = tmp_path / "dicts"
    dictionaries.mkdir()
    broken = _spelling(dictionaries, "en_US", ("hello",))
    broken.with_suffix(".aff").write_text(
        "SET UTF-8\nFLAG malformed\n",
        encoding="utf-8",
    )
    _spelling(dictionaries, "es_EC", ("hola",))
    _thesaurus(dictionaries, "en_US")
    service = LinguisticService("en_US", registry=_registry(dictionaries))

    assert service.check_word("word", locale="en_US")
    failure = service.component_failure("en_US", "spelling")
    assert failure is not None
    assert failure.diagnostic.error_type == "DictionaryLoadError"
    assert failure.diagnostic.cause_type is not None
    assert failure.diagnostic.cause_message
    assert service.thesaurus_entry("bright", locale="en_US") is not None
    assert service.check_word("hola", locale="es_EC")
    assert not service.check_word("wrong", locale="es_EC")


def test_deleted_dictionary_file_isolated_until_registry_refresh(tmp_path: Path):
    dictionaries = tmp_path / "dicts"
    dictionaries.mkdir()
    root = _spelling(dictionaries, "en_US", ("hello",))
    service = LinguisticService("en_US", registry=_registry(dictionaries))
    assert service.dictionary_info("en_US") is not None
    root.with_suffix(".dic").unlink()

    assert service.check_word("word")
    failure = service.component_failure("en_US", "spelling")
    assert failure is not None
    assert failure.diagnostic.error_type == "DictionaryNotFoundError"

    _spelling(dictionaries, "en_US", ("word",))
    assert service.refresh_dictionaries() == ("en_US",)
    assert service.component_failure("en_US", "spelling") is None
    assert service.check_word("word")


def test_logging_diagnostic_handler_uses_standard_logging(tmp_path: Path, caplog):
    dictionaries = tmp_path / "dicts"
    dictionaries.mkdir()
    _spelling(dictionaries, "en_US", ("hello",))
    logger = logging.getLogger("linguistic-test")
    service = LinguisticService(
        "en_US",
        registry=_registry(dictionaries),
        spell_resolver=_broken_resolver(),
        spell_backend="broken",
        allow_backend_fallback=False,
        diagnostic_handler=logging_diagnostic_handler(logger),
    )

    with caplog.at_level(logging.WARNING, logger="linguistic-test"):
        assert service.check_word("word")

    assert "check_word failed for en_US (spelling)" in caplog.text
    assert caplog.records[-1].linguistic_diagnostic.disabled


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
    assert service.refresh_dictionaries() == ()
    assert service.refresh_dictionaries() == ()
    assert len(service.diagnostics()) == 2
    assert all(
        item.error_type == "DictionaryDiscoveryError"
        for item in service.diagnostics()
    )


def test_failing_provider_does_not_hide_healthy_languages(tmp_path: Path):
    dictionaries = tmp_path / "dicts"
    dictionaries.mkdir()
    _spelling(dictionaries, "en_US", ("hello",))
    missing = DirectoryDictionaryProvider(
        tmp_path / "missing", source="missing", priority=300
    )
    healthy = DirectoryDictionaryProvider(
        dictionaries, source="healthy", priority=100
    )
    service = LinguisticService(
        "en_US",
        registry=DictionaryRegistry((missing, healthy)),
    )

    assert service.available_languages() == ("en_US",)
    assert service.check_word("hello")
    assert not service.check_word("wrong")
    assert len(service.diagnostics()) == 1
    diagnostic = service.diagnostics()[0]
    assert diagnostic.operation == "dictionary_discovery"
    assert diagnostic.path == (tmp_path / "missing").resolve()

    assert service.available_languages() == ("en_US",)
    assert len(service.diagnostics()) == 1


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
