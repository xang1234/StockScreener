"""Pattern aggregation entrypoint for Setup Engine analysis layer.

TODO(SE-B7): Emit typed SetupEngineReport-compatible aggregation output.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.analysis.patterns.calibration import (
    aggregation_rank_score,
    calibrate_candidates_for_aggregation,
)
from app.analysis.patterns.config import (
    DEFAULT_SETUP_ENGINE_PARAMETERS,
    SetupEngineParameters,
    assert_valid_setup_engine_parameters,
)
from app.analysis.patterns.detectors import (
    DetectorOutcome,
    PatternDetector,
    PatternDetectorInput,
    default_pattern_detectors,
)
from app.analysis.patterns.models import PatternCandidate
from app.analysis.patterns.policy import (
    SetupEngineDataPolicyResult,
    policy_failed_checks,
    policy_invalidation_flags,
)


@dataclass(frozen=True)
class DetectorExecutionTrace:
    """Deterministic execution trace row for one detector call."""

    execution_index: int
    detector_name: str
    outcome: str
    candidate_count: int
    passed_checks: tuple[str, ...]
    failed_checks: tuple[str, ...]
    warnings: tuple[str, ...]
    error_detail: str | None


@dataclass(frozen=True)
class AggregatedPatternOutput:
    """Normalized detector output consumed by scanner payload assembly."""

    pattern_primary: str | None
    pattern_confidence: float | None
    pivot_price: float | None
    pivot_type: str | None
    pivot_date: str | None
    candidates: tuple[PatternCandidate, ...]
    passed_checks: tuple[str, ...]
    failed_checks: tuple[str, ...]
    key_levels: dict[str, float | None]
    invalidation_flags: tuple[str, ...]
    diagnostics: tuple[str, ...]
    detector_traces: tuple[DetectorExecutionTrace, ...]


class SetupEngineAggregator:
    """Run detectors and normalize candidates for setup_engine payload use."""

    def __init__(self, detectors: Sequence[PatternDetector] | None = None):
        self._detectors: tuple[PatternDetector, ...] = tuple(
            detectors if detectors is not None else default_pattern_detectors()
        )

    def aggregate(
        self,
        detector_input: PatternDetectorInput,
        *,
        parameters: SetupEngineParameters = DEFAULT_SETUP_ENGINE_PARAMETERS,
        policy_result: SetupEngineDataPolicyResult | None = None,
    ) -> AggregatedPatternOutput:
        """Run detectors without leaking scanner concerns into analysis layer."""
        assert_valid_setup_engine_parameters(parameters)

        candidates: list[PatternCandidate] = []
        passed_checks: list[str] = []
        failed_checks: list[str] = []
        diagnostics: list[str] = []
        invalidation_flags: list[str] = []
        key_levels: dict[str, float | None] = {}
        detector_traces: list[DetectorExecutionTrace] = []

        for idx, detector in enumerate(self._detectors):
            result = detector.detect_safe(detector_input, parameters)
            detector_traces.append(
                DetectorExecutionTrace(
                    execution_index=idx,
                    detector_name=detector.name,
                    outcome=result.outcome.value,
                    candidate_count=len(result.candidates),
                    passed_checks=tuple(result.passed_checks),
                    failed_checks=tuple(result.failed_checks),
                    warnings=tuple(result.warnings),
                    error_detail=result.error_detail,
                )
            )

            if result.outcome == DetectorOutcome.ERROR:
                failed_checks.append(
                    f"{detector.name}:{DetectorOutcome.ERROR.value}"
                )
                if result.error_detail:
                    diagnostics.append(
                        f"{detector.name}:{result.error_detail}"
                    )
                continue

            diagnostics.extend(result.warnings)
            passed_checks.extend(result.passed_checks)
            failed_checks.extend(result.failed_checks)

            # Candidates are already coerced by detect_safe().
            candidates.extend(result.candidates)

        calibrated_candidates = list(calibrate_candidates_for_aggregation(candidates))
        calibration_applied = bool(calibrated_candidates)
        candidates = calibrated_candidates

        primary = _pick_primary_candidate(candidates)

        if policy_result is not None:
            failed_checks.extend(policy_failed_checks(policy_result))
            invalidation_flags.extend(policy_invalidation_flags(policy_result))
            if policy_result["status"] == "insufficient":
                candidates = []
                primary = None
                calibration_applied = False

        if calibration_applied and candidates:
            passed_checks.append("cross_detector_calibration_applied")
        if detector_traces:
            passed_checks.append("detector_pipeline_executed")

        if primary is None:
            failed_checks.append("no_primary_pattern")
        else:
            passed_checks.append("primary_pattern_selected")
            key_levels["pivot_price"] = primary.get("pivot_price")

        return AggregatedPatternOutput(
            pattern_primary=primary.get("pattern") if primary else None,
            pattern_confidence=primary.get("confidence_pct") if primary else None,
            pivot_price=primary.get("pivot_price") if primary else None,
            pivot_type=primary.get("pivot_type") if primary else None,
            pivot_date=primary.get("pivot_date") if primary else None,
            candidates=tuple(candidates),
            passed_checks=tuple(_stable_unique(passed_checks)),
            failed_checks=tuple(_stable_unique(failed_checks)),
            key_levels=key_levels,
            invalidation_flags=tuple(_stable_unique(invalidation_flags)),
            diagnostics=tuple(diagnostics),
            detector_traces=tuple(detector_traces),
        )


def _pick_primary_candidate(candidates: Sequence[PatternCandidate]) -> PatternCandidate | None:
    if not candidates:
        return None

    def _confidence(candidate: PatternCandidate) -> float:
        raw = candidate.get("confidence")
        if raw is None and candidate.get("confidence_pct") is not None:
            raw = float(candidate["confidence_pct"]) / 100.0
        if raw is None:
            return float("-inf")
        return float(raw)

    def _distance_score(candidate: PatternCandidate) -> float:
        distance = candidate.get("distance_to_pivot_pct")
        if distance is None:
            return float("-inf")
        return -abs(float(distance))

    def _score(candidate: PatternCandidate) -> tuple[float, float, float, float]:
        confidence = _confidence(candidate)
        quality = (
            float(candidate.get("quality_score"))
            if candidate.get("quality_score") is not None
            else float("-inf")
        )
        readiness = (
            float(candidate.get("readiness_score"))
            if candidate.get("readiness_score") is not None
            else float("-inf")
        )
        return (
            aggregation_rank_score(candidate),
            confidence,
            readiness + quality,
            _distance_score(candidate),
        )

    return max(candidates, key=_score)


def _stable_unique(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            unique.append(value)
    return unique
