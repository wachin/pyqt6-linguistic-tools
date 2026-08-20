"""Platform-neutral backend selection with explicit fallback diagnostics."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Generic, TypeVar, cast

from pyqt6_linguistic_tools.backends import (
    PyThesBackend,
    SpellCheckerBackend,
    SpyllsBackend,
    ThesaurusBackend,
)
from pyqt6_linguistic_tools.backends.base import LinguisticBackend
from pyqt6_linguistic_tools.errors import BackendResolutionError
from pyqt6_linguistic_tools.models import (
    BackendResolution,
    BackendResolutionCode,
    BackendResolutionDiagnostic,
)


BackendT = TypeVar("BackendT", bound=LinguisticBackend)
BackendFactory = Callable[[Path, str], BackendT]
AvailabilityCheck = Callable[[], bool]
CompatibilityCheck = Callable[[Path, str], bool]


@dataclass(frozen=True, slots=True)
class _Registration(Generic[BackendT]):
    factory: BackendFactory[BackendT]
    available: AvailabilityCheck
    compatible: CompatibilityCheck


def _always_compatible(dictionary: Path, locale: str) -> bool:
    return True


class BackendResolver(Generic[BackendT]):
    """Select registered backends without platform checks in host applications."""

    def __init__(self, *, default: str, backend_type: type[BackendT]) -> None:
        self._default = self._normalize_name(default)
        self._backend_type = backend_type
        self._registrations: dict[str, _Registration[BackendT]] = {}
        self._lock = RLock()

    @staticmethod
    def _normalize_name(name: str) -> str:
        if not isinstance(name, str):
            raise TypeError("backend name must be a string")
        normalized = name.strip().lower()
        if not normalized:
            raise ValueError("backend name must not be empty")
        return normalized

    @property
    def default_backend(self) -> str:
        return self._default

    def register(
        self,
        name: str,
        factory: BackendFactory[BackendT],
        *,
        available: AvailabilityCheck,
        compatible: CompatibilityCheck | None = None,
        replace: bool = False,
    ) -> None:
        """Register a backend factory and its inexpensive selection checks."""
        normalized = self._normalize_name(name)
        if not callable(factory) or not callable(available):
            raise TypeError("factory and available must be callable")
        if compatible is not None and not callable(compatible):
            raise TypeError("compatible must be callable or None")
        with self._lock:
            if normalized in self._registrations and not replace:
                raise ValueError(f"backend is already registered: {normalized}")
            self._registrations[normalized] = _Registration(
                factory=factory,
                available=available,
                compatible=compatible or _always_compatible,
            )

    def registered_backends(self) -> tuple[str, ...]:
        """Return all registered names in deterministic registration order."""
        with self._lock:
            return tuple(self._registrations)

    def available_backends(self) -> tuple[str, ...]:
        """Return registered backends whose availability checks succeed."""
        with self._lock:
            registrations = tuple(self._registrations.items())
        result = []
        for name, registration in registrations:
            try:
                if registration.available():
                    result.append(name)
            except Exception:
                continue
        return tuple(result)

    def resolve(
        self,
        dictionary: str | Path,
        *,
        locale: str,
        backend: str | None = None,
        allow_fallback: bool = True,
    ) -> BackendResolution[BackendT]:
        """Resolve one lazy backend while preserving *dictionary* and *locale*."""
        if not isinstance(locale, str):
            raise TypeError("locale must be a string")
        if not locale.strip():
            raise ValueError("locale must not be empty")
        if not isinstance(allow_fallback, bool):
            raise TypeError("allow_fallback must be a boolean")

        dictionary_path = Path(dictionary).expanduser().resolve()
        requested = self._normalize_name(backend) if backend is not None else None
        candidate = requested or self._default

        selected, failure = self._selectable(candidate, dictionary_path, locale)
        if selected is not None:
            code = (
                BackendResolutionCode.DEFAULT_SELECTED
                if requested is None
                else BackendResolutionCode.REQUESTED_SELECTED
            )
            return self._build_resolution(
                selected,
                dictionary_path,
                locale,
                BackendResolutionDiagnostic(
                    code=code,
                    requested_backend=requested,
                    selected_backend=candidate,
                    locale=locale,
                    fallback_used=False,
                    message=(
                        f"selected default backend {candidate}"
                        if requested is None
                        else f"selected requested backend {candidate}"
                    ),
                ),
            )

        failure_code, failure_message = failure
        if not allow_fallback or candidate == self._default:
            raise BackendResolutionError(
                failure_message,
                requested_backend=candidate,
                locale=locale,
            )

        fallback, fallback_failure = self._selectable(
            self._default, dictionary_path, locale
        )
        if fallback is None:
            raise BackendResolutionError(
                f"{failure_message}; portable fallback failed: {fallback_failure[1]}",
                requested_backend=candidate,
                locale=locale,
            )

        return self._build_resolution(
            fallback,
            dictionary_path,
            locale,
            BackendResolutionDiagnostic(
                code=failure_code,
                requested_backend=requested,
                selected_backend=self._default,
                locale=locale,
                fallback_used=True,
                message=f"{failure_message}; selected fallback {self._default}",
            ),
        )

    def _selectable(
        self, name: str, dictionary: Path, locale: str
    ) -> tuple[_Registration[BackendT] | None, tuple[BackendResolutionCode, str]]:
        with self._lock:
            registration = self._registrations.get(name)
        if registration is None:
            return None, (
                BackendResolutionCode.REQUESTED_UNKNOWN,
                f"requested backend is not registered: {name}",
            )
        try:
            is_available = bool(registration.available())
        except Exception:
            is_available = False
        if not is_available:
            return None, (
                BackendResolutionCode.REQUESTED_UNAVAILABLE,
                f"requested backend is unavailable: {name}",
            )
        try:
            is_compatible = bool(registration.compatible(dictionary, locale))
        except Exception:
            is_compatible = False
        if not is_compatible:
            return None, (
                BackendResolutionCode.REQUESTED_INCOMPATIBLE,
                f"requested backend is incompatible with locale {locale}: {name}",
            )
        return registration, (
            BackendResolutionCode.REQUESTED_SELECTED,
            f"selected backend {name}",
        )

    def _build_resolution(
        self,
        registration: _Registration[BackendT],
        dictionary: Path,
        locale: str,
        diagnostic: BackendResolutionDiagnostic,
    ) -> BackendResolution[BackendT]:
        try:
            backend = registration.factory(dictionary, locale)
        except Exception as error:
            raise BackendResolutionError(
                f"backend factory failed: {diagnostic.selected_backend}",
                requested_backend=diagnostic.selected_backend,
                locale=locale,
            ) from error
        if not isinstance(backend, self._backend_type):
            raise BackendResolutionError(
                f"backend factory returned an invalid type: {diagnostic.selected_backend}",
                requested_backend=diagnostic.selected_backend,
                locale=locale,
            )
        return BackendResolution(backend=cast(BackendT, backend), diagnostic=diagnostic)


class SpellBackendResolver(BackendResolver[SpellCheckerBackend]):
    """Resolver with portable Spylls as its platform-independent default."""

    def __init__(self) -> None:
        super().__init__(default="spylls", backend_type=SpellCheckerBackend)
        self.register(
            "spylls",
            lambda dictionary, locale: SpyllsBackend(dictionary, locale=locale),
            available=lambda: SpyllsBackend.available(),
        )


class ThesaurusBackendResolver(BackendResolver[ThesaurusBackend]):
    """Resolver with portable PyThes as its platform-independent default."""

    def __init__(self) -> None:
        super().__init__(default="pythes", backend_type=ThesaurusBackend)
        self.register(
            "pythes",
            lambda dictionary, locale: PyThesBackend(dictionary, locale=locale),
            available=lambda: PyThesBackend.available(),
        )


__all__ = ["BackendResolver", "SpellBackendResolver", "ThesaurusBackendResolver"]
