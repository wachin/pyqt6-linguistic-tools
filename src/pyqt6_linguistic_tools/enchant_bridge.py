"""Optional import/export bridge for Enchant personal word lists.

Enchant stores user words as one UTF-8 word per line in
``<config-dir>/<locale>.dic``. The sibling ``.exc`` files contain excluded
words; this bridge never rewrites them.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile

from pyqt6_linguistic_tools.personal import (
    PersonalDictionaryStore,
    normalize_personal_locale,
    normalize_personal_word,
)


def enchant_config_dir() -> Path:
    """Return the Enchant user configuration directory without creating it."""
    override = os.environ.get("ENCHANT_CONFIG_DIR")
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / "enchant"
        return Path.home() / "AppData" / "Local" / "enchant"
    if sys.platform == "darwin":
        existing = Path.home() / "Library" / "Preferences" / "enchant"
        if existing.is_dir():
            return existing
        return Path.home() / ".config" / "enchant"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "enchant"


def enchant_personal_file(
    locale: str,
    *,
    config_dir: str | Path | None = None,
) -> Path:
    """Return the Enchant personal ``.dic`` path for one normalized locale."""
    normalized = normalize_personal_locale(locale)
    root = (
        Path(config_dir).expanduser()
        if config_dir is not None
        else enchant_config_dir()
    )
    return root / f"{normalized}.dic"


def import_enchant_personal(
    store: PersonalDictionaryStore,
    *,
    config_dir: str | Path | None = None,
    locales: list[str] | tuple[str, ...] | None = None,
) -> dict[str, int]:
    """Import Enchant ``.dic`` words into the toolkit personal store.

    Returns a mapping of locale to the number of newly added words. Existing
    toolkit words are untouched; ``.exc`` files are intentionally ignored.
    """
    if not isinstance(store, PersonalDictionaryStore):
        raise TypeError("store must be a PersonalDictionaryStore")
    root = (
        Path(config_dir).expanduser()
        if config_dir is not None
        else enchant_config_dir()
    )
    selected = (
        tuple(sorted(locales))
        if locales is not None
        else tuple(sorted(path.stem for path in root.glob("*.dic") if path.is_file()))
    )
    imported: dict[str, int] = {}
    for locale in selected:
        try:
            normalized_locale = normalize_personal_locale(locale)
        except (TypeError, ValueError):
            continue
        path = root / f"{normalized_locale}.dic"
        try:
            lines = path.read_text(encoding="utf-8-sig").splitlines()
        except (OSError, UnicodeError):
            continue
        words: list[str] = []
        for line in lines:
            word = line.strip()
            if not word or word.startswith("#"):
                continue
            try:
                words.append(normalize_personal_word(word))
            except (TypeError, ValueError):
                continue
        added = store.for_locale(normalized_locale).add_words(words)
        imported[normalized_locale] = len(added)
    return imported


def export_enchant_personal(
    store: PersonalDictionaryStore,
    *,
    config_dir: str | Path | None = None,
    locales: list[str] | tuple[str, ...] | None = None,
    merge: bool = True,
) -> dict[str, int]:
    """Merge toolkit personal words into Enchant ``.dic`` files.

    Existing Enchant comments and words are preserved by default. The
    corresponding ``.exc`` files are never modified.
    """
    if not isinstance(store, PersonalDictionaryStore):
        raise TypeError("store must be a PersonalDictionaryStore")
    if not isinstance(merge, bool):
        raise TypeError("merge must be a boolean")
    root = (
        Path(config_dir).expanduser()
        if config_dir is not None
        else enchant_config_dir()
    )
    root.mkdir(parents=True, exist_ok=True)
    selected = (
        tuple(sorted(locales)) if locales is not None else store.available_locales()
    )
    exported: dict[str, int] = {}
    for locale in selected:
        try:
            normalized_locale = normalize_personal_locale(locale)
        except (TypeError, ValueError):
            continue
        target = root / f"{normalized_locale}.dic"
        try:
            existing_lines = target.read_text(encoding="utf-8-sig").splitlines()
        except (OSError, UnicodeError):
            existing_lines = []
        if not merge:
            existing_lines = [
                line for line in existing_lines if line.lstrip().startswith("#")
            ]
        existing_words = {
            line.strip()
            for line in existing_lines
            if line.strip() and not line.lstrip().startswith("#")
        }
        words = store.for_locale(normalized_locale).words()
        added = [word for word in words if word not in existing_words]
        if not added and target.exists():
            exported[normalized_locale] = 0
            continue
        lines = list(existing_lines)
        if lines and lines[-1].strip() and not lines[-1].startswith("#"):
            lines.append("")
        lines.extend(added)
        payload = "\n".join(lines).rstrip("\n") + "\n"
        _write_atomic(target, payload)
        exported[normalized_locale] = len(added)
    return exported


def _write_atomic(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise


__all__ = [
    "enchant_config_dir",
    "enchant_personal_file",
    "export_enchant_personal",
    "import_enchant_personal",
]
