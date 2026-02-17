"""Pure data-quality check functions for feature store runs.

All functions are pure: no I/O, no side effects, fully deterministic.
Each check returns a DQResult value object that captures the verdict,
severity, actual/threshold values, and a human-readable message.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence
from statistics import mean

from .models import DQSeverity


# ---------------------------------------------------------------------------
# DQ Result Value Object
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DQResult:
    """Outcome of a single data-quality check."""

    check_name: str
    passed: bool
    severity: DQSeverity
    actual_value: float
    threshold: float  # primary threshold for simple display
    message: str  # human-readable with full context


# ---------------------------------------------------------------------------
# Individual DQ Checks
# ---------------------------------------------------------------------------


def check_row_count(
    expected: int,
    actual: int,
    threshold: float = 0.9,
    severity: DQSeverity = DQSeverity.CRITICAL,
) -> DQResult:
    """Check that *actual* row count meets the *threshold* fraction of *expected*.

    Passes if ``actual / expected >= threshold``.  When ``expected == 0``
    the check passes (nothing was expected, nothing is missing).
    """
    if expected == 0:
        ratio = 1.0
    else:
        ratio = actual / expected

    passed = ratio >= threshold
    return DQResult(
        check_name="row_count",
        passed=passed,
        severity=severity,
        actual_value=ratio,
        threshold=threshold,
        message=(
            f"Row count ratio {ratio:.2%} (actual={actual}, expected={expected}) "
            f"{'meets' if passed else 'below'} threshold {threshold:.0%}"
        ),
    )


def check_null_rate(
    column_nulls: int,
    total: int,
    max_rate: float = 0.05,
    severity: DQSeverity = DQSeverity.WARNING,
) -> DQResult:
    """Check that the null rate is within the acceptable *max_rate*.

    Passes if ``column_nulls / total <= max_rate``.  When ``total == 0``
    the check passes (no rows to be null).
    """
    if total == 0:
        rate = 0.0
    else:
        rate = column_nulls / total

    passed = rate <= max_rate
    return DQResult(
        check_name="null_rate",
        passed=passed,
        severity=severity,
        actual_value=rate,
        threshold=max_rate,
        message=(
            f"Null rate {rate:.2%} (nulls={column_nulls}, total={total}) "
            f"{'within' if passed else 'exceeds'} limit {max_rate:.0%}"
        ),
    )


def check_score_distribution(
    scores: Sequence[float],
    expected_mean_range: tuple[float, float],
    severity: DQSeverity = DQSeverity.WARNING,
) -> DQResult:
    """Check that the mean of *scores* falls within *expected_mean_range*.

    Empty *scores* always fail.  The ``threshold`` field is set to the
    midpoint of the range for simple display; the ``message`` includes
    the full range.
    """
    low, high = expected_mean_range
    midpoint = (low + high) / 2.0

    if len(scores) == 0:
        return DQResult(
            check_name="score_distribution",
            passed=False,
            severity=severity,
            actual_value=0.0,
            threshold=midpoint,
            message=(
                f"Score distribution check failed: no scores provided "
                f"(expected mean in [{low}, {high}])"
            ),
        )

    actual_mean = mean(scores)
    passed = low <= actual_mean <= high
    return DQResult(
        check_name="score_distribution",
        passed=passed,
        severity=severity,
        actual_value=actual_mean,
        threshold=midpoint,
        message=(
            f"Mean score {actual_mean:.4f} "
            f"{'within' if passed else 'outside'} "
            f"expected range [{low}, {high}]"
        ),
    )


# ---------------------------------------------------------------------------
# Aggregate publishability
# ---------------------------------------------------------------------------


def is_publishable(dq_results: Sequence[DQResult]) -> bool:
    """Return True iff all CRITICAL results passed (warnings don't block)."""
    return all(
        r.passed for r in dq_results if r.severity == DQSeverity.CRITICAL
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "DQResult",
    "check_row_count",
    "check_null_rate",
    "check_score_distribution",
    "is_publishable",
]
