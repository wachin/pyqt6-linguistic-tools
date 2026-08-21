"""Application-facing linguistic facade independent of Qt widgets."""

from __future__ import annotations

from collections.abc import Callable, Hashable
import logging
from pathlib import Path
from threading import RLock
from typing import TypeVar

from pyqt6_linguistic_tools.backends import SpellCheckerBackend, ThesaurusBackend
from pyqt6_linguistic_tools.cache import (
    BackendCache,
    LinguisticResultCacheStats,
    ResultCache,
)
from pyqt6_linguistic_tools.errors import (
    DictionaryDiscoveryError,
    LinguisticError,
    PersonalDictionaryError,
)
from pyqt6_linguistic_tools.ignored import IgnoredWords, IgnoredWordsStore
from pyqt6_linguistic_tools.models import (
    BackendResolutionDiagnostic,
    DictionaryInfo,
    LinguisticCapabilities,
    LinguisticComponentFailure,
    LinguisticServiceDiagnostic,
    ThesaurusEntry,
)
from pyqt6_linguistic_tools.personal import (
    PersonalDictionary,
    PersonalDictionaryStore,
    normalize_personal_locale,
    normalize_personal_word,
)
from pyqt6_linguistic_tools.providers import (
    ManagedDictionaryProvider,
    LinuxSystemDictionaryProvider,
    UserDictionaryProvider,
)
from pyqt6_linguistic_tools.registry import DictionaryRegistry
from pyqt6_linguistic_tools.resolver import (
    SpellBackendResolver,
    ThesaurusBackendResolver,
)


DiagnosticHandler = Callable[[LinguisticServiceDiagnostic], None]
ResultT = TypeVar("ResultT")
_RECOVERABLE_ERRORS = (
    DictionaryDiscoveryError,
    LinguisticError,
    PersonalDictionaryError,
)
_COMPONENTS = frozenset({"spelling", "thesaurus"})


def logging_diagnostic_handler(
    logger: logging.Logger | None = None,
    *,
    level: int = logging.WARNING,
) -> DiagnosticHandler:
    """Create a standard-library logging bridge for service diagnostics."""
    if logger is not None and not isinstance(logger, logging.Logger):
        raise TypeError("logger must be a logging.Logger or None")
    if isinstance(level, bool) or not isinstance(level, int):
        raise TypeError("level must be an integer")
    selected = logger or logging.getLogger("pyqt6_linguistic_tools")

    def report(diagnostic: LinguisticServiceDiagnostic) -> None:
        selected.log(
            level,
            "%s failed for %s%s: %s",
            diagnostic.operation,
            diagnostic.locale,
            f" ({diagnostic.component})" if diagnostic.component else "",
            diagnostic.message,
            extra={"linguistic_diagnostic": diagnostic},
        )

    return report


