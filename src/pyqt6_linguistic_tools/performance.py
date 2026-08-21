"""Reproducible performance measurements for the portable linguistic engines."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gc
import importlib
import itertools
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import tracemalloc
from typing import Any, Iterable

try:
    resource: Any = importlib.import_module("resource")
except ImportError:  # pragma: no cover - unavailable on Windows
    resource = None


SCHEMA_VERSION = 1

DEFAULT_CASES = (
    {
        "engine": "spylls",
        "size": "small",
        "locale": "bo",
        "relative_path": "dict-bo/bo",
    },
    {
        "engine": "spylls",
        "size": "medium",
        "locale": "es_EC",
        "relative_path": "dict-es/es_EC",
    },
    {
        "engine": "spylls",
        "size": "very_large",
        "locale": "mn_MN",
        "relative_path": "dict-mn/mn_MN",
    },
    {
        "engine": "pythes",
        "size": "small",
        "locale": "lv_LV",
        "relative_path": "dict-lv/th_lv_LV_v2.dat",
    },
    {
        "engine": "pythes",
        "size": "medium",
        "locale": "es",
        "relative_path": "dict-es/th_es_v2.dat",
    },
    {
        "engine": "pythes",
        "size": "very_large",
        "locale": "en_US",
        "relative_path": "dict-en/th_en_US_v2.dat",
    },
)


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _subprocess_environment() -> dict[str, str]:
    root = _repository_root()
    paths = (root / "src", root / "libs" / "spylls", root / "libs" / "pythes")
    environment = os.environ.copy()
    existing = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = os.pathsep.join(
        [*(str(path) for path in paths), *((existing,) if existing else ())]
    )
    return environment


def _source_size(paths: Iterable[Path]) -> int:
    return sum(path.stat().st_size for path in paths if path.is_file())


def _peak_rss_mib() -> float | None:
    if resource is None:
        return None
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return peak / (1024 * 1024)
    return peak / 1024


def _average_microseconds(function, words: list[str], iterations: int) -> float:
    started = time.perf_counter()
    calls = 0
    for _ in range(iterations):
        for word in words:
            function(word)
            calls += 1
    return (time.perf_counter() - started) * 1_000_000 / calls


def _measure_load(factory):
    gc.collect()
    tracemalloc.start()
    started = time.perf_counter()
    instance = factory()
    load_seconds = time.perf_counter() - started
    current_bytes, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return instance, {
        "load_ms": load_seconds * 1000,
        "python_current_mib": current_bytes / (1024 * 1024),
        "python_peak_mib": peak_bytes / (1024 * 1024),
        "process_peak_rss_mib": _peak_rss_mib(),
    }


def benchmark_spylls(
    dictionary_root: Path, *, iterations: int, suggestion_limit: int
) -> dict[str, Any]:
    from spylls.hunspell import Dictionary

    dictionary, measurements = _measure_load(
        lambda: Dictionary.from_files(str(dictionary_root))
    )
    known_words = []
    for dictionary_word in dictionary.dic.words[:2000]:
        word = dictionary_word.stem
        if word and not word.startswith("#") and dictionary.lookup(word):
            known_words.append(word)
        if len(known_words) == 8:
            break
    if not known_words:
        raise RuntimeError(f"no valid sample words found in {dictionary_root}")

    missing_words = [f"__pyqt6_linguistic_missing_{index}__" for index in range(8)]
    measurements.update(
        {
            "entry_count": len(dictionary.dic.words),
            "source_bytes": _source_size(
                (dictionary_root.with_suffix(".aff"), dictionary_root.with_suffix(".dic"))
            ),
            "lookup_hit_us": _average_microseconds(
                dictionary.lookup, known_words, iterations
            ),
            "lookup_miss_us": _average_microseconds(
                dictionary.lookup, missing_words, iterations
            ),
        }
    )

    misspelling = known_words[0] + "x"
    started = time.perf_counter()
    suggestions = list(itertools.islice(dictionary.suggest(misspelling), suggestion_limit))
    measurements.update(
        {
            "suggest_ms": (time.perf_counter() - started) * 1000,
            "suggestions_returned": len(suggestions),
            "sample_word": known_words[0],
            "sample_misspelling": misspelling,
        }
    )
    return measurements


def benchmark_pythes(data_path: Path, *, iterations: int) -> dict[str, Any]:
    from pythes import PyThes

    thesaurus, measurements = _measure_load(lambda: PyThes(data_path))
    known_words = list(itertools.islice(thesaurus.index, 8))
    if not known_words:
        raise RuntimeError(f"no thesaurus entries found in {data_path}")
    missing_words = [f"__pyqt6_linguistic_missing_{index}__" for index in range(8)]

    thesaurus.clear_cache()
    started = time.perf_counter()
    for word in known_words:
        thesaurus.lookup(word)
    cold_hit_us = (time.perf_counter() - started) * 1_000_000 / len(known_words)

    thesaurus.clear_cache()
    started = time.perf_counter()
    for word in missing_words:
        thesaurus.lookup(word)
    cold_miss_us = (time.perf_counter() - started) * 1_000_000 / len(missing_words)

    measurements.update(
        {
            "entry_count": len(thesaurus.index),
            "source_bytes": _source_size(
                (data_path, data_path.with_suffix(".idx"))
            ),
            "lookup_hit_us": cold_hit_us,
            "lookup_miss_us": cold_miss_us,
            "lookup_cached_hit_us": _average_microseconds(
                thesaurus.lookup, known_words, iterations
            ),
            "lookup_cached_miss_us": _average_microseconds(
                thesaurus.lookup, missing_words, iterations
            ),
            "sample_word": known_words[0],
        }
    )
    return measurements


def benchmark_case(
    engine: str,
    path: Path,
    *,
    iterations: int = 25,
    suggestion_limit: int = 5,
) -> dict[str, Any]:
    path = Path(path).expanduser().resolve()
    if engine == "spylls":
        return benchmark_spylls(
            path, iterations=iterations, suggestion_limit=suggestion_limit
        )
    if engine == "pythes":
        return benchmark_pythes(path, iterations=iterations)
    raise ValueError(f"unknown engine: {engine}")


def run_case_isolated(
    case: dict[str, str],
    corpus: Path,
    *,
    iterations: int,
    suggestion_limit: int,
    timeout: float,
) -> dict[str, Any]:
    path = corpus / case["relative_path"]
    command = [
        sys.executable,
        "-m",
        "pyqt6_linguistic_tools.performance",
        "--worker",
        case["engine"],
        str(path),
        "--iterations",
        str(iterations),
        "--suggestion-limit",
        str(suggestion_limit),
    ]
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            env=_subprocess_environment(),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            **case,
            "status": "timeout",
            "elapsed_ms": (time.perf_counter() - started) * 1000,
        }
    if completed.returncode != 0:
        return {
            **case,
            "status": "error",
            "elapsed_ms": (time.perf_counter() - started) * 1000,
            "error": completed.stderr.strip() or completed.stdout.strip(),
        }

    measurements = json.loads(completed.stdout)
    return {**case, "status": "ok", **measurements}


def run_suite(
    corpus: Path,
    *,
    iterations: int = 25,
    suggestion_limit: int = 5,
    timeout: float = 300,
    cases=DEFAULT_CASES,
) -> dict[str, Any]:
    corpus = Path(corpus).expanduser().resolve()
    if not corpus.is_dir():
        raise NotADirectoryError(corpus)
    results = [
        run_case_isolated(
            case,
            corpus,
            iterations=iterations,
            suggestion_limit=suggestion_limit,
            timeout=timeout,
        )
        for case in cases
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "cpu_count": os.cpu_count(),
        },
        "settings": {
            "iterations": iterations,
            "suggestion_limit": suggestion_limit,
            "timeout_seconds": timeout,
        },
        "cases": results,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--iterations", type=int, default=25)
    parser.add_argument("--suggestion-limit", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--worker", nargs=2, metavar=("ENGINE", "PATH"))
    return parser


def main(argv=None) -> int:
    arguments = _parser().parse_args(argv)
    if arguments.worker:
        engine, path = arguments.worker
        result = benchmark_case(
            engine,
            Path(path),
            iterations=arguments.iterations,
            suggestion_limit=arguments.suggestion_limit,
        )
    else:
        if arguments.corpus is None:
            raise SystemExit("--corpus is required")
        result = run_suite(
            arguments.corpus,
            iterations=arguments.iterations,
            suggestion_limit=arguments.suggestion_limit,
            timeout=arguments.timeout,
        )

    serialized = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if arguments.output:
        arguments.output.write_text(serialized + "\n", encoding="utf-8")
    else:
        print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
