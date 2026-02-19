"""Double-bottom detector stub.

Expected input orientation:
- Weekly or daily features in chronological order (oldest -> newest).

TODO(SE-C7): Calibrate and normalize double-bottom confidence against other families.
"""

from __future__ import annotations

from app.analysis.patterns.config import SetupEngineParameters
from app.analysis.patterns.detectors.base import (
    PatternDetector,
    PatternDetectorInput,
    PatternDetectorResult,
)
from app.analysis.patterns.normalization import normalize_detector_input_ohlcv


class DoubleBottomDetector(PatternDetector):
    """Placeholder detector implementation with deterministic fallback."""

    name = "double_bottom"

    def detect(
        self,
        detector_input: PatternDetectorInput,
        parameters: SetupEngineParameters,
    ) -> PatternDetectorResult:
        del parameters
        normalized_weekly = normalize_detector_input_ohlcv(
            features=detector_input.features,
            timeframe="weekly",
            min_bars=10,
            feature_key="weekly_ohlcv",
            fallback_bar_count=detector_input.weekly_bars,
        )
        normalized_daily = normalize_detector_input_ohlcv(
            features=detector_input.features,
            timeframe="daily",
            min_bars=80,
            feature_key="daily_ohlcv",
            fallback_bar_count=detector_input.daily_bars,
        )

        if (not normalized_weekly.prerequisites_ok) and (
            not normalized_daily.prerequisites_ok
        ):
            # Merge checks/warnings from both timeframes.
            failed = tuple(
                dict.fromkeys(
                    normalized_weekly.failed_checks
                    + normalized_daily.failed_checks
                )
            )
            warns = tuple(
                dict.fromkeys(
                    normalized_weekly.warnings + normalized_daily.warnings
                )
            )
            return PatternDetectorResult.insufficient_data(
                self.name, failed_checks=failed, warnings=warns
            )

        # Merge warnings from both timeframes for the stub path.
        all_warnings = tuple(
            dict.fromkeys(
                normalized_weekly.warnings + normalized_daily.warnings
            )
        )
        return PatternDetectorResult.not_implemented(
            self.name, warnings=all_warnings
        )
