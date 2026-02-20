"""Tests for deterministic detector orchestration in the aggregator."""

from app.analysis.patterns.aggregator import SetupEngineAggregator
from app.analysis.patterns.config import DEFAULT_SETUP_ENGINE_PARAMETERS
from app.analysis.patterns.detectors.base import (
    PatternDetector,
    PatternDetectorInput,
    PatternDetectorResult,
)
from app.analysis.patterns.models import PatternCandidateModel


def _detector_input() -> PatternDetectorInput:
    return PatternDetectorInput(
        symbol="AAPL",
        timeframe="daily",
        daily_bars=260,
        weekly_bars=60,
        features={},
    )


def test_aggregator_execution_trace_preserves_detector_order():
    class _DetectorAlpha(PatternDetector):
        name = "detector_alpha"

        def detect(self, detector_input, parameters):
            del detector_input, parameters
            return PatternDetectorResult.detected(
                self.name,
                PatternCandidateModel(
                    pattern="vcp",
                    timeframe="daily",
                    source_detector=self.name,
                    quality_score=80.0,
                    readiness_score=78.0,
                    confidence=0.74,
                ),
                passed_checks=("alpha_pass",),
                warnings=("alpha_warning",),
            )

    class _DetectorBeta(PatternDetector):
        name = "detector_beta"

        def detect(self, detector_input, parameters):
            del detector_input, parameters
            return PatternDetectorResult.no_detection(
                self.name,
                failed_checks=("beta_miss",),
                warnings=("beta_warning",),
            )

    agg = SetupEngineAggregator(detectors=[_DetectorAlpha(), _DetectorBeta()])
    first = agg.aggregate(_detector_input(), parameters=DEFAULT_SETUP_ENGINE_PARAMETERS)
    second = agg.aggregate(_detector_input(), parameters=DEFAULT_SETUP_ENGINE_PARAMETERS)

    assert [c["source_detector"] for c in first.candidates] == [
        c["source_detector"] for c in second.candidates
    ]
    assert [trace.detector_name for trace in first.detector_traces] == [
        "detector_alpha",
        "detector_beta",
    ]
    assert [trace.execution_index for trace in first.detector_traces] == [0, 1]
    assert first.detector_traces[0].outcome == "detected"
    assert first.detector_traces[1].outcome == "not_detected"
    assert first.pattern_primary == "vcp"
    assert "detector_pipeline_executed" in first.passed_checks


def test_aggregator_trace_includes_detector_errors():
    class _BrokenDetector(PatternDetector):
        name = "detector_broken"

        def detect(self, detector_input, parameters):
            del detector_input, parameters
            raise RuntimeError("boom")

    agg = SetupEngineAggregator(detectors=[_BrokenDetector()])
    result = agg.aggregate(_detector_input(), parameters=DEFAULT_SETUP_ENGINE_PARAMETERS)

    assert "detector_broken:error" in result.failed_checks
    assert len(result.detector_traces) == 1
    trace = result.detector_traces[0]
    assert trace.outcome == "error"
    assert trace.error_detail is not None
    assert "RuntimeError: boom" in trace.error_detail
