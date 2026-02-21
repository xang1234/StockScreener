"""Shared fixtures and composable assertion helpers for golden regression tests.

Golden tests pin known-good detector outputs as inline expectations.
The ``--golden-update`` flag writes actual outputs to ``snapshots/`` for
review before manually updating inline expectations.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
import pytest

from app.analysis.patterns.detectors import (
    DetectorOutcome,
    PatternDetectorInput,
    PatternDetectorResult,
)

SNAPSHOTS_DIR = Path(__file__).parent / "snapshots"


# ---------------------------------------------------------------------------
# pytest CLI flag
# ---------------------------------------------------------------------------


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--golden-update",
        action="store_true",
        default=False,
        help="Export actual detector outputs to snapshots/ for review",
    )


@pytest.fixture
def golden_update(request: pytest.FixtureRequest) -> bool:
    return request.config.getoption("--golden-update")


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def golden_ohlcv_frame(
    *,
    index: pd.DatetimeIndex,
    close: np.ndarray | Sequence[float],
    low: np.ndarray | Sequence[float] | None = None,
    high: np.ndarray | Sequence[float] | None = None,
    volume: np.ndarray | Sequence[float] | None = None,
    extra_cols: dict[str, np.ndarray | Sequence[float]] | None = None,
) -> pd.DataFrame:
    """Build a deterministic OHLCV DataFrame from close prices."""
    close_arr = np.asarray(close, dtype=float)
    n = len(close_arr)
    assert len(index) == n, f"index length {len(index)} != close length {n}"

    df = pd.DataFrame(
        {
            "Open": close_arr * 0.995,
            "High": close_arr * 1.01 if high is None else np.asarray(high, dtype=float),
            "Low": close_arr * 0.99 if low is None else np.asarray(low, dtype=float),
            "Close": close_arr,
            "Volume": (
                np.full(n, 1_000_000, dtype=float)
                if volume is None
                else np.asarray(volume, dtype=float)
            ),
        },
        index=index,
    )

    if extra_cols:
        for col_name, col_data in extra_cols.items():
            df[col_name] = np.asarray(col_data, dtype=float)

    return df


def golden_detector_input(
    *,
    symbol: str = "GOLDEN",
    timeframe: str = "daily",
    daily: pd.DataFrame | None = None,
    weekly: pd.DataFrame | None = None,
) -> PatternDetectorInput:
    """Wrap daily/weekly frames into a PatternDetectorInput."""
    features: dict[str, Any] = {}
    daily_bars = 0
    weekly_bars = 0

    if daily is not None:
        features["daily_ohlcv"] = daily
        daily_bars = len(daily)
    if weekly is not None:
        features["weekly_ohlcv"] = weekly
        weekly_bars = len(weekly)

    return PatternDetectorInput(
        symbol=symbol,
        timeframe=timeframe,
        daily_bars=daily_bars,
        weekly_bars=weekly_bars,
        features=features,
    )


# ---------------------------------------------------------------------------
# Composable assertion helpers
# ---------------------------------------------------------------------------


def assert_outcome(result: PatternDetectorResult, expected: str) -> None:
    """Exact match on result.outcome.value."""
    actual = result.outcome.value
    assert actual == expected, (
        f"outcome: expected {expected!r}, got {actual!r}"
    )


def assert_candidate_count(
    result: PatternDetectorResult,
    *,
    exact: int | None = None,
    min_count: int | None = None,
) -> None:
    """Assert candidate count (exact or minimum)."""
    actual = len(result.candidates)
    if exact is not None:
        assert actual == exact, (
            f"candidate_count: expected exactly {exact}, got {actual}"
        )
    if min_count is not None:
        assert actual >= min_count, (
            f"candidate_count: expected >= {min_count}, got {actual}"
        )


def assert_primary_fields(
    candidate: Mapping[str, Any],
    *,
    pattern: str | None = None,
    timeframe: str | None = None,
    pivot_type: str | None = None,
) -> None:
    """Exact string matches on structural candidate fields."""
    if pattern is not None:
        assert candidate["pattern"] == pattern, (
            f"pattern: expected {pattern!r}, got {candidate['pattern']!r}"
        )
    if timeframe is not None:
        assert candidate["timeframe"] == timeframe, (
            f"timeframe: expected {timeframe!r}, got {candidate['timeframe']!r}"
        )
    if pivot_type is not None:
        assert candidate["pivot_type"] == pivot_type, (
            f"pivot_type: expected {pivot_type!r}, got {candidate['pivot_type']!r}"
        )


def assert_pivot_type_contains(candidate: Mapping[str, Any], substring: str) -> None:
    """Assert pivot_type contains a substring."""
    actual = candidate.get("pivot_type") or ""
    assert substring in actual, (
        f"pivot_type {actual!r} does not contain {substring!r}"
    )


def assert_score_ranges(
    candidate: Mapping[str, Any],
    *,
    confidence: tuple[float, float] | None = None,
    quality_score: tuple[float, float] | None = None,
    readiness_score: tuple[float, float] | None = None,
) -> None:
    """Assert scores fall within (min, max) ranges."""
    if confidence is not None:
        val = candidate.get("confidence")
        assert val is not None, "confidence is None"
        lo, hi = confidence
        assert lo <= val <= hi, (
            f"confidence: expected [{lo}, {hi}], got {val}"
        )
    if quality_score is not None:
        val = candidate.get("quality_score")
        assert val is not None, "quality_score is None"
        lo, hi = quality_score
        assert lo <= val <= hi, (
            f"quality_score: expected [{lo}, {hi}], got {val}"
        )
    if readiness_score is not None:
        val = candidate.get("readiness_score")
        assert val is not None, "readiness_score is None"
        lo, hi = readiness_score
        assert lo <= val <= hi, (
            f"readiness_score: expected [{lo}, {hi}], got {val}"
        )


def assert_pivot_approx(
    candidate: Mapping[str, Any],
    *,
    approx: float,
    tolerance_pct: float,
) -> None:
    """Assert pivot_price is within tolerance_pct of approx."""
    val = candidate.get("pivot_price")
    assert val is not None, "pivot_price is None"
    diff_pct = abs(val - approx) / approx * 100.0
    assert diff_pct <= tolerance_pct, (
        f"pivot_price: expected ~{approx} +/-{tolerance_pct}%, got {val} "
        f"(diff={diff_pct:.2f}%)"
    )


def assert_checks(
    candidate: Mapping[str, Any],
    *,
    required_true: Sequence[str] | None = None,
    required_false: Sequence[str] | None = None,
) -> None:
    """Assert boolean checks on candidate['checks']."""
    checks = candidate.get("checks", {})
    if required_true:
        for key in required_true:
            assert checks.get(key) is True, (
                f"checks[{key!r}]: expected True, got {checks.get(key)!r}"
            )
    if required_false:
        for key in required_false:
            assert checks.get(key) is False, (
                f"checks[{key!r}]: expected False, got {checks.get(key)!r}"
            )


def assert_metrics_range(
    candidate: Mapping[str, Any],
    ranges_dict: dict[str, tuple[float, float]],
) -> None:
    """Assert metric values fall within (min, max) ranges."""
    metrics = candidate.get("metrics", {})
    for key, (lo, hi) in ranges_dict.items():
        val = metrics.get(key)
        assert val is not None, f"metrics[{key!r}] is None or missing"
        assert lo <= val <= hi, (
            f"metrics[{key!r}]: expected [{lo}, {hi}], got {val}"
        )


def assert_result_checks(
    result: PatternDetectorResult,
    *,
    passed_superset: Sequence[str] | None = None,
    failed_contains: Sequence[str] | None = None,
) -> None:
    """Assert result-level passed/failed checks."""
    if passed_superset:
        passed = set(result.passed_checks)
        for check in passed_superset:
            assert check in passed, (
                f"passed_checks missing {check!r}; have: {sorted(passed)}"
            )
    if failed_contains:
        failed = set(result.failed_checks)
        for check in failed_contains:
            assert check in failed, (
                f"failed_checks missing {check!r}; have: {sorted(failed)}"
            )


# ---------------------------------------------------------------------------
# Top-level orchestrators
# ---------------------------------------------------------------------------


def assert_golden_match(
    result: PatternDetectorResult,
    expectation: dict[str, Any],
) -> None:
    """Delegate to sub-functions based on expectation dict keys."""
    if "outcome" in expectation:
        assert_outcome(result, expectation["outcome"])

    if "candidate_count" in expectation:
        assert_candidate_count(result, exact=expectation["candidate_count"])
    if "candidate_count_min" in expectation:
        assert_candidate_count(result, min_count=expectation["candidate_count_min"])

    if "passed_checks_superset" in expectation:
        assert_result_checks(
            result, passed_superset=expectation["passed_checks_superset"]
        )
    if "failed_checks_contains" in expectation:
        assert_result_checks(
            result, failed_contains=expectation["failed_checks_contains"]
        )

    # Candidate-level assertions operate on the first candidate
    _CANDIDATE_KEYS = {
        "pattern", "pivot_type", "timeframe", "pivot_type_contains",
        "confidence", "quality_score", "readiness_score",
        "checks_true", "checks_false", "metrics_range", "pivot_approx",
    }
    candidate = result.candidates[0] if result.candidates else None

    if candidate is None and _CANDIDATE_KEYS & expectation.keys():
        raise AssertionError(
            "Expectation includes candidate-level keys "
            f"{sorted(_CANDIDATE_KEYS & expectation.keys())} "
            "but result has no candidates"
        )

    if candidate is not None:
        if "pattern" in expectation or "pivot_type" in expectation or "timeframe" in expectation:
            assert_primary_fields(
                candidate,
                pattern=expectation.get("pattern"),
                timeframe=expectation.get("timeframe"),
                pivot_type=expectation.get("pivot_type"),
            )
        if "pivot_type_contains" in expectation:
            assert_pivot_type_contains(candidate, expectation["pivot_type_contains"])
        if "confidence" in expectation:
            assert_score_ranges(candidate, confidence=expectation["confidence"])
        if "quality_score" in expectation:
            assert_score_ranges(candidate, quality_score=expectation["quality_score"])
        if "readiness_score" in expectation:
            assert_score_ranges(candidate, readiness_score=expectation["readiness_score"])
        if "checks_true" in expectation:
            assert_checks(candidate, required_true=expectation["checks_true"])
        if "checks_false" in expectation:
            assert_checks(candidate, required_false=expectation["checks_false"])
        if "metrics_range" in expectation:
            assert_metrics_range(candidate, expectation["metrics_range"])
        if "pivot_approx" in expectation:
            assert_pivot_approx(
                candidate,
                approx=expectation["pivot_approx"]["value"],
                tolerance_pct=expectation["pivot_approx"]["tolerance_pct"],
            )


# ---------------------------------------------------------------------------
# Aggregator-specific assertion helper
# ---------------------------------------------------------------------------


def assert_golden_aggregation_match(
    output: Any,  # AggregatedPatternOutput
    expectation: dict[str, Any],
) -> None:
    """Handle aggregator-level output assertions."""
    if "pattern_primary" in expectation:
        assert output.pattern_primary == expectation["pattern_primary"], (
            f"pattern_primary: expected {expectation['pattern_primary']!r}, "
            f"got {output.pattern_primary!r}"
        )

    if "pattern_primary_is_none" in expectation and expectation["pattern_primary_is_none"]:
        assert output.pattern_primary is None, (
            f"pattern_primary: expected None, got {output.pattern_primary!r}"
        )

    if "pattern_confidence" in expectation:
        lo, hi = expectation["pattern_confidence"]
        val = output.pattern_confidence
        if val is None:
            assert lo <= 0 and hi >= 0, (
                f"pattern_confidence is None, expected [{lo}, {hi}]"
            )
        else:
            assert lo <= val <= hi, (
                f"pattern_confidence: expected [{lo}, {hi}], got {val}"
            )

    if "candidate_count" in expectation:
        actual = len(output.candidates)
        assert actual == expectation["candidate_count"], (
            f"candidate_count: expected {expectation['candidate_count']}, got {actual}"
        )
    if "candidate_count_min" in expectation:
        actual = len(output.candidates)
        assert actual >= expectation["candidate_count_min"], (
            f"candidate_count: expected >= {expectation['candidate_count_min']}, "
            f"got {actual}"
        )

    if "passed_checks_superset" in expectation:
        passed = set(output.passed_checks)
        for check in expectation["passed_checks_superset"]:
            assert check in passed, (
                f"passed_checks missing {check!r}; have: {sorted(passed)}"
            )

    if "failed_checks_contains" in expectation:
        failed = set(output.failed_checks)
        for check in expectation["failed_checks_contains"]:
            assert check in failed, (
                f"failed_checks missing {check!r}; have: {sorted(failed)}"
            )

    if "detector_trace_count" in expectation:
        actual = len(output.detector_traces)
        assert actual == expectation["detector_trace_count"], (
            f"detector_trace_count: expected {expectation['detector_trace_count']}, "
            f"got {actual}"
        )


# ---------------------------------------------------------------------------
# Golden snapshot export
# ---------------------------------------------------------------------------


def _serialize_result(result: PatternDetectorResult) -> dict[str, Any]:
    """Convert detector result to JSON-serializable dict."""
    return {
        "outcome": result.outcome.value,
        "detector_name": result.detector_name,
        "candidate_count": len(result.candidates),
        "passed_checks": list(result.passed_checks),
        "failed_checks": list(result.failed_checks),
        "warnings": list(result.warnings),
        "candidates": [dict(c) for c in result.candidates],
    }


def _serialize_aggregation(output: Any) -> dict[str, Any]:
    """Convert aggregator output to JSON-serializable dict."""
    return {
        "pattern_primary": output.pattern_primary,
        "pattern_confidence": output.pattern_confidence,
        "pivot_price": output.pivot_price,
        "pivot_type": output.pivot_type,
        "candidate_count": len(output.candidates),
        "candidates": [dict(c) for c in output.candidates],
        "passed_checks": list(output.passed_checks),
        "failed_checks": list(output.failed_checks),
        "detector_trace_count": len(output.detector_traces),
        "detector_traces": [
            {
                "detector_name": t.detector_name,
                "outcome": t.outcome,
                "candidate_count": t.candidate_count,
            }
            for t in output.detector_traces
        ],
    }


def maybe_export_snapshot(
    case_id: str,
    result: Any,
    golden_update: bool,
    *,
    is_aggregation: bool = False,
) -> None:
    """If --golden-update, write snapshot and skip the test."""
    if not golden_update:
        return

    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOTS_DIR / f"{case_id}.json"

    payload = (
        _serialize_aggregation(result) if is_aggregation else _serialize_result(result)
    )

    path.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    pytest.skip(f"Golden snapshot '{case_id}' written to {path}")