class LinguisticService:
    """Unify dictionaries, engines, personal words, and ignored state."""

    def __init__(
        self,
        language: str,
        *,
        registry: DictionaryRegistry | None = None,
        spell_resolver: SpellBackendResolver | None = None,
        thesaurus_resolver: ThesaurusBackendResolver | None = None,
        personal_store: PersonalDictionaryStore | None = None,
        ignored_store: IgnoredWordsStore | None = None,
        namespace: str = "pyqt6-linguistic-tools",
        spell_backend: str | None = None,
        thesaurus_backend: str | None = None,
        allow_backend_fallback: bool = True,
        spell_check_enabled: bool = True,
        thesaurus_enabled: bool = True,
        backend_cache_size: int = 2,
        result_cache_size: int = 2048,
        strict: bool = False,
        diagnostic_handler: DiagnosticHandler | None = None,
        diagnostic_limit: int = 100,
    ) -> None:
        if registry is not None and not isinstance(registry, DictionaryRegistry):
            raise TypeError("registry must be a DictionaryRegistry")
        if spell_resolver is not None and not isinstance(
            spell_resolver, SpellBackendResolver
        ):
            raise TypeError("spell_resolver must be a SpellBackendResolver")
        if thesaurus_resolver is not None and not isinstance(
            thesaurus_resolver, ThesaurusBackendResolver
        ):
            raise TypeError("thesaurus_resolver must be a ThesaurusBackendResolver")
        if personal_store is not None and not isinstance(
            personal_store, PersonalDictionaryStore
        ):
            raise TypeError("personal_store must be a PersonalDictionaryStore")
        if ignored_store is not None and not isinstance(
            ignored_store, IgnoredWordsStore
        ):
            raise TypeError("ignored_store must be an IgnoredWordsStore")
        for name, value in (
            ("allow_backend_fallback", allow_backend_fallback),
            ("spell_check_enabled", spell_check_enabled),
            ("thesaurus_enabled", thesaurus_enabled),
            ("strict", strict),
        ):
            if not isinstance(value, bool):
                raise TypeError(f"{name} must be a boolean")
        if diagnostic_handler is not None and not callable(diagnostic_handler):
            raise TypeError("diagnostic_handler must be callable or None")
        if isinstance(diagnostic_limit, bool) or not isinstance(diagnostic_limit, int):
            raise TypeError("diagnostic_limit must be an integer")
        if diagnostic_limit < 1:
            raise ValueError("diagnostic_limit must be at least one")

        self._language = normalize_personal_locale(language)
        self.registry = registry or DictionaryRegistry(
            (
                LinuxSystemDictionaryProvider(),
                ManagedDictionaryProvider(namespace=namespace),
                UserDictionaryProvider(namespace=namespace),
            )
        )
        self.spell_resolver = spell_resolver or SpellBackendResolver()
        self.thesaurus_resolver = thesaurus_resolver or ThesaurusBackendResolver()
        self.personal_store = personal_store or PersonalDictionaryStore(
            namespace=namespace
        )
        self.ignored_store = ignored_store or IgnoredWordsStore()
        self.spell_backend = spell_backend
        self.thesaurus_backend = thesaurus_backend
        self.allow_backend_fallback = allow_backend_fallback
        self.strict = strict
        self._spell_check_enabled = spell_check_enabled
        self._thesaurus_enabled = thesaurus_enabled
        self._diagnostic_handler = diagnostic_handler
        self._diagnostic_limit = diagnostic_limit
        self._diagnostics: list[LinguisticServiceDiagnostic] = []
        self._resolution_diagnostics: list[BackendResolutionDiagnostic] = []
        self._component_failures: dict[
            tuple[str, str], LinguisticComponentFailure
        ] = {}
        self._personal: dict[str, PersonalDictionary] = {}
        self._spell_cache: BackendCache[
            tuple[str, Path, str | None], SpellCheckerBackend
        ] = BackendCache(backend_cache_size)
        self._thesaurus_cache: BackendCache[
            tuple[str, Path, str | None], ThesaurusBackend
        ] = BackendCache(backend_cache_size)
        self._spelling_results: ResultCache[tuple[str, str], bool] = ResultCache(
            result_cache_size
        )
        self._suggestion_results: ResultCache[
            tuple[str, str], tuple[str, ...]
        ] = ResultCache(result_cache_size)
        self._thesaurus_results: ResultCache[
            tuple[str, str], ThesaurusEntry | None
        ] = ResultCache(result_cache_size)
        self._personal_revisions: dict[str, int] = {}
        self._registry_revision = self.registry.revision
        self._reported_registry_error_revision = -1
        self._lock = RLock()

    @property
    def language(self) -> str:
        with self._lock:
            return self._language

    @property
    def spell_check_enabled(self) -> bool:
        with self._lock:
            return self._spell_check_enabled

    @property
    def thesaurus_enabled(self) -> bool:
        with self._lock:
            return self._thesaurus_enabled

    def set_language(self, language: str) -> bool:
        """Select the active normalized locale and report whether it changed."""
        normalized = normalize_personal_locale(language)
        with self._lock:
            if normalized == self._language:
                return False
            self._language = normalized
        self.clear_result_caches()
        return True

    def set_spell_check_enabled(self, enabled: bool) -> bool:
        if not isinstance(enabled, bool):
            raise TypeError("enabled must be a boolean")
        with self._lock:
            changed = enabled != self._spell_check_enabled
            self._spell_check_enabled = enabled
            return changed

    def set_thesaurus_enabled(self, enabled: bool) -> bool:
        if not isinstance(enabled, bool):
            raise TypeError("enabled must be a boolean")
        with self._lock:
            changed = enabled != self._thesaurus_enabled
            self._thesaurus_enabled = enabled
            return changed

    def available_languages(self) -> tuple[str, ...]:
        """Return exact locales having spelling, a thesaurus, or both."""
        locale = self.language
        try:
            entries = self.registry.discover(tolerate_provider_errors=True)
            self._sync_registry_revision()
            return tuple(info.locale for info in entries)
        except _RECOVERABLE_ERRORS as error:
            return self._recover(error, "available_languages", locale, ())

    def dictionary_info(self, locale: str | None = None) -> DictionaryInfo | None:
        """Return resolved source information for one requested locale."""
        normalized = self._locale(locale)
        try:
            info = self.registry.get(
                normalized,
                tolerate_provider_errors=True,
            )
            self._sync_registry_revision()
            return info
        except _RECOVERABLE_ERRORS as error:
            return self._recover(error, "dictionary_info", normalized, None)

    def capabilities(self, locale: str | None = None) -> LinguisticCapabilities:
        """Return independently resolved spelling and thesaurus availability."""
        normalized = self._locale(locale)
        info = self.dictionary_info(normalized)
        spelling = False
        suggestions = False
        thesaurus = False
        if info is not None and info.has_spelling and self.spell_check_enabled:
            backend = self._get_spell_backend(info, normalized, "capabilities")
            if backend is not None:
                spelling = backend.metadata.capabilities.spell_check
                suggestions = backend.metadata.capabilities.suggestions
        if info is not None and info.has_thesaurus and self.thesaurus_enabled:
            backend = self._get_thesaurus_backend(info, normalized, "capabilities")
            if backend is not None:
                thesaurus = backend.metadata.capabilities.thesaurus
        return LinguisticCapabilities(
            locale=normalized,
            spell_check=spelling,
            suggestions=suggestions,
            thesaurus=thesaurus,
            spelling_source=info.spelling_source if info else None,
            thesaurus_source=info.thesaurus_source if info else None,
        )

    def check_word(
        self,
        word: str,
        *,
        locale: str | None = None,
        document_id: Hashable | None = None,
        occurrence_id: Hashable | None = None,
    ) -> bool:
        """Accept a word through ignored, personal, or official dictionaries."""
        normalized_word = normalize_personal_word(word)
        normalized_locale = self._locale(locale)
        ignored = self.ignored_words(normalized_locale)
        if ignored.is_ignored(
            normalized_word,
            document_id=document_id,
            occurrence_id=occurrence_id,
        ):
            return True
        try:
            personal = self.personal_dictionary(normalized_locale)
            self._sync_personal_revision(normalized_locale, personal)
            if personal.contains(normalized_word):
                return True
        except PersonalDictionaryError as error:
            self._recover(error, "check_personal_word", normalized_locale, False)
        if not self.spell_check_enabled:
            return True
        info = self.dictionary_info(normalized_locale)
        if info is None or not info.has_spelling:
            return True
        if self.component_failure(normalized_locale, "spelling") is not None:
            return True
        cache_key = (normalized_locale, normalized_word)
        found, cached = self._spelling_results.try_get(cache_key)
        if found:
            return bool(cached)
        backend = self._get_spell_backend(info, normalized_locale, "check_word")
        if backend is None:
            return True
        try:
            accepted = backend.check_word(normalized_word)
            self._spelling_results.put(cache_key, accepted)
            return accepted
        except _RECOVERABLE_ERRORS as error:
            return self._disable_component(
                error, "check_word", normalized_locale, "spelling", True
            )

    def suggestions(
        self,
        word: str,
        *,
        locale: str | None = None,
        limit: int | None = 8,
        document_id: Hashable | None = None,
        occurrence_id: Hashable | None = None,
    ) -> tuple[str, ...]:
        """Return spelling suggestions or an empty safe fallback."""
        normalized_word = normalize_personal_word(word)
        if limit is not None and (
            isinstance(limit, bool) or not isinstance(limit, int)
        ):
            raise TypeError("limit must be an integer or None")
        if limit is not None and limit < 0:
            raise ValueError("limit must be zero or greater")
        if limit == 0:
            return ()
        normalized_locale = self._locale(locale)
        if self.component_failure(normalized_locale, "spelling") is not None:
            return ()
        if self.check_word(
            normalized_word,
            locale=normalized_locale,
            document_id=document_id,
            occurrence_id=occurrence_id,
        ):
            return ()
        info = self.dictionary_info(normalized_locale)
        if info is None or not info.has_spelling:
            return ()
        cache_key = (normalized_locale, normalized_word)
        found, cached = self._suggestion_results.try_get(cache_key)
        if found:
            return self._limit_suggestions(cached or (), limit)
        backend = self._get_spell_backend(info, normalized_locale, "suggestions")
        if backend is None:
            return ()
        try:
            suggestions = backend.suggest(normalized_word, limit=None)
            self._suggestion_results.put(cache_key, suggestions)
            return self._limit_suggestions(suggestions, limit)
        except _RECOVERABLE_ERRORS as error:
            return self._disable_component(
                error, "suggestions", normalized_locale, "spelling", ()
            )

    def thesaurus_entry(
        self, word: str, *, locale: str | None = None
    ) -> ThesaurusEntry | None:
        """Return one structured entry while keeping thesaurus loading lazy."""
        normalized_word = normalize_personal_word(word)
        normalized_locale = self._locale(locale)
        if not self.thesaurus_enabled:
            return None
        info = self.dictionary_info(normalized_locale)
        if info is None or not info.has_thesaurus:
            return None
        if self.component_failure(normalized_locale, "thesaurus") is not None:
            return None
        cache_key = (normalized_locale, normalized_word)
        found, cached = self._thesaurus_results.try_get(cache_key)
        if found:
            return cached
        backend = self._get_thesaurus_backend(info, normalized_locale, "thesaurus")
        if backend is None:
            return None
        try:
            entry = backend.lookup(normalized_word)
            self._thesaurus_results.put(cache_key, entry)
            return entry
        except _RECOVERABLE_ERRORS as error:
            return self._disable_component(
                error, "thesaurus", normalized_locale, "thesaurus", None
            )

    def synonyms(self, word: str, *, locale: str | None = None) -> tuple[str, ...]:
        """Return unique synonyms across all meanings in source order."""
        entry = self.thesaurus_entry(word, locale=locale)
        if entry is None:
            return ()
        seen: set[str] = set()
        result: list[str] = []
        for meaning in entry.meanings:
            for synonym in (meaning.meaning, *meaning.synonyms):
                if synonym not in seen:
                    seen.add(synonym)
                    result.append(synonym)
        return tuple(result)

    def personal_dictionary(self, locale: str | None = None) -> PersonalDictionary:
        normalized = self._locale(locale)
        with self._lock:
            dictionary = self._personal.get(normalized)
            if dictionary is None:
                dictionary = self.personal_store.for_locale(normalized)
                self._personal[normalized] = dictionary
            return dictionary

    def add_to_personal_dictionary(
        self, word: str, *, locale: str | None = None
    ) -> bool:
        normalized_locale = self._locale(locale)
        try:
            dictionary = self.personal_dictionary(normalized_locale)
            changed = dictionary.add_word(word)
            if changed:
                self._invalidate_personal_locale(normalized_locale, dictionary)
            return changed
        except PersonalDictionaryError as error:
            return self._recover(error, "add_personal_word", normalized_locale, False)

    def remove_from_personal_dictionary(
        self, word: str, *, locale: str | None = None
    ) -> bool:
        normalized_locale = self._locale(locale)
        try:
            dictionary = self.personal_dictionary(normalized_locale)
            changed = dictionary.remove_word(word)
            if changed:
                self._invalidate_personal_locale(normalized_locale, dictionary)
            return changed
        except PersonalDictionaryError as error:
            return self._recover(
                error, "remove_personal_word", normalized_locale, False
            )

    def personal_words(self, locale: str | None = None) -> tuple[str, ...]:
        normalized_locale = self._locale(locale)
        try:
            return self.personal_dictionary(normalized_locale).words()
        except PersonalDictionaryError as error:
            return self._recover(error, "personal_words", normalized_locale, ())

    def ignored_words(self, locale: str | None = None) -> IgnoredWords:
        return self.ignored_store.for_locale(self._locale(locale))

    def ignore_once(
        self,
        word: str,
        *,
        document_id: Hashable,
        occurrence_id: Hashable,
        locale: str | None = None,
    ) -> bool:
        return self.ignored_words(locale).ignore_once(
            word, document_id=document_id, occurrence_id=occurrence_id
        )

    def ignore_for_document(
        self,
        word: str,
        *,
        document_id: Hashable,
        locale: str | None = None,
    ) -> bool:
        return self.ignored_words(locale).ignore_for_document(
            word, document_id=document_id
        )

    def ignore_for_session(
        self, word: str, *, locale: str | None = None
    ) -> bool:
        return self.ignored_words(locale).ignore_for_session(word)

    def clear_ignored_document(
        self, document_id: Hashable, *, locale: str | None = None
    ) -> bool:
        return self.ignored_words(locale).clear_document(document_id)

    def clear_ignored_once(
        self,
        *,
        document_id: Hashable,
        occurrence_id: Hashable,
        locale: str | None = None,
    ) -> bool:
        return self.ignored_words(locale).clear_once(
            document_id=document_id, occurrence_id=occurrence_id
        )

    def clear_ignored_session(self, *, locale: str | None = None) -> bool:
        return self.ignored_words(locale).clear_session()

    def clear_all_ignored(self, *, locale: str | None = None) -> bool:
        return self.ignored_words(locale).clear_all()

    def refresh_dictionaries(self) -> tuple[str, ...]:
        """Rediscover sources and unload backends pointing at the old snapshot."""
        locale = self.language
        try:
            entries = self.registry.refresh(tolerate_provider_errors=True)
        except _RECOVERABLE_ERRORS as error:
            return self._recover(error, "refresh_dictionaries", locale, ())
        self._sync_registry_revision()
        return tuple(entry.locale for entry in entries)

    def result_cache_stats(self) -> LinguisticResultCacheStats:
        """Return hit, miss, eviction, and occupancy counters."""
        return LinguisticResultCacheStats(
            spelling=self._spelling_results.stats(),
            suggestions=self._suggestion_results.stats(),
            thesaurus=self._thesaurus_results.stats(),
        )

    def clear_result_caches(self, locale: str | None = None) -> int:
        """Invalidate every result, or only results belonging to one locale."""
        if locale is None:
            return (
                self._spelling_results.clear()
                + self._suggestion_results.clear()
                + self._thesaurus_results.clear()
            )
        normalized = normalize_personal_locale(locale)
        return (
            self._spelling_results.invalidate(lambda key: key[0] == normalized)
            + self._suggestion_results.invalidate(lambda key: key[0] == normalized)
            + self._thesaurus_results.invalidate(lambda key: key[0] == normalized)
        )

    def diagnostics(self) -> tuple[LinguisticServiceDiagnostic, ...]:
        with self._lock:
            return tuple(self._diagnostics)

    def disabled_components(self) -> tuple[LinguisticComponentFailure, ...]:
        """Return spelling/thesaurus failures isolated by exact locale."""
        with self._lock:
            return tuple(
                self._component_failures[key]
                for key in sorted(self._component_failures)
            )

    def component_failure(
        self, locale: str, component: str
    ) -> LinguisticComponentFailure | None:
        normalized = normalize_personal_locale(locale)
        component = self._validate_component(component)
        with self._lock:
            return self._component_failures.get((normalized, component))

    def retry_component(self, locale: str, component: str) -> bool:
        """Clear one circuit breaker so a repaired dictionary can be retried."""
        normalized = normalize_personal_locale(locale)
        component = self._validate_component(component)
        with self._lock:
            removed = self._component_failures.pop(
                (normalized, component), None
            )
        if removed is None:
            return False
        if component == "spelling":
            self._remove_locale_backends(self._spell_cache, normalized)
        else:
            self._remove_locale_backends(self._thesaurus_cache, normalized)
        self.clear_result_caches(normalized)
        return True

    def resolution_diagnostics(self) -> tuple[BackendResolutionDiagnostic, ...]:
        with self._lock:
            return tuple(self._resolution_diagnostics)

    def clear_diagnostics(self) -> bool:
        with self._lock:
            if not (self._diagnostics or self._resolution_diagnostics):
                return False
            self._diagnostics.clear()
            self._resolution_diagnostics.clear()
            return True

    def close(self) -> None:
        """Unload all cached engine dictionaries."""
        self._spell_cache.clear()
        self._thesaurus_cache.clear()
        self.clear_result_caches()

    def _locale(self, locale: str | None) -> str:
        return self.language if locale is None else normalize_personal_locale(locale)

    @staticmethod
    def _limit_suggestions(
        suggestions: tuple[str, ...], limit: int | None
    ) -> tuple[str, ...]:
        return suggestions if limit is None else suggestions[:limit]

    def _sync_registry_revision(self) -> None:
        revision = self.registry.revision
        with self._lock:
            if revision == self._registry_revision:
                return
            self._registry_revision = revision
        self._spell_cache.clear()
        self._thesaurus_cache.clear()
        self.clear_result_caches()
        with self._lock:
            self._component_failures.clear()
            report_errors = revision != self._reported_registry_error_revision
            self._reported_registry_error_revision = revision
        if report_errors:
            for error in self.registry.discovery_errors():
                if self.strict:
                    raise error
                self._recover(
                    error,
                    "dictionary_discovery",
                    self.language,
                    None,
                )

    def _sync_personal_revision(
        self, locale: str, dictionary: PersonalDictionary
    ) -> None:
        revision = dictionary.revision
        with self._lock:
            previous = self._personal_revisions.get(locale)
            self._personal_revisions[locale] = revision
        if previous is not None and revision != previous:
            self.clear_result_caches(locale)

    def _invalidate_personal_locale(
        self, locale: str, dictionary: PersonalDictionary
    ) -> None:
        revision = dictionary.revision
        with self._lock:
            self._personal_revisions[locale] = revision
        self.clear_result_caches(locale)

    def _get_spell_backend(
        self, info: DictionaryInfo, locale: str, operation: str
    ) -> SpellCheckerBackend | None:
        if info.aff_path is None:
            return None
        if self.component_failure(locale, "spelling") is not None:
            return None
        key = (locale, info.aff_path, self.spell_backend)

        def create() -> SpellCheckerBackend:
            resolution = self.spell_resolver.resolve(
                info.aff_path,
                locale=locale,
                backend=self.spell_backend,
                allow_fallback=self.allow_backend_fallback,
            )
            with self._lock:
                self._resolution_diagnostics.append(resolution.diagnostic)
                if len(self._resolution_diagnostics) > self._diagnostic_limit:
                    del self._resolution_diagnostics[
                        : len(self._resolution_diagnostics) - self._diagnostic_limit
                    ]
            return resolution.backend

        try:
            return self._spell_cache.get_or_create(key, create)
        except _RECOVERABLE_ERRORS as error:
            return self._disable_component(
                error, operation, locale, "spelling", None
            )

    def _get_thesaurus_backend(
        self, info: DictionaryInfo, locale: str, operation: str
    ) -> ThesaurusBackend | None:
        if info.thesaurus_dat is None:
            return None
        if self.component_failure(locale, "thesaurus") is not None:
            return None
        key = (locale, info.thesaurus_dat, self.thesaurus_backend)

        def create() -> ThesaurusBackend:
            resolution = self.thesaurus_resolver.resolve(
                info.thesaurus_dat,
                locale=locale,
                backend=self.thesaurus_backend,
                allow_fallback=self.allow_backend_fallback,
            )
            with self._lock:
                self._resolution_diagnostics.append(resolution.diagnostic)
                if len(self._resolution_diagnostics) > self._diagnostic_limit:
                    del self._resolution_diagnostics[
                        : len(self._resolution_diagnostics) - self._diagnostic_limit
                    ]
            return resolution.backend

        try:
            return self._thesaurus_cache.get_or_create(key, create)
        except _RECOVERABLE_ERRORS as error:
            return self._disable_component(
                error, operation, locale, "thesaurus", None
            )

    def _disable_component(
        self,
        error: Exception,
        operation: str,
        locale: str,
        component: str,
        fallback: ResultT,
    ) -> ResultT:
        diagnostic = self._make_diagnostic(
            error,
            operation,
            locale,
            component=component,
            disabled=True,
        )
        failure = LinguisticComponentFailure(locale, component, diagnostic)
        with self._lock:
            first_failure = (locale, component) not in self._component_failures
            if first_failure:
                self._component_failures[(locale, component)] = failure
        if first_failure:
            self._record_diagnostic(diagnostic)
        if component == "spelling":
            self._remove_locale_backends(self._spell_cache, locale)
        else:
            self._remove_locale_backends(self._thesaurus_cache, locale)
        self.clear_result_caches(locale)
        if self.strict:
            raise error
        return fallback

    def _recover(
        self,
        error: Exception,
        operation: str,
        locale: str,
        fallback: ResultT,
    ) -> ResultT:
        diagnostic = self._make_diagnostic(error, operation, locale)
        self._record_diagnostic(diagnostic)
        if self.strict:
            raise error
        return fallback

    @staticmethod
    def _make_diagnostic(
        error: Exception,
        operation: str,
        locale: str,
        *,
        component: str | None = None,
        disabled: bool = False,
    ) -> LinguisticServiceDiagnostic:
        cause = error.__cause__
        return LinguisticServiceDiagnostic(
            operation=operation,
            locale=locale,
            error_type=type(error).__name__,
            message=str(error),
            backend=getattr(error, "backend", None),
            path=getattr(error, "path", None),
            component=component,
            disabled=disabled,
            cause_type=type(cause).__name__ if cause is not None else None,
            cause_message=str(cause) if cause is not None else None,
        )

    def _record_diagnostic(self, diagnostic: LinguisticServiceDiagnostic) -> None:
        with self._lock:
            self._diagnostics.append(diagnostic)
            if len(self._diagnostics) > self._diagnostic_limit:
                del self._diagnostics[: len(self._diagnostics) - self._diagnostic_limit]
        if self._diagnostic_handler is not None:
            try:
                self._diagnostic_handler(diagnostic)
            except Exception:
                pass

    @staticmethod
    def _validate_component(component: str) -> str:
        if not isinstance(component, str):
            raise TypeError("component must be a string")
        if component not in _COMPONENTS:
            raise ValueError("component must be 'spelling' or 'thesaurus'")
        return component

    @staticmethod
    def _remove_locale_backends(cache: BackendCache, locale: str) -> None:
        for key in cache.keys():
            if key[0] == locale:
                cache.remove(key)


__all__ = [
    "DiagnosticHandler",
    "LinguisticService",
    "logging_diagnostic_handler",
]
