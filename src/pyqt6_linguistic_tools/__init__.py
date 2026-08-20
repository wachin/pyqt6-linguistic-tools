"""Cross-platform linguistic services for Python and PyQt6 applications."""

from pyqt6_linguistic_tools.backends import (
    PyThesBackend,
    SpellCheckerBackend,
    SpyllsBackend,
    ThesaurusBackend,
)
from pyqt6_linguistic_tools.cache import BackendCache
from pyqt6_linguistic_tools.errors import (
    BackendOperationError,
    BackendUnavailableError,
    DictionaryLoadError,
    DictionaryNotFoundError,
    LinguisticError,
    UnsupportedOperationError,
)
from pyqt6_linguistic_tools.models import (
    BackendCapabilities,
    BackendMetadata,
    DictionaryMetadata,
    ThesaurusEntry,
    ThesaurusMeaning,
)

__version__ = "0.1.0.dev0"

__all__ = [
    "BackendCache",
    "BackendCapabilities",
    "BackendMetadata",
    "BackendOperationError",
    "BackendUnavailableError",
    "DictionaryLoadError",
    "DictionaryMetadata",
    "DictionaryNotFoundError",
    "LinguisticError",
    "PyThesBackend",
    "SpellCheckerBackend",
    "SpyllsBackend",
    "ThesaurusBackend",
    "ThesaurusEntry",
    "ThesaurusMeaning",
    "UnsupportedOperationError",
    "__version__",
]
