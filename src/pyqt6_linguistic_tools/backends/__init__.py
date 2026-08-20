"""Public backend contracts and portable engine adapters."""

from pyqt6_linguistic_tools.backends.base import (
    LinguisticBackend,
    SpellCheckerBackend,
    ThesaurusBackend,
)
from pyqt6_linguistic_tools.backends.pythes import PyThesBackend
from pyqt6_linguistic_tools.backends.spylls import SpyllsBackend

__all__ = [
    "LinguisticBackend",
    "PyThesBackend",
    "SpellCheckerBackend",
    "SpyllsBackend",
    "ThesaurusBackend",
]

