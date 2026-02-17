"""Tests for feature store data-quality checks and publish readiness.

Verifies:
- DQResult construction and frozen behaviour
- check_row_count: passing, failing, boundary, zero expected, custom severity
- check_null_rate: passing, failing, zero total, boundary
- check_score_distribution: in-range, out-of-range, empty, single, message
- is_publishable: critical pass/fail, warnings-only, empty
- evaluate_publish_readiness: status gating, DQ partitioning, reason property
"""

from __future__ import annotations

import pytest

from app.domain.feature_store.models import DQSeverity, RunStatus
from app.domain.feature_store.quality import (
    DQResult,
    check_null_rate,
    check_row_count,
    check_score_distribution,
    is_publishable,
)
from app.domain.feature_store.publish_policy import evaluate_publish_readiness


# ── Helpers ──────────────────────────────────────────────────────────


def _make_dq(
    passed: bool = True,
    severity: DQSeverity = DQSeverity.CRITICAL,
    name: str = "test_check",
) -> DQResult:
    """Factory for a minimal DQResult."""
    return DQResult(
        check_name=name,
        passed=passed,
        severity=severity,
        actual_value=0.95 if passed else 0.5,
        threshold=0.9,
        message="test",
    )


# ── DQResult Tests ───────────────────────────────────────────────────


class TestDQResult:
    """DQResult construction and immutability."""

    def test_construction(self):
        r = _make_dq()
        assert r.check_name == "test_check"
        assert r.passed is True
        assert r.severity == DQSeverity.CRITICAL

    def test_frozen(self):
        r = _make_dq()
        with pytest.raises(AttributeError):
            r.passed = False  # type: ignore[misc]

    def test_severity_field(self):
        r = _make_dq(severity=DQSeverity.WARNING)
        assert r.severity == DQSeverity.WARNING


# ── check_row_count Tests ────────────────────────────────────────────


class TestCheckRowCount:
    """Row count DQ check."""

    def test_passing(self):
        result = check_row_count(expected=100, actual=95)
        assert result.passed is True
        assert result.check_name == "row_count"

    def test_failing(self):
        result = check_row_count(expected=100, actual=80)
        assert result.passed is False

    def test_exact_threshold_passes(self):
        result = check_row_count(expected=100, actual=90, threshold=0.9)
        assert result.passed is True
        assert result.actual_value == pytest.approx(0.9)

    def test_just_below_threshold_fails(self):
        result = check_row_count(expected=100, actual=89, threshold=0.9)
        assert result.passed is False
        assert result.actual_value == pytest.approx(0.89)

    def test_zero_expected_passes(self):
        result = check_row_count(expected=0, actual=0)
        assert result.passed is True

    def test_custom_severity(self):
        result = check_row_count(
            expected=100, actual=50, severity=DQSeverity.WARNING
        )
        assert result.severity == DQSeverity.WARNING

    def test_message_contains_counts(self):
        result = check_row_count(expected=100, actual=95)
        assert "actual=95" in result.message
        assert "expected=100" in result.message


# ── check_null_rate Tests ────────────────────────────────────────────


class TestCheckNullRate:
    """Null rate DQ check."""

    def test_passing(self):
        result = check_null_rate(column_nulls=2, total=100)
        assert result.passed is True
        assert result.check_name == "null_rate"

    def test_failing(self):
        result = check_null_rate(column_nulls=10, total=100)
        assert result.passed is False

    def test_zero_total_passes(self):
        result = check_null_rate(column_nulls=0, total=0)
        assert result.passed is True

    def test_exact_threshold_passes(self):
        result = check_null_rate(column_nulls=5, total=100, max_rate=0.05)
        assert result.passed is True
        assert result.actual_value == pytest.approx(0.05)

    def test_just_above_threshold_fails(self):
        result = check_null_rate(column_nulls=6, total=100, max_rate=0.05)
        assert result.passed is False

    def test_message_contains_counts(self):
        result = check_null_rate(column_nulls=3, total=100)
        assert "nulls=3" in result.message
        assert "total=100" in result.message


# ── check_score_distribution Tests ───────────────────────────────────


