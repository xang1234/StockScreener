"""Cross-detector score normalization and confidence calibration helpers.

This module enforces consistent scoring semantics across detector families
before aggregation/ranking chooses a primary candidate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.analysis.patterns.config import CANDIDATE_SETUP_SCORE_WEIGHTS
from app.analysis.patterns.models import PatternCandidate


@dataclass(frozen=True)
class DetectorCalibrationProfile:
    """Expected raw score envelopes for one detector family."""

    quality_min: float
    quality_max: float
    readiness_min: float
    readiness_max: float
    confidence_min: float
    confidence_max: float
    confidence_bias: float = 0.0


_DEFAULT_PROFILE = DetectorCalibrationProfile(
    quality_min=35.0,
    quality_max=95.0,
    readiness_min=35.0,
    readiness_max=95.0,
    confidence_min=0.20,
    confidence_max=0.95,
    confidence_bias=-0.01,
)


_PROFILE_BY_DETECTOR: dict[str, DetectorCalibrationProfile] = {
    "vcp": DetectorCalibrationProfile(
        quality_min=45.0,
        quality_max=95.0,
        readiness_min=45.0,
        readiness_max=95.0,
        confidence_min=0.25,
        confidence_max=0.95,
        confidence_bias=0.01,
    ),
    "three_weeks_tight": DetectorCalibrationProfile(
        quality_min=45.0,
        quality_max=95.0,
        readiness_min=50.0,
        readiness_max=95.0,
        confidence_min=0.35,
        confidence_max=0.95,
        confidence_bias=0.0,
    ),
    "high_tight_flag": DetectorCalibrationProfile(
        quality_min=45.0,
        quality_max=98.0,
        readiness_min=60.0,
        readiness_max=98.0,
        confidence_min=0.30,
        confidence_max=0.95,
        confidence_bias=0.03,
    ),
    "cup_with_handle": DetectorCalibrationProfile(
        quality_min=45.0,
        quality_max=95.0,
        readiness_min=45.0,
        readiness_max=95.0,
        confidence_min=0.30,
        confidence_max=0.95,
        confidence_bias=0.02,
    ),
    # Backward-compat alias used in older docs/tests.
    "cup_handle": DetectorCalibrationProfile(
        quality_min=45.0,
        quality_max=95.0,
        readiness_min=45.0,
        readiness_max=95.0,
        confidence_min=0.30,
        confidence_max=0.95,
        confidence_bias=0.02,
    ),
    "first_pullback": DetectorCalibrationProfile(
        quality_min=40.0,
        quality_max=95.0,
        readiness_min=35.0,
        readiness_max=90.0,
        confidence_min=0.25,
        confidence_max=0.95,
        confidence_bias=-0.02,
    ),
    "nr7_inside_day": DetectorCalibrationProfile(
        quality_min=20.0,
        quality_max=65.0,
        readiness_min=24.0,
        readiness_max=70.0,
        confidence_min=0.20,
        confidence_max=0.78,
        confidence_bias=-0.06,
    ),
    "double_bottom": DetectorCalibrationProfile(
        quality_min=45.0,
        quality_max=95.0,
        readiness_min=45.0,
        readiness_max=95.0,
        confidence_min=0.25,
        confidence_max=0.95,
        confidence_bias=-0.01,
    ),
}


def calibrate_candidates_for_aggregation(
    candidates: Sequence[PatternCandidate],
) -> tuple[PatternCandidate, ...]:
    """Return candidates with calibrated score/confidence semantics."""
    return tuple(calibrate_candidate_scores(candidate) for candidate in candidates)


def calibrate_candidate_scores(candidate: PatternCandidate) -> PatternCandidate:
    """Calibrate one candidate and annotate metrics with raw/calibrated values."""
    detector = str(
        candidate.get("source_detector")
        or candidate.get("pattern")
        or "unknown"
    )
    profile = _PROFILE_BY_DETECTOR.get(detector, _DEFAULT_PROFILE)

    raw_quality = _as_float(candidate.get("quality_score"))
    raw_readiness = _as_float(candidate.get("readiness_score"))
    raw_confidence = _extract_confidence(candidate)

    quality_norm = _normalize(raw_quality, profile.quality_min, profile.quality_max)
    readiness_norm = _normalize(
        raw_readiness, profile.readiness_min, profile.readiness_max
    )
    confidence_norm = _normalize(
        raw_confidence, profile.confidence_min, profile.confidence_max
    )

    calibrated_quality = (
        round(_clamp(quality_norm * 100.0, 0.0, 100.0), 6)
        if quality_norm is not None
        else None
    )
    calibrated_readiness = (
        round(_clamp(readiness_norm * 100.0, 0.0, 100.0), 6)
        if readiness_norm is not None
        else None
    )
    calibrated_confidence = _calibrate_confidence(
        confidence_norm=confidence_norm,
        quality_norm=quality_norm,
        readiness_norm=readiness_norm,
        confidence_bias=profile.confidence_bias,
    )
    calibrated_confidence_pct = (
        round(calibrated_confidence * 100.0, 6)
        if calibrated_confidence is not None
        else None
    )
    rank_score = round(
        _aggregation_rank_score_from_parts(
            confidence=calibrated_confidence,
            quality_score=calibrated_quality,
            readiness_score=calibrated_readiness,
        ),
        6,
    )

    # Per-candidate setup_score synthesis.
    wq, wr, wc = CANDIDATE_SETUP_SCORE_WEIGHTS
    if calibrated_quality is not None and calibrated_readiness is not None and calibrated_confidence is not None:
        candidate_setup_score = round(
            _clamp(
                wq * calibrated_quality + wr * calibrated_readiness + wc * (calibrated_confidence * 100.0),
                0.0,
                100.0,
            ),
            6,
        )
    else:
        candidate_setup_score = None

    output: PatternCandidate = dict(candidate)
    output["quality_score"] = calibrated_quality
    output["readiness_score"] = calibrated_readiness
    output["confidence"] = calibrated_confidence
    output["confidence_pct"] = calibrated_confidence_pct
    output["setup_score"] = candidate_setup_score

    metrics = dict(output.get("metrics") or {})
    metrics.update(
        {
            "calibration_version": "cross_detector_v1",
            "calibration_source_detector": detector,
            "raw_quality_score": _round_or_none(raw_quality),
            "raw_readiness_score": _round_or_none(raw_readiness),
            "raw_confidence": _round_or_none(raw_confidence),
            "raw_confidence_pct": (
                round(raw_confidence * 100.0, 6)
                if raw_confidence is not None
                else None
            ),
            "normalized_quality_score_0_1": _round_or_none(quality_norm),
            "normalized_readiness_score_0_1": _round_or_none(readiness_norm),
            "normalized_confidence_0_1": _round_or_none(confidence_norm),
            "calibrated_quality_score": calibrated_quality,
            "calibrated_readiness_score": calibrated_readiness,
            "calibrated_confidence": calibrated_confidence,
            "calibrated_confidence_pct": calibrated_confidence_pct,
            "aggregation_rank_score": rank_score,
            "candidate_setup_score": candidate_setup_score,
            "setup_score_method": "candidate_blend_v1",
        }
    )
    output["metrics"] = metrics

    notes = list(output.get("notes") or [])
    if "cross_detector_calibration_v1_applied" not in notes:
        notes.append("cross_detector_calibration_v1_applied")
    output["notes"] = notes
    return output


def aggregation_rank_score(candidate: PatternCandidate) -> float:
    """Composite ranking score used for deterministic primary selection."""
    return _aggregation_rank_score_from_parts(
        confidence=_extract_confidence(candidate),
        quality_score=_as_float(candidate.get("quality_score")),
        readiness_score=_as_float(candidate.get("readiness_score")),
    )


def _aggregation_rank_score_from_parts(
    *,
    confidence: float | None,
    quality_score: float | None,
    readiness_score: float | None,
) -> float:
    conf = _clamp(confidence or 0.0, 0.0, 1.0)
    quality_component = (
        _clamp((quality_score or 0.0) / 100.0, 0.0, 1.0)
        if quality_score is not None
        else conf
    )
    readiness_component = (
        _clamp((readiness_score or 0.0) / 100.0, 0.0, 1.0)
        if readiness_score is not None
        else conf
    )
    return _clamp(
        conf * 0.55 + quality_component * 0.25 + readiness_component * 0.20,
        0.0,
        1.0,
    )


def _calibrate_confidence(
    *,
    confidence_norm: float | None,
    quality_norm: float | None,
    readiness_norm: float | None,
    confidence_bias: float,
) -> float | None:
    weighted_norm = _weighted_mean_defined(
        ((confidence_norm, 0.55), (quality_norm, 0.25), (readiness_norm, 0.20))
    )
    if weighted_norm is None:
        return None
    return round(_clamp(weighted_norm + confidence_bias, 0.05, 0.95), 6)


def _extract_confidence(candidate: PatternCandidate) -> float | None:
    confidence = _as_float(candidate.get("confidence"))
    if confidence is not None:
        return _clamp(confidence, 0.0, 1.0)

    confidence_pct = _as_float(candidate.get("confidence_pct"))
    if confidence_pct is None:
        return None
    return _clamp(confidence_pct / 100.0, 0.0, 1.0)


def _normalize(value: float | None, lower: float, upper: float) -> float | None:
    if value is None:
        return None
    if upper <= lower:
        return _clamp(value, 0.0, 1.0)
    return _clamp((value - lower) / (upper - lower), 0.0, 1.0)


def _weighted_mean_defined(
    values: Sequence[tuple[float | None, float]],
) -> float | None:
    total = 0.0
    total_weight = 0.0
    for value, weight in values:
        if value is None:
            continue
        total += value * weight
        total_weight += weight
    if total_weight <= 0.0:
        return None
    return total / total_weight


def _as_float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _round_or_none(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 6)


def _clamp(value: float, lower: float, upper: float) -> float:
    return min(upper, max(lower, value))
