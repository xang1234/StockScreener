"""Three-Weeks-Tight / Multi-Weeks-Tight detector entrypoint.

Expected input orientation:
- Weekly bars derived from chronological daily bars.
- Current incomplete week excluded unless policy explicitly permits.

TODO(SE-C2): Implement strict/relaxed tightness scoring and pivot extraction.
"""

from __future__ import annotations

from app.analysis.patterns.config import SetupEngineParameters
from app.analysis.patterns.detectors.base import (
    PatternDetector,
    PatternDetectorInput,
    PatternDetectorResult,
)


class ThreeWeeksTightDetector(PatternDetector):
    """Compile-safe entrypoint for 3WT/MWT detection."""

    name = "three_weeks_tight"

    def detect(
        self,
        detector_input: PatternDetectorInput,
        parameters: SetupEngineParameters,
    ) -> PatternDetectorResult:
        del parameters
        if detector_input.weekly_bars < 8:
            return PatternDetectorResult(
                detector_name=self.name,
                candidate=None,
                failed_checks=("insufficient_data", "weekly_bars_lt_8"),
                warnings=("three_weeks_tight_insufficient_data",),
            )

        return PatternDetectorResult(
            detector_name=self.name,
            candidate=None,
            failed_checks=("detector_not_implemented",),
            warnings=("three_weeks_tight_stub",),
        )
