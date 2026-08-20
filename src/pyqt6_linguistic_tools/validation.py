"""Reusable validation for Hunspell and MyThes dictionary files."""

from __future__ import annotations

import codecs
from pathlib import Path
import re
import unicodedata
import warnings

from pyqt6_linguistic_tools.backends import PyThesBackend, SpyllsBackend
from pyqt6_linguistic_tools.errors import DictionaryValidationError
from pyqt6_linguistic_tools.locales import normalize_locale, thesaurus_locale_from_stem
from pyqt6_linguistic_tools.models import (
    DictionaryBundleValidation,
    DictionaryCandidate,
    DictionaryValidationReport,
    ValidationCheck,
    ValidationStatus,
)


_SET_LINE = re.compile(rb"^\s*SET\s+([^\s#]+)", re.IGNORECASE)


def _check(
    code: str,
    status: ValidationStatus,
    message: str,
    path: Path | None = None,
) -> ValidationCheck:
    return ValidationCheck(code=code, status=status, message=message, path=path)


def _declared_hunspell_encoding(path: Path) -> str | None:
    with path.open("rb") as aff_file:
        for raw_line in aff_file:
            match = _SET_LINE.match(raw_line.lstrip(b"\xef\xbb\xbf"))
            if match:
                return match.group(1).decode("ascii")
    return None


def _declared_mythes_encoding(path: Path) -> str:
    with path.open("rb") as source:
        return source.readline().decode("utf-8-sig").strip()


def _known_codec(name: str) -> str:
    return codecs.lookup(name).name


def _read_hunspell_words(
    path: Path, encoding: str, *, maximum: int = 256
) -> tuple[list[str], int | None, int]:
    words: list[str] = []
    declared_count: int | None = None
    actual_count = 0
    saw_first = False
    with path.open("r", encoding=encoding, errors="surrogateescape") as dictionary:
        for line in dictionary:
            entry = line.strip()
            if not entry:
                continue
            if not saw_first:
                saw_first = True
                try:
                    declared_count = int(entry)
                    continue
                except ValueError:
                    pass
            actual_count += 1
            if len(words) < maximum:
                lexical = entry.split("\t", 1)[0].split(" ", 1)[0]
                slash = re.search(r"(?<!\\)/", lexical)
                word = lexical[: slash.start()] if slash else lexical
                word = word.replace(r"\/", "/")
                if word and word not in words:
                    words.append(word)
    return words, declared_count, actual_count


def _mythes_index_entries(path: Path, encoding: str) -> tuple[list[tuple[str, int]], int]:
    with path.open("r", encoding=encoding) as index_file:
        index_file.readline()
        count_text = index_file.readline().strip()
        declared_count = int(count_text)
        entries: list[tuple[str, int]] = []
        for line in index_file:
            line = line.rstrip("\r\n")
            if not line:
                continue
            word, separator, offset = line.rpartition("|")
            if not separator or not word:
                raise ValueError("malformed index entry")
            entries.append((word, int(offset)))
    return entries, declared_count


def _sample_evenly(items: list, limit: int) -> list:
    if len(items) <= limit:
        return items
    if limit == 1:
        return [items[0]]
    indexes = {round(position * (len(items) - 1) / (limit - 1)) for position in range(limit)}
    return [items[index] for index in sorted(indexes)]


def _scan_mythes_words(path: Path, encoding: str, limit: int) -> list[str]:
    words: list[str] = []
    with path.open("r", encoding=encoding) as data_file:
        data_file.readline()
        while len(words) < limit:
            header = data_file.readline()
            if not header:
                break
            entry, separator, count_text = header.rstrip("\r\n").rpartition("|")
            if not separator:
                raise ValueError("malformed MyThes entry header")
            count = int(count_text)
            words.append(entry)
            for _ in range(count):
                if data_file.readline() == "":
                    raise ValueError("truncated MyThes meaning list")
    return words


