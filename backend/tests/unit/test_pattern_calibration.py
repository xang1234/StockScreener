"""Tests for cross-detector score normalization and calibration."""

import pytest

from app.analysis.patterns.aggregator import SetupEngineAggregator
from app.analysis.patterns.calibration import (
    aggregation_rank_score,
    calibrate_candidate_scores,
)
from app.analysis.patterns.config import DEFAULT_SETUP_ENGINE_PARAMETERS
from app.analysis.patterns.detectors.base import (
    PatternDetector,
    PatternDetectorInput,
    PatternDetectorResult,
)
from app.analysis.patterns.models import PatternCandidateModel


def test_calibrate_candidate_adds_canonical_metric_keys():
    calibrated = calibrate_candidate_scores(
        {
            "pattern": "vcp",
            "timeframe": "daily",
            "source_detector": "vcp",
            "quality_score": 72.0,
            "readiness_score": 70.0,
            "confidence": 0.68,
            "metrics": {"legacy_metric": 1.0},
            "checks": {},
            "notes": [],
        }
    )

    assert calibrated["metrics"]["calibration_version"] == "cross_detector_v1"
    assert calibrated["metrics"]["raw_quality_score"] == pytest.approx(72.0)
    assert calibrated["metrics"]["raw_readiness_score"] == pytest.approx(70.0)
    assert calibrated["metrics"]["raw_confidence"] == pytest.approx(0.68)
    assert calibrated["metrics"]["calibrated_quality_score"] == pytest.approx(
        calibrated["quality_score"]
    )
    assert calibrated["metrics"]["calibrated_readiness_score"] == pytest.approx(
        calibrated["readiness_score"]
    )
    assert calibrated["confidence_pct"] == pytest.approx(
        calibrated["confidence"] * 100.0
    )
    assert "cross_detector_calibration_v1_applied" in calibrated["notes"]


def test_calibration_rescales_detector_specific_score_ranges():
    nr7 = calibrate_candidate_scores(
        {
            "pattern": "nr7_inside_day",
            "timeframe": "daily",
            "source_detector": "nr7_inside_day",
            "quality_score": 60.0,
            "readiness_score": 62.0,
            "confidence": 0.60,
            "metrics": {},
            "checks": {},
            "notes": [],
        }
    )
    vcp = calibrate_candidate_scores(
        {
            "pattern": "vcp",
            "timeframe": "daily",
            "source_detector": "vcp",
            "quality_score": 60.0,
            "readiness_score": 62.0,
            "confidence": 0.60,
            "metrics": {},
            "checks": {},
            "notes": [],
        }
    )

    # Same raw values imply different calibrated semantics per detector profile.
    assert nr7["quality_score"] > vcp["quality_score"]
    assert nr7["readiness_score"] > vcp["readiness_score"]


def test_aggregator_primary_selection_uses_calibrated_rank():
    class _Nr7Detector(PatternDetector):
        name = "nr7_inside_day"

        def detect(self, detector_input, parameters):
            del detector_input, parameters
            return PatternDetectorResult.detected(
                self.name,
                PatternCandidateModel(
                    pattern=self.name,
                    timeframe="daily",
                    source_detector=self.name,
                    quality_score=50.0,
                    readiness_score=52.0,
                    confidence=0.78,
                ),
            )

    class _VcpDetector(PatternDetector):
        name = "vcp"

        def detect(self, detector_input, parameters):
            del detector_input, parameters
            return PatternDetectorResult.detected(
                self.name,
                PatternCandidateModel(
                    pattern=self.name,
                    timeframe="daily",
                    source_detector=self.name,
                    quality_score=88.0,
                    readiness_score=90.0,
                    confidence=0.72,
                ),
            )

    aggregator = SetupEngineAggregator(detectors=[_Nr7Detector(), _VcpDetector()])
    result = aggregator.aggregate(
        PatternDetectorInput(
            symbol="AAPL",
            timeframe="daily",
            daily_bars=260,
            weekly_bars=60,
            features={},
        ),
        parameters=DEFAULT_SETUP_ENGINE_PARAMETERS,
    )

    assert result.pattern_primary == "vcp"
    assert "cross_detector_calibration_applied" in result.passed_checks
    primary = next(
        candidate
        for candidate in result.candidates
        if candidate["pattern"] == result.pattern_primary
    )
    assert primary["metrics"]["aggregation_rank_score"] == pytest.approx(
        aggregation_rank_score(primary)
    )
    assert result.pattern_confidence == pytest.approx(primary["confidence_pct"])
