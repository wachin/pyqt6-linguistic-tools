# Portable engine performance baseline and budgets

Baseline captured on 2026-08-20 with Python 3.13.5 on Linux, an Intel Core
i3-7020U (4 logical CPUs) and 7.65 GiB of RAM. The exact machine-readable
results are stored in [`performance-baseline.json`](performance-baseline.json).

These measurements answer an architectural question, not which engine wins a
microbenchmark. Spylls and PyThes are the required portable engines; the goal
is to keep their cost bounded and prevent UI-blocking integration decisions.

## Reproducing the report

Install the repository in editable mode, or run from its root with the local
source paths available, and provide the LibreOffice `dicts` directory:

```bash
python -m pyqt6_linguistic_tools.performance \
  --corpus /path/to/libreoffice-dictionaries-collection/dicts \
  --iterations 25 \
  --suggestion-limit 5 \
  --timeout 300 \
  --output performance-report.json
```

Each case runs in a fresh subprocess. This makes process peak memory and
timeouts independent between dictionaries. Load memory is measured with
`tracemalloc`; peak RSS is also recorded on Unix. Windows still reports Python
allocation peaks but leaves RSS null unless a future platform-specific
collector is added. Timings collected with `tracemalloc` must be compared only
with reports produced by the same tool.

The default matrix is:

| Engine | Size | Locale | Entries | Source size |
| --- | --- | --- | ---: | ---: |
| Spylls | Small | `bo` | 378 | 6.2 KiB |
| Spylls | Medium | `es_EC` | 56,749 | 843.7 KiB |
| Spylls | Very large | `mn_MN` | 583,521 | 17.2 MiB |
| PyThes | Small | `lv_LV` | 2 | 201 bytes |
| PyThes | Medium | `es` | 21,846 | 3.1 MiB |
| PyThes | Very large | `en_US` | 145,866 | 20.6 MiB |

## Initial baseline

| Engine / size | Load | Peak RSS | Hit lookup | Miss lookup | Suggest / cached hit |
| --- | ---: | ---: | ---: | ---: | ---: |
| Spylls small | 39 ms | 17.2 MiB | 11.5 µs | 28.8 µs | 3.4 ms suggest |
| Spylls medium (`es_EC`) | 4.26 s | 110.7 MiB | 11.1 µs | 38.6 µs | 190 ms suggest |
| Spylls very large | 43.8 s | 1003.9 MiB | 14.1 µs | 2.03 ms | 604 ms suggest |
| PyThes small | 0.84 ms | 14.2 MiB | 77.2 µs | 2.6 µs | 3.3 µs cached |
| PyThes medium | 794 ms | 21.9 MiB | 328 µs | 2.8 µs | 2.6 µs cached |
| PyThes very large | 5.45 s | 61.5 MiB | 1.88 ms | 3.0 µs | 2.4 µs cached |

PyThes hit lookup is a cold file seek; its bounded cache makes repeated
lookups roughly three orders of magnitude faster in the large case. Spylls
lookups remain fast after loading, but suggestions can exceed an interactive
frame budget even for a medium dictionary.

## Initial diagnostic budgets

Budgets deliberately include approximately 2–5× headroom for slower machines,
filesystem variation and instrumentation. They are review thresholds, not CI
failures, until baselines exist for Linux, Windows and macOS.

| Engine / size | Load budget | Peak RSS budget | Hit budget | Miss budget | Extra budget |
| --- | ---: | ---: | ---: | ---: | ---: |
| Spylls small | 250 ms | 40 MiB | 100 µs | 500 µs | 100 ms suggest |
| Spylls medium | 10 s | 250 MiB | 100 µs | 500 µs | 1.5 s suggest |
| Spylls very large | 90 s | 1400 MiB | 200 µs | 5 ms | 5 s suggest |
| PyThes small | 100 ms | 40 MiB | 500 µs | 100 µs | 20 µs cached hit |
| PyThes medium | 2.5 s | 80 MiB | 1 ms | 100 µs | 20 µs cached hit |
| PyThes very large | 12 s | 150 MiB | 5 ms | 100 µs | 20 µs cached hit |

A result requires investigation when it exceeds either its budget or twice the
previous like-for-like baseline. Reports must retain errors and timeouts rather
than silently dropping an incompatible dictionary.

## Architecture consequences

- Never load every installed spelling dictionary at startup.
- Load only the active spelling dictionary and do so outside the GUI thread.
- Load a thesaurus only when synonyms are first requested.
- Keep dictionary caches bounded and provide an unload path when languages
  change.
- Run Spylls suggestions outside the GUI thread; even `es_EC` measured 190 ms.
- Treat very large Spylls dictionaries as high-memory resources. The Mongolian
  case consumed about 1 GiB RSS on an 8 GiB machine.
- Keep lookup and suggestion budgets separate: fast lookup does not imply
  interactive suggestion latency.
- Re-run the same matrix after engine changes and before release packaging on
  every supported platform.

