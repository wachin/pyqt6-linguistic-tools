# Error handling and component isolation

`LinguisticService` is tolerant by default because a damaged optional
dictionary must not crash a text editor or make every word appear misspelled.
It returns conservative fallbacks:

- spelling accepts a word when its official backend is unavailable;
- suggestions return an empty tuple;
- thesaurus lookup returns `None` and synonyms return an empty tuple;
- healthy locales and the healthy component of the same locale remain usable.

Invalid caller arguments still raise `TypeError` or `ValueError`. Set
`strict=True` when tests or command-line validation need the original toolkit
exception.

## Structured diagnostics

Each recovered failure produces `LinguisticServiceDiagnostic`. It contains the
operation, exact locale, toolkit error type, message, backend, source path,
optional spelling/thesaurus component, disabled state, and the underlying
cause type and message. Diagnostics are bounded and available through
`service.diagnostics()`.

Applications may bridge them to Python logging without coupling the core to a
particular logging configuration:

```python
import logging

from pyqt6_linguistic_tools import (
    LinguisticService,
    logging_diagnostic_handler,
)

service = LinguisticService(
    "es_EC",
    diagnostic_handler=logging_diagnostic_handler(
        logging.getLogger("guitarchordstudio.linguistic")
    ),
)
```

## Per-component circuit breaker

The first recoverable backend failure disables only the exact `(locale,
component)` pair. For example, broken `en_US` MyThes data does not disable
`en_US` spelling or any `es_EC` resource. Subsequent calls use safe fallbacks
without repeatedly loading the same malformed file or flooding diagnostics.

```python
failure = service.component_failure("en_US", "thesaurus")
all_failures = service.disabled_components()

# After repairing or replacing the files:
service.retry_component("en_US", "thesaurus")
```

`refresh_dictionaries()` clears component failures, unloads stale engines, and
retries discovery. A registry revision change has the same invalidation
effect. Clearing diagnostic history does not silently reactivate a broken
component.

## Provider isolation and validation

The service uses tolerant registry discovery: a failed provider records a
`DictionaryDiscoveryError`, while dictionaries returned by other providers
remain available. Direct `DictionaryRegistry` calls remain strict unless the
caller explicitly passes `tolerate_provider_errors=True`.

`DictionaryValidator` detects absent files, unknown or invalid encodings,
malformed Hunspell rules, malformed MyThes data and unsafe indexes before a
manual import is published. Runtime backends translate engine exceptions into
stable toolkit errors and retain their original causes in diagnostics.
