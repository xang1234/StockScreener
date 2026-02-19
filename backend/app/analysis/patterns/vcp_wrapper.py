"""VCP detector entrypoint wrapper.

Expected input orientation:
- Chronological features (oldest -> newest).
- No look-ahead assumptions.

TODO(SE-C1): Wrap existing criteria/vcp_detection implementation without logic fork.
"""

from __future__ import annotations

from app.analysis.patterns.config import SetupEngineParameters
from app.analysis.patterns.detectors.base import (
    PatternDetector,
    PatternDetectorInput,
    PatternDetectorResult,
)


class VCPWrapperDetector(PatternDetector):
    """Compile-safe entrypoint for VCP integration."""

    name = "vcp"

    def detect(
        self,
        detector_input: PatternDetectorInput,
        parameters: SetupEngineParameters,
    ) -> PatternDetectorResult:
        del parameters
        if detector_input.daily_bars < 120:
            return PatternDetectorResult(
                detector_name=self.name,
                candidate=None,
                failed_checks=("insufficient_data", "daily_bars_lt_120"),
                warnings=("vcp_wrapper_insufficient_data",),
            )

        return PatternDetectorResult(
            detector_name=self.name,
            candidate=None,
            failed_checks=("detector_not_implemented",),
            warnings=("vcp_wrapper_stub",),
        )
