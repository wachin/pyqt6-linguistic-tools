"""Locale normalization and optional Qt-backed display names."""

from __future__ import annotations

import re


_SEPARATOR = re.compile(r"[-_]+")


def normalize_locale(locale: str) -> str:
    """Return a stable underscore-separated locale without losing variants."""
    if not isinstance(locale, str):
        raise TypeError("locale must be a string")
    parts = [part for part in _SEPARATOR.split(locale.strip()) if part]
    if not parts:
        raise ValueError("locale must not be empty")

    normalized = [parts[0].lower()]
    for part in parts[1:]:
        if len(part) == 4 and part.isalpha():
            normalized.append(part.title())
        elif (len(part) == 2 and part.isalpha()) or (
            len(part) == 3 and part.isdigit()
        ):
            normalized.append(part.upper())
        else:
            normalized.append(part.lower())
    return "_".join(normalized)


def language_of(locale: str) -> str:
    """Return the normalized ISO language component."""
    return normalize_locale(locale).split("_", 1)[0]


def spelling_locale_from_stem(stem: str) -> str:
    """Derive a locale from a Hunspell basename."""
    if stem.startswith("hyph_"):
        raise ValueError("hyphenation dictionaries are not spelling dictionaries")
    if stem.lower().endswith("_frami"):
        stem = stem[:-6]
    return normalize_locale(stem)


def thesaurus_locale_from_stem(stem: str) -> str:
    """Derive the language/script/territory prefix from a MyThes basename."""
    if not stem.lower().startswith("th_"):
        raise ValueError("MyThes basenames must start with 'th_'")
    parts = [part for part in _SEPARATOR.split(stem[3:]) if part]
    if not parts:
        raise ValueError("MyThes basename does not contain a locale")

    locale_parts = [parts[0]]
    position = 1
    if position < len(parts) and len(parts[position]) == 4 and parts[position].isalpha():
        locale_parts.append(parts[position])
        position += 1
    if position < len(parts):
        territory = parts[position]
        if (len(territory) == 2 and territory.isalpha()) or (
            len(territory) == 3 and territory.isdigit()
        ):
            locale_parts.append(territory)
    return normalize_locale("_".join(locale_parts))


def locale_display_name(locale: str) -> str:
    """Return a native human-readable name, using Qt when it is available."""
    normalized = normalize_locale(locale)
    parts = normalized.split("_")
    language = parts[0]
    script = next((part for part in parts[1:] if len(part) == 4), None)
    territory = next(
        (
            part
            for part in parts[1:]
            if (len(part) == 2 and part.isupper()) or part.isdigit()
        ),
        None,
    )
    variants = [
        part
        for part in parts[1:]
        if part not in {script, territory}
    ]

    language_name = language
    qualifiers: list[str] = []
    try:
        from PyQt6.QtCore import QLocale

        qt_locale = QLocale(normalized.replace("_", "-"))
        language_name = qt_locale.nativeLanguageName() or QLocale.languageToString(
            qt_locale.language()
        )
        if territory is not None:
            qualifiers.append(
                qt_locale.nativeTerritoryName()
                or QLocale.territoryToString(qt_locale.territory())
                or territory
            )
        if script is not None:
            qualifiers.append(QLocale.scriptToString(qt_locale.script()) or script)
    except (ImportError, AttributeError):
        if territory is not None:
            qualifiers.append(territory)
        if script is not None:
            qualifiers.append(script)

    qualifiers.extend(variant.replace("-", " ").title() for variant in variants)
    language_name = language_name[:1].upper() + language_name[1:]
    return (
        f"{language_name} ({', '.join(qualifiers)})"
        if qualifiers
        else language_name
    )


__all__ = [
    "language_of",
    "locale_display_name",
    "normalize_locale",
    "spelling_locale_from_stem",
    "thesaurus_locale_from_stem",
]
