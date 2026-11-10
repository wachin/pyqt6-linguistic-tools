"""Reusable service factory for applications embedding the toolkit."""

from __future__ import annotations

from collections.abc import Iterable
import locale as _locale
from pathlib import Path

from pyqt6_linguistic_tools.locales import normalize_locale
from pyqt6_linguistic_tools.models import DictionarySourcePriority
from pyqt6_linguistic_tools.providers import (
    DictionaryProvider,
    DirectoryDictionaryProvider,
    LinuxSystemDictionaryProvider,
    ManagedDictionaryProvider,
    UserDictionaryProvider,
)
from pyqt6_linguistic_tools.registry import DictionaryRegistry
from pyqt6_linguistic_tools.service import LinguisticService


def _system_language() -> str:
    try:
        language, _encoding = _locale.getdefaultlocale()
    except Exception:
        language = None
    if language:
        return normalize_locale(language)
    return "en_US"


def create_service(
    *,
    language: str | None = None,
    namespace: str = "pyqt6-linguistic-tools",
    include_linux_system: bool = True,
    corpus_path: str | Path | None = None,
    extra_providers: Iterable[DictionaryProvider] = (),
) -> LinguisticService:
    """Create a service with the standard platform and managed providers.

    This is the reusable factory for applications embedding the toolkit as a
    package or as a ``libs/`` git submodule. It never hard-codes a parent
    checkout path: pass ``corpus_path`` explicitly when an application has a
    local LibreOffice corpus.

    ``include_linux_system`` is harmless on Windows and macOS because the
    Linux provider has no roots there. ``namespace`` controls the managed,
    user and personal dictionary storage shared by an application.
    """
    providers: list[DictionaryProvider] = []
    if include_linux_system:
        providers.append(LinuxSystemDictionaryProvider())

    if corpus_path is not None:
        resolved_corpus = Path(corpus_path).expanduser().resolve()
        if not resolved_corpus.is_dir():
            raise ValueError(f"dictionary corpus does not exist: {resolved_corpus}")
        providers.append(
            DirectoryDictionaryProvider(
                resolved_corpus,
                source="corpus",
                priority=DictionarySourcePriority.MANAGED,
            )
        )

    providers.extend(extra_providers)
    providers.extend(
        (
            ManagedDictionaryProvider(namespace=namespace),
            UserDictionaryProvider(namespace=namespace),
        )
    )

    selected_language = language or _system_language()
    registry = DictionaryRegistry(tuple(providers))
    return LinguisticService(
        selected_language,
        registry=registry,
        namespace=namespace,
    )


__all__ = ["create_service"]