class TestCheckScoreDistribution:
    """Score distribution DQ check."""

    def test_in_range_mean(self):
        scores = [40.0, 50.0, 60.0]  # mean = 50
        result = check_score_distribution(scores, (30.0, 70.0))
        assert result.passed is True

    def test_out_of_range_mean(self):
        scores = [90.0, 95.0, 100.0]  # mean = 95
        result = check_score_distribution(scores, (30.0, 70.0))
        assert result.passed is False

    def test_empty_scores_fail(self):
        result = check_score_distribution([], (30.0, 70.0))
        assert result.passed is False
        assert "no scores" in result.message

    def test_single_score(self):
        result = check_score_distribution([50.0], (40.0, 60.0))
        assert result.passed is True
        assert result.actual_value == pytest.approx(50.0)

    def test_custom_severity(self):
        result = check_score_distribution(
            [50.0], (40.0, 60.0), severity=DQSeverity.CRITICAL
        )
        assert result.severity == DQSeverity.CRITICAL

    def test_message_includes_range(self):
        result = check_score_distribution([50.0], (30.0, 70.0))
        assert "[30.0, 70.0]" in result.message

    def test_threshold_is_midpoint(self):
        result = check_score_distribution([50.0], (30.0, 70.0))
        assert result.threshold == pytest.approx(50.0)

    def test_boundary_low(self):
        """Mean exactly at low bound passes."""
        result = check_score_distribution([30.0], (30.0, 70.0))
        assert result.passed is True

    def test_boundary_high(self):
        """Mean exactly at high bound passes."""
        result = check_score_distribution([70.0], (30.0, 70.0))
        assert result.passed is True


# ── is_publishable Tests ─────────────────────────────────────────────


class TestIsPublishable:
    """Aggregate publishability from DQ results."""

    def test_all_critical_pass(self):
        results = [_make_dq(passed=True), _make_dq(passed=True)]
        assert is_publishable(results) is True

    def test_one_critical_fails(self):
        results = [_make_dq(passed=True), _make_dq(passed=False)]
        assert is_publishable(results) is False

    def test_warnings_only_failures_still_publishable(self):
        results = [
            _make_dq(passed=True, severity=DQSeverity.CRITICAL),
            _make_dq(passed=False, severity=DQSeverity.WARNING),
        ]
        assert is_publishable(results) is True

    def test_empty_list_publishable(self):
        assert is_publishable([]) is True


# ── evaluate_publish_readiness Tests ─────────────────────────────────


class TestEvaluatePublishReadiness:
    """Publish readiness policy evaluation."""

    def test_completed_all_pass(self):
        dq = [_make_dq(passed=True)]
        decision = evaluate_publish_readiness(RunStatus.COMPLETED, dq)
        assert decision.allowed is True
        assert decision.blocking_checks == ()
        assert decision.reason == "All critical checks passed"

    def test_completed_critical_fail(self):
        dq = [_make_dq(passed=False, severity=DQSeverity.CRITICAL, name="row_count")]
        decision = evaluate_publish_readiness(RunStatus.COMPLETED, dq)
        assert decision.allowed is False
        assert len(decision.blocking_checks) == 1
        assert "row_count" in decision.reason

    def test_running_status_blocks(self):
        decision = evaluate_publish_readiness(RunStatus.RUNNING, [])
        assert decision.allowed is False
        assert decision.reason == "Run is not in COMPLETED status"

    def test_failed_status_blocks(self):
        decision = evaluate_publish_readiness(RunStatus.FAILED, [])
        assert decision.allowed is False
        assert decision.reason == "Run is not in COMPLETED status"

    def test_published_status_blocks(self):
        decision = evaluate_publish_readiness(RunStatus.PUBLISHED, [])
        assert decision.allowed is False
        assert decision.reason == "Run is not in COMPLETED status"

    def test_completed_only_warnings_fail(self):
        dq = [
            _make_dq(passed=True, severity=DQSeverity.CRITICAL),
            _make_dq(passed=False, severity=DQSeverity.WARNING, name="null_rate"),
        ]
        decision = evaluate_publish_readiness(RunStatus.COMPLETED, dq)
        assert decision.allowed is True
        assert len(decision.warnings) == 1
        assert decision.warnings[0].check_name == "null_rate"

    def test_blocking_and_warnings_partitioned(self):
        dq = [
            _make_dq(passed=False, severity=DQSeverity.CRITICAL, name="row_count"),
            _make_dq(passed=False, severity=DQSeverity.WARNING, name="null_rate"),
            _make_dq(passed=True, severity=DQSeverity.CRITICAL, name="other"),
        ]
        decision = evaluate_publish_readiness(RunStatus.COMPLETED, dq)
        assert decision.allowed is False
        assert len(decision.blocking_checks) == 1
        assert len(decision.warnings) == 1
        assert decision.blocking_checks[0].check_name == "row_count"
        assert decision.warnings[0].check_name == "null_rate"

    def test_publish_decision_frozen(self):
        decision = evaluate_publish_readiness(RunStatus.COMPLETED, [])
        with pytest.raises(AttributeError):
            decision.allowed = False  # type: ignore[misc]

    def test_non_completed_has_empty_checks(self):
        """Non-COMPLETED status returns empty blocking_checks (not status as DQ)."""
        decision = evaluate_publish_readiness(RunStatus.RUNNING, [_make_dq()])
        assert decision.blocking_checks == ()
        assert decision.warnings == ()
