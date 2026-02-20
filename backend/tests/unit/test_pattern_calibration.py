"""Tests for cross-detector score normalization and calibration."""

import pytest

from app.analysis.patterns.aggregator import SetupEngineAggregator
from app.analysis.patterns.calibration import (
    aggregation_rank_score,
    calibrate_candidate_scores,
)
from app.analysis.patterns.config import (
    CANDIDATE_SETUP_SCORE_WEIGHTS,
    DEFAULT_SETUP_ENGINE_PARAMETERS,
)
from app.analysis.patterns.detectors.base import (
    PatternDetector,
    PatternDetectorInput,
    PatternDetectorResult,
)
from app.analysis.patterns.models import PatternCandidateModel
from app.analysis.patterns.policy import evaluate_setup_engine_data_policy


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


def test_cup_with_handle_detector_uses_family_profile():
    cup_with_handle = calibrate_candidate_scores(
        {
            "pattern": "cup_with_handle",
            "timeframe": "daily",
            "source_detector": "cup_with_handle",
            "quality_score": 70.0,
            "readiness_score": 72.0,
            "confidence": 0.70,
            "metrics": {},
            "checks": {},
            "notes": [],
        }
    )
    cup_handle_alias = calibrate_candidate_scores(
        {
            "pattern": "cup_handle",
            "timeframe": "daily",
            "source_detector": "cup_handle",
            "quality_score": 70.0,
            "readiness_score": 72.0,
            "confidence": 0.70,
            "metrics": {},
            "checks": {},
            "notes": [],
        }
    )

    assert cup_with_handle["quality_score"] == pytest.approx(
        cup_handle_alias["quality_score"]
    )
    assert cup_with_handle["readiness_score"] == pytest.approx(
        cup_handle_alias["readiness_score"]
    )
    assert cup_with_handle["confidence"] == pytest.approx(
        cup_handle_alias["confidence"]
    )


def test_missing_scores_and_confidence_remain_null_after_calibration():
    calibrated = calibrate_candidate_scores(
        {
            "pattern": "vcp",
            "timeframe": "daily",
            "source_detector": "vcp",
            "quality_score": None,
            "readiness_score": None,
            "confidence": None,
            "metrics": {},
            "checks": {},
            "notes": [],
        }
    )

    assert calibrated["quality_score"] is None
    assert calibrated["readiness_score"] is None
    assert calibrated["confidence"] is None
    assert calibrated["confidence_pct"] is None
    assert calibrated["metrics"]["normalized_quality_score_0_1"] is None
    assert calibrated["metrics"]["normalized_readiness_score_0_1"] is None
    assert calibrated["metrics"]["normalized_confidence_0_1"] is None
    assert calibrated["metrics"]["calibrated_confidence"] is None
    assert calibrated["metrics"]["calibrated_confidence_pct"] is None


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


def test_policy_insufficient_does_not_emit_calibration_applied_check():
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

    policy = evaluate_setup_engine_data_policy(
        daily_bars=100,
        weekly_bars=30,
        benchmark_bars=20,
        current_week_sessions=1,
    )
    aggregator = SetupEngineAggregator(detectors=[_VcpDetector()])
    result = aggregator.aggregate(
        PatternDetectorInput(
            symbol="AAPL",
            timeframe="daily",
            daily_bars=260,
            weekly_bars=60,
            features={},
        ),
        parameters=DEFAULT_SETUP_ENGINE_PARAMETERS,
        policy_result=policy,
    )

    assert result.candidates == ()
    assert "cross_detector_calibration_applied" not in result.passed_checks


# ── SE-D4: Per-candidate setup_score tests ────────────────────


def test_calibrated_candidate_has_setup_score():
    calibrated = calibrate_candidate_scores(
        {
            "pattern": "vcp",
            "timeframe": "daily",
            "source_detector": "vcp",
            "quality_score": 72.0,
            "readiness_score": 70.0,
            "confidence": 0.68,
            "metrics": {},
            "checks": {},
            "notes": [],
        }
    )

    assert calibrated["setup_score"] is not None
    assert 0.0 <= calibrated["setup_score"] <= 100.0


def test_candidate_setup_score_formula():
    calibrated = calibrate_candidate_scores(
        {
            "pattern": "vcp",
            "timeframe": "daily",
            "source_detector": "vcp",
            "quality_score": 72.0,
            "readiness_score": 70.0,
            "confidence": 0.68,
            "metrics": {},
            "checks": {},
            "notes": [],
        }
    )

    wq, wr, wc = CANDIDATE_SETUP_SCORE_WEIGHTS
    expected = (
        wq * calibrated["quality_score"]
        + wr * calibrated["readiness_score"]
        + wc * (calibrated["confidence"] * 100.0)
    )
    assert calibrated["setup_score"] == pytest.approx(expected, abs=1e-4)


def test_candidate_setup_score_method_in_metrics():
    calibrated = calibrate_candidate_scores(
        {
            "pattern": "vcp",
            "timeframe": "daily",
            "source_detector": "vcp",
            "quality_score": 72.0,
            "readiness_score": 70.0,
            "confidence": 0.68,
            "metrics": {},
            "checks": {},
            "notes": [],
        }
    )

    assert calibrated["metrics"]["setup_score_method"] == "candidate_blend_v1"
    assert calibrated["metrics"]["candidate_setup_score"] == pytest.approx(
        calibrated["setup_score"]
    )
