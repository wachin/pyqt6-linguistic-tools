from pathlib import Path

import pytest

from pyqt6_linguistic_tools.performance import benchmark_case, run_suite


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPELLING_FIXTURE = (
    PROJECT_ROOT / "libs" / "spylls" / "tests" / "integrational" / "fixtures" / "base"
)


def _write_thesaurus(root: Path) -> Path:
    data_path = root.with_suffix(".dat")
    data_path.write_text(
        "UTF-8\nárbol|1\n(sustantivo)|planta alta|vegetal\n",
        encoding="utf-8",
    )
    offset = len("UTF-8\n".encode("utf-8"))
    root.with_suffix(".idx").write_text(
        f"UTF-8\n1\nárbol|{offset}\n",
        encoding="utf-8",
    )
    return data_path


@pytest.mark.parametrize("engine", ["spylls", "pythes"])
def test_benchmark_case_exposes_common_metrics(tmp_path, engine):
    path = SPELLING_FIXTURE if engine == "spylls" else _write_thesaurus(tmp_path / "th_test")

    result = benchmark_case(engine, path, iterations=1, suggestion_limit=1)

    assert result["load_ms"] >= 0
    assert result["entry_count"] > 0
    assert result["source_bytes"] > 0
    assert result["python_peak_mib"] >= result["python_current_mib"] >= 0
    assert result["process_peak_rss_mib"] is None or result["process_peak_rss_mib"] > 0
    assert result["lookup_hit_us"] >= 0
    assert result["lookup_miss_us"] >= 0


def test_isolated_suite_has_stable_json_schema():
    relative_fixture = SPELLING_FIXTURE.relative_to(PROJECT_ROOT)
    case = {
        "engine": "spylls",
        "size": "fixture",
        "locale": "test",
        "relative_path": str(relative_fixture),
    }

    report = run_suite(
        PROJECT_ROOT,
        iterations=1,
        suggestion_limit=1,
        timeout=30,
        cases=(case,),
    )

    assert report["schema_version"] == 1
    assert report["generated_at_utc"].endswith("+00:00")
    assert report["settings"]["iterations"] == 1
    assert report["environment"]["python"]
    assert report["cases"][0]["status"] == "ok"
    assert report["cases"][0]["engine"] == "spylls"
