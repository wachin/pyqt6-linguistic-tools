"""Central dictionary registry with deterministic source resolution."""

from __future__ import annotations

from pathlib import Path
from threading import RLock

from pyqt6_linguistic_tools.errors import DictionaryDiscoveryError
from pyqt6_linguistic_tools.locales import (
    language_of,
    locale_display_name,
    normalize_locale,
)
from pyqt6_linguistic_tools.models import DictionaryCandidate, DictionaryInfo
from pyqt6_linguistic_tools.providers import DictionaryProvider


class DictionaryRegistry:
    """Combine provider results into spelling/thesaurus entries by locale."""

    def __init__(self, providers: tuple[DictionaryProvider, ...] = ()) -> None:
        self._providers: list[DictionaryProvider] = []
        self._cache: tuple[DictionaryInfo, ...] | None = None
        self._by_locale: dict[str, DictionaryInfo] = {}
        self._spelling: dict[str, DictionaryCandidate] = {}
        self._thesauri: dict[str, DictionaryCandidate] = {}
        self._discovery_errors: tuple[DictionaryDiscoveryError, ...] = ()
        self._revision = 0
        self._lock = RLock()
        for provider in providers:
            self.add_provider(provider)

    def add_provider(self, provider: DictionaryProvider) -> None:
        if not isinstance(provider, DictionaryProvider):
            raise TypeError("provider must implement DictionaryProvider")
        with self._lock:
            self._providers.append(provider)
            self._invalidate()

    def remove_providers(self, source: str) -> int:
        """Remove every provider named *source* and return the count."""
        with self._lock:
            retained = [
                provider
                for provider in self._providers
                if provider.source != source
            ]
            removed = len(self._providers) - len(retained)
            if removed:
                self._providers = retained
                self._invalidate()
            return removed

    def providers(self) -> tuple[DictionaryProvider, ...]:
        with self._lock:
            return tuple(self._providers)

    @property
    def revision(self) -> int:
        """Increment whenever provider topology or a discovery snapshot changes."""
        with self._lock:
            return self._revision

    def discover(
        self,
        *,
        force: bool = False,
        tolerate_provider_errors: bool = False,
    ) -> tuple[DictionaryInfo, ...]:
        """Discover and cache all exact locales exposed by the providers."""
        if not isinstance(force, bool):
            raise TypeError("force must be a boolean")
        if not isinstance(tolerate_provider_errors, bool):
            raise TypeError("tolerate_provider_errors must be a boolean")
        with self._lock:
            if self._cache is not None and not force:
                if self._discovery_errors and not tolerate_provider_errors:
                    raise self._discovery_errors[0]
                return self._cache
            providers = tuple(self._providers)

        candidates: list[DictionaryCandidate] = []
        discovery_errors: list[DictionaryDiscoveryError] = []
        for provider in providers:
            try:
                candidates.extend(provider.discover())
            except DictionaryDiscoveryError as error:
                if not tolerate_provider_errors:
                    raise
                discovery_errors.append(error)
            except Exception as error:
                wrapped = DictionaryDiscoveryError(
                    f"dictionary provider failed: {provider.source}",
                    source=provider.source,
                    path=getattr(provider, "root", None),
                )
                wrapped.__cause__ = error
                if not tolerate_provider_errors:
                    raise wrapped
                discovery_errors.append(wrapped)

        spelling: dict[str, DictionaryCandidate] = {}
        thesauri: dict[str, DictionaryCandidate] = {}
        for candidate in candidates:
            locale = normalize_locale(candidate.locale)
            if candidate.has_spelling:
                self._prefer(spelling, locale, candidate)
            if candidate.has_thesaurus:
                self._prefer(thesauri, locale, candidate)

        locales = sorted(
            set(spelling) | set(thesauri),
            key=lambda item: (language_of(item), item),
        )
        entries = tuple(
            self._make_info(locale, spelling, thesauri, allow_language_fallback=True)
            for locale in locales
        )
        with self._lock:
            self._spelling = spelling
            self._thesauri = thesauri
            self._discovery_errors = tuple(discovery_errors)
            self._cache = entries
            self._by_locale = {entry.locale: entry for entry in entries}
            self._revision += 1
            return entries

    def refresh(
        self, *, tolerate_provider_errors: bool = False
    ) -> tuple[DictionaryInfo, ...]:
        """Discard cached discovery data and query every provider again."""
        return self.discover(
            force=True,
            tolerate_provider_errors=tolerate_provider_errors,
        )

    def discovery_errors(self) -> tuple[DictionaryDiscoveryError, ...]:
        """Return provider failures retained by tolerant discovery."""
        with self._lock:
            return self._discovery_errors

    def get(
        self,
        locale: str,
        *,
        allow_language_fallback: bool = True,
        tolerate_provider_errors: bool = False,
    ) -> DictionaryInfo | None:
        """Return resources for *locale*, optionally using language-only data."""
        if not isinstance(allow_language_fallback, bool):
            raise TypeError("allow_language_fallback must be a boolean")
        normalized = normalize_locale(locale)
        self.discover(tolerate_provider_errors=tolerate_provider_errors)
        with self._lock:
            exact = self._by_locale.get(normalized)
            spelling = dict(self._spelling)
            thesauri = dict(self._thesauri)
        if exact is not None and allow_language_fallback:
            return exact
        info = self._make_info(
            normalized,
            spelling,
            thesauri,
            allow_language_fallback=allow_language_fallback,
        )
        return info if info.has_spelling or info.has_thesaurus else None

    def spelling_dictionaries(self) -> tuple[DictionaryInfo, ...]:
        return tuple(entry for entry in self.discover() if entry.has_spelling)

    def thesauri(self) -> tuple[DictionaryInfo, ...]:
        return tuple(entry for entry in self.discover() if entry.has_thesaurus)

    @staticmethod
    def _prefer(
        selected: dict[str, DictionaryCandidate],
        locale: str,
        candidate: DictionaryCandidate,
    ) -> None:
        current = selected.get(locale)
        if current is None or candidate.priority > current.priority:
            selected[locale] = candidate

    @staticmethod
    def _component(
        locale: str,
        selected: dict[str, DictionaryCandidate],
        allow_language_fallback: bool,
    ) -> tuple[DictionaryCandidate | None, str | None]:
        candidate = selected.get(locale)
        if candidate is not None:
            return candidate, locale
        language = language_of(locale)
        if allow_language_fallback and language != locale:
            candidate = selected.get(language)
            if candidate is not None:
                return candidate, language
        return None, None

    @classmethod
    def _make_info(
        cls,
        locale: str,
        spelling: dict[str, DictionaryCandidate],
        thesauri: dict[str, DictionaryCandidate],
        *,
        allow_language_fallback: bool,
    ) -> DictionaryInfo:
        spell, spell_locale = cls._component(
            locale, spelling, allow_language_fallback
        )
        thesaurus, thesaurus_locale = cls._component(
            locale, thesauri, allow_language_fallback
        )
        return DictionaryInfo(
            locale=locale,
            display_name=locale_display_name(locale),
            aff_path=spell.aff_path if spell else None,
            dic_path=spell.dic_path if spell else None,
            thesaurus_dat=thesaurus.thesaurus_dat if thesaurus else None,
            thesaurus_idx=thesaurus.thesaurus_idx if thesaurus else None,
            spelling_source=spell.source if spell else None,
            thesaurus_source=thesaurus.source if thesaurus else None,
            spelling_locale=spell_locale,
            thesaurus_locale=thesaurus_locale,
        )

    def _invalidate(self) -> None:
        self._cache = None
        self._by_locale = {}
        self._spelling = {}
        self._thesauri = {}
        self._discovery_errors = ()
        self._revision += 1


__all__ = ["DictionaryRegistry"]
