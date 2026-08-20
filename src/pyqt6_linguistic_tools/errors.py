"""Stable toolkit errors that do not expose portable-engine exceptions."""

from __future__ import annotations

from pathlib import Path


class LinguisticError(Exception):
    """Base error raised by the public linguistic toolkit API."""

    def __init__(
        self,
        message: str,
        *,
        backend: str,
        operation: str,
        path: Path | None = None,
    ) -> None:
        super().__init__(message)
        self.backend = backend
        self.operation = operation
        self.path = path


class BackendUnavailableError(LinguisticError):
    """The selected backend cannot be imported on this installation."""


class DictionaryLoadError(LinguisticError):
    """A spelling dictionary or thesaurus could not be loaded."""


class DictionaryNotFoundError(DictionaryLoadError):
    """One or more source dictionary files do not exist."""


class BackendOperationError(LinguisticError):
    """A loaded backend failed while processing a request."""


class UnsupportedOperationError(LinguisticError):
    """The selected backend does not support an optional operation."""


class BackendResolutionError(LinguisticError):
    """A requested backend could not be selected or safely replaced."""

    def __init__(
        self,
        message: str,
        *,
        requested_backend: str,
        locale: str,
    ) -> None:
        super().__init__(
            message,
            backend=requested_backend,
            operation="resolve_backend",
        )
        self.requested_backend = requested_backend
        self.locale = locale


class DictionaryDiscoveryError(Exception):
    """A dictionary provider failed while enumerating its source."""

    def __init__(self, message: str, *, source: str, path: Path | None = None) -> None:
        super().__init__(message)
        self.source = source
        self.path = path


class DictionaryImportError(Exception):
    """A manual dictionary import is incomplete, invalid, or unsafe."""

    def __init__(self, message: str, *, validation=None) -> None:
        super().__init__(message)
        self.validation = validation


class DictionaryCatalogError(Exception):
    """A dictionary download catalog does not match the supported schema."""


class DictionaryValidationError(Exception):
    """An explicit validation or repair operation could not be completed."""

    def __init__(self, message: str, *, path: Path | None = None) -> None:
        super().__init__(message)
        self.path = path