class DictionaryValidator:
    """Validate source files without modifying or regenerating them."""

    def __init__(self, *, sample_size: int = 8) -> None:
        if isinstance(sample_size, bool) or not isinstance(sample_size, int):
            raise TypeError("sample_size must be an integer")
        if sample_size < 1:
            raise ValueError("sample_size must be at least one")
        self.sample_size = sample_size

    def validate_spelling(
        self,
        aff_path: str | Path,
        dic_path: str | Path,
        *,
        locale: str | None = None,
        representative_words: tuple[str, ...] = (),
    ) -> DictionaryValidationReport:
        aff = Path(aff_path).expanduser().resolve()
        dic = Path(dic_path).expanduser().resolve()
        resolved_locale = normalize_locale(locale or aff.stem)
        checks: list[ValidationCheck] = []
        for code, path in (("aff_exists", aff), ("dic_exists", dic)):
            checks.append(
                _check(
                    code,
                    ValidationStatus.PASS if path.is_file() else ValidationStatus.FAIL,
                    f"file {'exists' if path.is_file() else 'is missing'}: {path.name}",
                    path,
                )
            )
        if not aff.is_file() or not dic.is_file():
            return DictionaryValidationReport("spelling", resolved_locale, tuple(checks))

        encoding = None
        try:
            declared = _declared_hunspell_encoding(aff)
            if declared is None:
                encoding = "Windows-1252"
                checks.append(
                    _check(
                        "encoding_declaration",
                        ValidationStatus.WARNING,
                        "SET is missing; Hunspell's Windows-1252 default will be used",
                        aff,
                    )
                )
            else:
                encoding = _known_codec(declared)
                checks.append(
                    _check(
                        "encoding_declaration",
                        ValidationStatus.PASS,
                        f"declared encoding is supported: {declared}",
                        aff,
                    )
                )
        except (OSError, UnicodeError, LookupError) as error:
            checks.append(
                _check(
                    "encoding_declaration",
                    ValidationStatus.FAIL,
                    f"invalid Hunspell encoding declaration: {error}",
                    aff,
                )
            )
            return DictionaryValidationReport(
                "spelling", resolved_locale, tuple(checks), encoding=encoding
            )

        try:
            with dic.open("r", encoding=encoding) as dictionary:
                for _ in dictionary:
                    pass
            checks.append(
                _check("dictionary_decoding", ValidationStatus.PASS, "dictionary decodes strictly", dic)
            )
        except UnicodeDecodeError as error:
            checks.append(
                _check(
                    "dictionary_decoding",
                    ValidationStatus.WARNING,
                    f"dictionary contains undecodable flag bytes at offset {error.start}; Spylls may preserve them",
                    dic,
                )
            )

        words, declared_count, actual_count = _read_hunspell_words(dic, encoding)
        if declared_count is None:
            checks.append(
                _check("entry_count", ValidationStatus.WARNING, "dictionary has no numeric entry count", dic)
            )
        elif declared_count != actual_count:
            checks.append(
                _check(
                    "entry_count",
                    ValidationStatus.WARNING,
                    f"dictionary declares {declared_count} entries but contains {actual_count}",
                    dic,
                )
            )
        else:
            checks.append(
                _check("entry_count", ValidationStatus.PASS, f"entry count matches: {actual_count}", dic)
            )

        backend = SpyllsBackend(aff, locale=resolved_locale)
        try:
            backend.load_dictionary()
            checks.append(
                _check("engine_load", ValidationStatus.PASS, "Spylls loaded all affix rules and entries", aff)
            )
        except Exception as error:
            checks.append(
                _check("engine_load", ValidationStatus.FAIL, f"Spylls load failed: {error}", aff)
            )
            return DictionaryValidationReport(
                "spelling", resolved_locale, tuple(checks), encoding=encoding
            )

        requested = tuple(representative_words)
        sampled: list[str] = []
        failed_requested: list[str] = []
        try:
            if requested:
                for word in requested:
                    if backend.check_word(word):
                        sampled.append(word)
                    else:
                        failed_requested.append(word)
            else:
                for word in words:
                    if backend.check_word(word):
                        sampled.append(word)
                    if len(sampled) >= self.sample_size:
                        break
        finally:
            backend.unload()

        if failed_requested:
            checks.append(
                _check(
                    "representative_words",
                    ValidationStatus.FAIL,
                    "expected words were rejected: " + ", ".join(failed_requested),
                    dic,
                )
            )
        elif sampled:
            checks.append(
                _check(
                    "representative_words",
                    ValidationStatus.PASS,
                    f"accepted {len(sampled)} representative word(s)",
                    dic,
                )
            )
        else:
            checks.append(
                _check(
                    "representative_words",
                    ValidationStatus.WARNING,
                    "no sampled standalone dictionary entry was accepted",
                    dic,
                )
            )
        return DictionaryValidationReport(
            "spelling",
            resolved_locale,
            tuple(checks),
            encoding=encoding,
            sampled_entries=tuple(sampled),
        )

    def validate_thesaurus(
        self,
        dat_path: str | Path,
        idx_path: str | Path | None = None,
        *,
        locale: str | None = None,
        representative_words: tuple[str, ...] = (),
    ) -> DictionaryValidationReport:
        dat = Path(dat_path).expanduser().resolve()
        idx = (
            Path(idx_path).expanduser().resolve()
            if idx_path is not None
            else dat.with_suffix(".idx")
        )
        resolved_locale = normalize_locale(
            locale or thesaurus_locale_from_stem(dat.stem)
        )
        checks = [
            _check(
                "dat_exists",
                ValidationStatus.PASS if dat.is_file() else ValidationStatus.FAIL,
                f"file {'exists' if dat.is_file() else 'is missing'}: {dat.name}",
                dat,
            )
        ]
        if not dat.is_file():
            return DictionaryValidationReport("thesaurus", resolved_locale, tuple(checks))
        checks.append(
            _check(
                "idx_exists",
                ValidationStatus.PASS if idx.is_file() else ValidationStatus.WARNING,
                "index exists" if idx.is_file() else "index is missing; PyThes will build it in memory",
                idx,
            )
        )

        encoding = None
        try:
            declared = _declared_mythes_encoding(dat)
            encoding = _known_codec(declared)
            with dat.open("r", encoding=encoding) as data_file:
                for _ in data_file:
                    pass
            checks.append(
                _check(
                    "encoding_declaration",
                    ValidationStatus.PASS,
                    f"declared encoding is supported and data decodes: {declared}",
                    dat,
                )
            )
        except (OSError, UnicodeError, LookupError) as error:
            checks.append(
                _check(
                    "encoding_declaration",
                    ValidationStatus.FAIL,
                    f"invalid MyThes encoding or data: {error}",
                    dat,
                )
            )
            return DictionaryValidationReport(
                "thesaurus", resolved_locale, tuple(checks), encoding=encoding
            )

        index_entries: list[tuple[str, int]] = []
        if idx.is_file():
            try:
                index_encoding = _known_codec(_declared_mythes_encoding(idx))
                index_entries, declared_count = _mythes_index_entries(idx, index_encoding)
                if declared_count != len(index_entries):
                    raise ValueError(
                        f"index declares {declared_count} entries but contains {len(index_entries)}"
                    )
                checks.append(
                    _check("index_count", ValidationStatus.PASS, f"index count matches: {declared_count}", idx)
                )
            except (OSError, UnicodeError, LookupError, ValueError) as error:
                checks.append(
                    _check(
                        "index_count",
                        ValidationStatus.WARNING,
                        f"external index is unusable and will require in-memory recovery: {error}",
                        idx,
                    )
                )

        if index_entries:
            mismatches = []
            try:
                with dat.open("r", encoding=encoding) as data_file:
                    for word, offset in _sample_evenly(index_entries, self.sample_size):
                        data_file.seek(offset)
                        entry = data_file.readline().rstrip("\r\n").rpartition("|")[0]
                        if unicodedata.normalize("NFC", entry.casefold()) != unicodedata.normalize(
                            "NFC", word.casefold()
                        ):
                            mismatches.append(f"{word}@{offset}")
            except (OSError, UnicodeError, ValueError) as error:
                mismatches.append(str(error))
            checks.append(
                _check(
                    "sampled_offsets",
                    ValidationStatus.WARNING if mismatches else ValidationStatus.PASS,
                    (
                        "sampled index offsets mismatch: " + ", ".join(mismatches)
                        if mismatches
                        else f"verified {min(len(index_entries), self.sample_size)} sampled byte offset(s)"
                    ),
                    idx,
                )
            )

        backend = PyThesBackend(dat, locale=resolved_locale, lookup_cache_size=0)
        caught: list[warnings.WarningMessage]
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                backend.load_dictionary()
            checks.append(
                _check(
                    "engine_load",
                    ValidationStatus.WARNING if caught else ValidationStatus.PASS,
                    (
                        "PyThes loaded with recovery: " + "; ".join(str(item.message) for item in caught)
                        if caught
                        else "PyThes loaded and validated the thesaurus"
                    ),
                    dat,
                )
            )
        except Exception as error:
            checks.append(
                _check("engine_load", ValidationStatus.FAIL, f"PyThes load failed: {error}", dat)
            )
            return DictionaryValidationReport(
                "thesaurus", resolved_locale, tuple(checks), encoding=encoding
            )

        try:
            words = list(representative_words) or _scan_mythes_words(
                dat, encoding, self.sample_size
            )
            failures = [word for word in words if backend.lookup(word) is None]
            if not words:
                failures = ["thesaurus contains no readable entries"]
        except Exception as error:
            words = []
            failures = [str(error)]
        finally:
            backend.unload()
        checks.append(
            _check(
                "representative_entries",
                ValidationStatus.FAIL if failures else ValidationStatus.PASS,
                (
                    "thesaurus lookups failed: " + ", ".join(failures)
                    if failures
                    else f"read {len(words)} representative thesaurus entry/entries"
                ),
                dat,
            )
        )
        return DictionaryValidationReport(
            "thesaurus",
            resolved_locale,
            tuple(checks),
            encoding=encoding,
            sampled_entries=tuple(words),
        )

    def validate_candidate(self, candidate: DictionaryCandidate) -> DictionaryBundleValidation:
        reports: list[DictionaryValidationReport] = []
        if candidate.has_spelling:
            reports.append(
                self.validate_spelling(
                    candidate.aff_path,
                    candidate.dic_path,
                    locale=candidate.locale,
                )
            )
        if candidate.has_thesaurus:
            reports.append(
                self.validate_thesaurus(
                    candidate.thesaurus_dat,
                    candidate.thesaurus_idx,
                    locale=candidate.locale,
                )
            )
        return DictionaryBundleValidation(tuple(reports))

    def validate_candidates(
        self, candidates: tuple[DictionaryCandidate, ...]
    ) -> DictionaryBundleValidation:
        reports = tuple(
            report
            for candidate in candidates
            for report in self.validate_candidate(candidate).reports
        )
        return DictionaryBundleValidation(reports)


def regenerate_thesaurus_index(
    dat_path: str | Path,
    destination: str | Path | None = None,
    *,
    overwrite: bool = False,
) -> Path:
    """Explicitly regenerate and validate a MyThes index through PyThes."""
    if not isinstance(overwrite, bool):
        raise TypeError("overwrite must be a boolean")
    from pythes import PyThes

    resolved = Path(dat_path).expanduser().resolve()
    try:
        thesaurus = PyThes(resolved)
        return thesaurus.regenerate_index(destination, overwrite=overwrite)
    except FileExistsError:
        raise
    except Exception as error:
        raise DictionaryValidationError(
            f"could not regenerate MyThes index for {resolved}",
            path=resolved,
        ) from error


__all__ = ["DictionaryValidator", "regenerate_thesaurus_index"]
