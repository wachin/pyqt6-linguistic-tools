"""Validated runtime settings shared by future Qt integration components."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class QtLinguisticSettings:
    """Widget-layer defaults without reading or writing QSettings yet."""

    spellcheck_enabled: bool = True
    highlighting_enabled: bool = True
    thesaurus_enabled: bool = True
    context_menu_enabled: bool = True
    suggestion_limit: int = 8
    synonym_limit: int = 12
    debounce_ms: int = 300

    def __post_init__(self) -> None:
        for name in (
            "spellcheck_enabled",
            "highlighting_enabled",
            "thesaurus_enabled",
            "context_menu_enabled",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be a boolean")
        for name in ("suggestion_limit", "synonym_limit", "debounce_ms"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an integer")
            if value < 0:
                raise ValueError(f"{name} must be zero or greater")


__all__ = ["QtLinguisticSettings"]
