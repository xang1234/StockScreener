"""Compatibility alias for cup-with-handle detector entrypoint."""

from app.analysis.patterns.cup_handle import CupHandleDetector


class CupWithHandleDetector(CupHandleDetector):
    """Backward-compatible name retained for existing imports."""
