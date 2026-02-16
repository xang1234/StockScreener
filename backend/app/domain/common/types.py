"""Shared value types used across domain sub-packages.

These are thin wrappers that make function signatures self-documenting
and prevent primitive obsession (passing raw ints/strings everywhere).
"""

from __future__ import annotations

from typing import NewType

# Identifiers
ScanId = NewType("ScanId", int)
Ticker = NewType("Ticker", str)

# Scores are always 0-100 floats
Score = NewType("Score", float)
