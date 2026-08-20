"""Validated metadata for future managed dictionary downloads."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from urllib.parse import urlparse

from pyqt6_linguistic_tools.errors import DictionaryCatalogError


_SAFE_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")


def _code_key(code: str) -> str:
    return code.replace("-", "_").lower()


@dataclass(frozen=True, slots=True)
class DictionaryCatalogEntry:
    """One downloadable language bundle described by dictionaries.json."""

    code: str
    name: str
    url: str
    size: int
    sha256: str | None = None


@dataclass(frozen=True, slots=True)
class DictionaryCatalog:
    """A validated immutable dictionary release catalog."""

    source: str
    dictionaries: tuple[DictionaryCatalogEntry, ...]

    def get(self, code: str) -> DictionaryCatalogEntry | None:
        if not isinstance(code, str):
            raise TypeError("dictionary code must be a string")
        key = _code_key(code.strip())
        return next(
            (entry for entry in self.dictionaries if _code_key(entry.code) == key),
            None,
        )

    @property
    def supports_verified_downloads(self) -> bool:
        """Return whether every archive has a SHA-256 checksum."""
        return bool(self.dictionaries) and all(
            entry.sha256 is not None for entry in self.dictionaries
        )


def load_dictionary_catalog(path: str | Path) -> DictionaryCatalog:
    """Load and strictly validate the current dictionaries.json schema."""
    catalog_path = Path(path).expanduser().resolve()
    try:
        with catalog_path.open("r", encoding="utf-8-sig") as catalog_file:
            payload = json.load(catalog_file)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DictionaryCatalogError(
            f"cannot read dictionary catalog: {catalog_path}"
        ) from error

    if not isinstance(payload, dict):
        raise DictionaryCatalogError("dictionary catalog root must be an object")
    source = payload.get("source")
    entries = payload.get("dictionaries")
    if not isinstance(source, str) or not source.strip():
        raise DictionaryCatalogError("dictionary catalog requires a source string")
    if not isinstance(entries, list):
        raise DictionaryCatalogError("dictionary catalog requires a dictionaries list")

    parsed: list[DictionaryCatalogEntry] = []
    seen: set[str] = set()
    for position, item in enumerate(entries):
        if not isinstance(item, dict):
            raise DictionaryCatalogError(f"catalog entry {position} must be an object")
        code = item.get("code")
        name = item.get("name")
        url = item.get("url")
        size = item.get("size")
        sha256 = item.get("sha256")
        if not isinstance(code, str) or not _SAFE_CODE.fullmatch(code):
            raise DictionaryCatalogError(f"catalog entry {position} has an invalid code")
        key = _code_key(code)
        if key in seen:
            raise DictionaryCatalogError(f"duplicate dictionary code: {code}")
        seen.add(key)
        if not isinstance(name, str) or not name.strip():
            raise DictionaryCatalogError(f"catalog entry {code} has an invalid name")
        if not isinstance(url, str):
            raise DictionaryCatalogError(f"catalog entry {code} has an invalid URL")
        parsed_url = urlparse(url)
        if parsed_url.scheme != "https" or not parsed_url.netloc:
            raise DictionaryCatalogError(f"catalog entry {code} must use an HTTPS URL")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise DictionaryCatalogError(f"catalog entry {code} has an invalid size")
        if sha256 is not None and (
            not isinstance(sha256, str) or not _SHA256.fullmatch(sha256)
        ):
            raise DictionaryCatalogError(f"catalog entry {code} has an invalid SHA-256")
        parsed.append(
            DictionaryCatalogEntry(
                code=code,
                name=name.strip(),
                url=url,
                size=size,
                sha256=sha256.lower() if sha256 else None,
            )
        )
    return DictionaryCatalog(source=source.strip(), dictionaries=tuple(parsed))


__all__ = [
    "DictionaryCatalog",
    "DictionaryCatalogEntry",
    "load_dictionary_catalog",
]
