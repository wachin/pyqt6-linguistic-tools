"""Spell-highlighting boundary.

Phase 23 implements the narrow ``QSyntaxHighlighter`` adapter here. It will
tokenize blocks and query cached spelling state, never discover or download
dictionaries and never generate suggestions while painting.
"""

__all__: list[str] = []
