"""Compatibility alias for VCP wrapper detector entrypoint."""

from app.analysis.patterns.vcp_wrapper import VCPWrapperDetector


class VCPDetector(VCPWrapperDetector):
    """Backward-compatible name retained for existing imports."""
