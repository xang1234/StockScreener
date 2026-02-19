"""High-Tight-Flag detector entrypoint.

Expected input orientation:
- Chronological daily bars (oldest -> newest).
- Pole and flag phases use strictly historical windows.

TODO(SE-C3a): Implement pole candidate identification over configurable windows.
TODO(SE-C3b): Implement flag validation and pivot extraction.
"""

from __future__ import annotations

from app.analysis.patterns.config import SetupEngineParameters
from app.analysis.patterns.detectors.base import (
    PatternDetector,
    PatternDetectorInput,
    PatternDetectorResult,
)


class HighTightFlagDetector(PatternDetector):
    """Compile-safe entrypoint for HTF detection."""

    name = "high_tight_flag"

    def detect(
        self,
        detector_input: PatternDetectorInput,
        parameters: SetupEngineParameters,
    ) -> PatternDetectorResult:
        del parameters
        if detector_input.daily_bars < 180:
            return PatternDetectorResult(
                detector_name=self.name,
                candidate=None,
                failed_checks=("insufficient_data", "daily_bars_lt_180"),
                warnings=("high_tight_flag_insufficient_data",),
            )

        return PatternDetectorResult(
            detector_name=self.name,
            candidate=None,
            failed_checks=("detector_not_implemented",),
            warnings=("high_tight_flag_stub",),
        )
