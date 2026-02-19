"""NR7/Inside-Day trigger detector entrypoint.

Expected input orientation:
- Daily bars in chronological order.
- Trigger bars are evaluated on completed bars only.

TODO(SE-C5): Implement NR7, inside-day, and combined trigger subtype logic.
"""

from __future__ import annotations

from app.analysis.patterns.config import SetupEngineParameters
from app.analysis.patterns.detectors.base import (
    PatternDetector,
    PatternDetectorInput,
    PatternDetectorResult,
)


class NR7InsideDayDetector(PatternDetector):
    """Compile-safe entrypoint for trigger-family detection."""

    name = "nr7_inside_day"

    def detect(
        self,
        detector_input: PatternDetectorInput,
        parameters: SetupEngineParameters,
    ) -> PatternDetectorResult:
        del parameters
        if detector_input.daily_bars < 10:
            return PatternDetectorResult(
                detector_name=self.name,
                candidate=None,
                failed_checks=("insufficient_data", "daily_bars_lt_10"),
                warnings=("nr7_inside_day_insufficient_data",),
            )

        return PatternDetectorResult(
            detector_name=self.name,
            candidate=None,
            failed_checks=("detector_not_implemented",),
            warnings=("nr7_inside_day_stub",),
        )
