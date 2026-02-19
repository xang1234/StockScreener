"""Pattern detector registry for Setup Engine analysis layer."""

from app.analysis.patterns.detectors.base import (
    DetectorOutcome,
    PatternDetector,
    PatternDetectorInput,
    PatternDetectorResult,
)
from app.analysis.patterns.first_pullback import FirstPullbackDetector
from app.analysis.patterns.high_tight_flag import HighTightFlagDetector
from app.analysis.patterns.nr7_inside_day import NR7InsideDayDetector
from app.analysis.patterns.three_weeks_tight import ThreeWeeksTightDetector
from app.analysis.patterns.detectors.cup_with_handle import CupWithHandleDetector
from app.analysis.patterns.detectors.double_bottom import DoubleBottomDetector
from app.analysis.patterns.detectors.vcp import VCPDetector


def default_pattern_detectors() -> tuple[PatternDetector, ...]:
    """Return the default v1 detector set in stable execution order."""
    return (
        CupWithHandleDetector(),
        ThreeWeeksTightDetector(),
        HighTightFlagDetector(),
        FirstPullbackDetector(),
        VCPDetector(),
        NR7InsideDayDetector(),
        DoubleBottomDetector(),
    )


__all__ = [
    "DetectorOutcome",
    "PatternDetector",
    "PatternDetectorInput",
    "PatternDetectorResult",
    "CupWithHandleDetector",
    "DoubleBottomDetector",
    "FirstPullbackDetector",
    "HighTightFlagDetector",
    "NR7InsideDayDetector",
    "ThreeWeeksTightDetector",
    "VCPDetector",
    "default_pattern_detectors",
]
