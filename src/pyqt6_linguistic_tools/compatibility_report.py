"""Machine-readable dictionary compatibility report generation."""

from __future__ import annotations

import importlib.metadata
import json
import platform
import sys
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pyqt6_linguistic_tools.locales import (
    language_of,
    locale_display_name,
    normalize_locale,
)
from pyqt6_linguistic_tools.models import (
    CompatibilityClassification,
    CompatibilityComponentResult,
    CompatibilityLocaleResult,
    CompatibilityReportMetadata,
    DictionaryCompatibilityReport,
    DictionaryInfo,
    DictionaryValidationReport,
    ValidationCheck,
    ValidationStatus,
)
from pyqt6_linguistic_tools.providers import DirectoryDictionaryProvider
from pyqt6_linguistic_tools.registry import DictionaryRegistry
from pyqt6_linguistic_tools.validation import DictionaryValidator


SCHEMA_VERSION = 1


def _try_get_version(distribution: str) -> str:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _relative_to_corpus(path: Path, corpus_root: Path) -> str | None:
    try:
        return str(path.relative_to(corpus_root))
    except ValueError:
        return None


def _classify_component(
    report: DictionaryValidationReport,
) -> CompatibilityClassification:
    if report.status is ValidationStatus.FAIL:
        return CompatibilityClassification.UNSUPPORTED
    if report.status is ValidationStatus.WARNING:
        return CompatibilityClassification.LIMITED
    return CompatibilityClassification.READY


def _component_result(
    validator: DictionaryValidator,
    registry_entry: DictionaryInfo,
    corpus_root: Path,
    *,
    is_spelling: bool,
) -> CompatibilityComponentResult | None:
    if is_spelling:
        if not registry_entry.has_spelling:
            return None
        aff_path = registry_entry.aff_path
        dic_path = registry_entry.dic_path
        if aff_path is None or dic_path is None:
            return None
        locale = registry_entry.spelling_locale or registry_entry.locale
        validation = validator.validate_spelling(
            aff_path,
            dic_path,
            locale=locale,
        )
        source_path = _relative_to_corpus(dic_path, corpus_root)
    else:
        if not registry_entry.has_thesaurus:
            return None
        dat_path = registry_entry.thesaurus_dat
        idx_path = registry_entry.thesaurus_idx
        if dat_path is None:
            return None
        locale = registry_entry.thesaurus_locale or registry_entry.locale
        validation = validator.validate_thesaurus(
            dat_path,
            idx_path,
            locale=locale,
        )
        source_path = _relative_to_corpus(dat_path, corpus_root)

    component = "spelling" if is_spelling else "thesaurus"
    classification = _classify_component(validation)
    return CompatibilityComponentResult(
        component=component,
        locale=validation.locale,
        source_path=source_path,
        source_encoding=validation.encoding,
        checks=validation.checks,
        classification=classification,
        sampled_entries=validation.sampled_entries,
    )


def generate_compatibility_report(
    corpus_root: Path,
    *,
    sample_size: int = 8,
) -> DictionaryCompatibilityReport:
    """Generate a complete dictionary compatibility report for a corpus."""

    corpus_root = Path(corpus_root).expanduser().resolve()
    if not corpus_root.is_dir():
        raise NotADirectoryError(corpus_root)

    provider = DirectoryDictionaryProvider(
        corpus_root,
        source="corpus",
        priority=100,
    )
    registry = DictionaryRegistry((provider,))
    entries = registry.discover()

    validator = DictionaryValidator(sample_size=sample_size)

    locale_results: list[CompatibilityLocaleResult] = []
    for entry in entries:
        spelling_result = _component_result(
            validator, entry, corpus_root, is_spelling=True
        )
        thesaurus_result = _component_result(
            validator, entry, corpus_root, is_spelling=False
        )
        locale_results.append(
            CompatibilityLocaleResult(
                locale=entry.locale,
                display_name=entry.display_name,
                spelling=spelling_result,
                thesaurus=thesaurus_result,
            )
        )

    locale_results.sort(key=lambda item: (language_of(item.locale), item.locale))

    toolkit_version = _try_get_version("pyqt6-linguistic-tools")
    spylls_version = _try_get_version("spylls")
    pythes_version = _try_get_version("pythes")

    metadata = CompatibilityReportMetadata(
        schema_version=SCHEMA_VERSION,
        generated_at_utc=datetime.now(timezone.utc).isoformat(),
        toolkit_version=toolkit_version,
        spylls_version=spylls_version,
        pythes_version=pythes_version,
        python_version=platform.python_version(),
        platform=platform.platform(),
        machine=platform.machine(),
        corpus_identity=corpus_root.name,
    )

    return DictionaryCompatibilityReport(
        metadata=metadata,
        locales=tuple(locale_results),
    )


def serialize_report(report: DictionaryCompatibilityReport) -> str:
    """Serialize report to deterministic UTF-8 JSON."""

    def default_serializer(obj: Any) -> Any:
        if hasattr(obj, "__dataclass_fields__"):
            return {
                field: getattr(obj, field)
                for field in obj.__dataclass_fields__
            }
        if isinstance(obj, Path):
            return str(obj)
        if isinstance(obj, (set, frozenset)):
            return sorted(obj)
        if isinstance(obj, Enum):
            return obj.value
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    return json.dumps(
        report,
        default=default_serializer,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def write_report(report: DictionaryCompatibilityReport, output_path: Path) -> None:
    """Write report to file with deterministic UTF-8 encoding."""
    output_path = Path(output_path).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = serialize_report(report)
    output_path.write_text(serialized + "\n", encoding="utf-8")


def _parse_args() -> tuple[Path, Path, int]:
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate a dictionary compatibility report for a LibreOffice dictionary corpus."
    )
    parser.add_argument(
        "corpus",
        type=Path,
        help="Path to the LibreOffice dictionaries collection (the dicts directory)",
    )
    parser.add_argument(
        "output",
        type=Path,
        help="Output path for the JSON compatibility report",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=8,
        help="Number of representative entries to sample per component (default: 8)",
    )
    args = parser.parse_args()
    return args.corpus, args.output, args.sample_size


def main() -> int:
    corpus_root, output_path, sample_size = _parse_args()
    report = generate_compatibility_report(corpus_root, sample_size=sample_size)
    write_report(report, output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())