"""Tests for calculate_composite_score.

Verifies:
- Empty inputs return 0.0 for all composite methods
- Single-screener identity (score passes through unchanged)
- Weighted average: equal-weight and custom-weight paths
- Maximum and minimum methods
- Boundary values (all zeros, all hundreds, mixed)
"""

from __future__ import annotations

import pytest

from app.domain.scanning.models import CompositeMethod, ScreenerOutputDomain
from app.domain.scanning.scoring import calculate_composite_score


# ── Helpers ──────────────────────────────────────────────────────────


def _make_output(
    score: float, passes: bool = True, name: str = "screener"
) -> ScreenerOutputDomain:
    """Factory for a minimal ScreenerOutputDomain."""
    return ScreenerOutputDomain(
        screener_name=name,
        score=score,
        passes=passes,
        rating="Strong Buy" if passes else "Pass",
        breakdown={},
        details={},
    )


# ── Empty Inputs ─────────────────────────────────────────────────────


class TestEmptyInputs:
    """Empty screener_outputs dict returns 0.0 regardless of method."""

    @pytest.mark.parametrize("method", list(CompositeMethod))
    def test_empty_dict_returns_zero(self, method: CompositeMethod):
        assert calculate_composite_score({}, method) == 0.0


# ── Single Screener ──────────────────────────────────────────────────


class TestSingleScreener:
    """A single screener's score is the composite for any method."""

    @pytest.mark.parametrize("method", list(CompositeMethod))
    def test_single_screener_identity(self, method: CompositeMethod):
        outputs = {"alpha": _make_output(75.0)}
        assert calculate_composite_score(outputs, method) == 75.0


# ── Weighted Average ─────────────────────────────────────────────────


class TestWeightedAverage:
    """Tests for the WEIGHTED_AVERAGE composite method."""

    def test_two_screeners_equal_weights(self):
        """(80 + 60) / 2 = 70."""
        outputs = {
            "alpha": _make_output(80.0),
            "beta": _make_output(60.0),
        }
        result = calculate_composite_score(
            outputs, CompositeMethod.WEIGHTED_AVERAGE
        )
        assert result == 70.0

    def test_three_screeners_equal_weights(self):
        """(90 + 60 + 30) / 3 = 60."""
        outputs = {
            "alpha": _make_output(90.0),
            "beta": _make_output(60.0),
            "gamma": _make_output(30.0),
        }
        result = calculate_composite_score(
            outputs, CompositeMethod.WEIGHTED_AVERAGE
        )
        assert result == 60.0

    def test_custom_weights(self):
        """80×2 + 60×1 = 220 / 3 ≈ 73.33."""
        outputs = {
            "alpha": _make_output(80.0),
            "beta": _make_output(60.0),
        }
        weights = {"alpha": 2.0, "beta": 1.0}
        result = calculate_composite_score(
            outputs, CompositeMethod.WEIGHTED_AVERAGE, weights=weights
        )
        assert result == pytest.approx(73.333, abs=0.01)

    def test_missing_key_in_weights_defaults_to_one(self):
        """Weights dict only has 'alpha'; 'beta' falls back to weight=1.0."""
        outputs = {
            "alpha": _make_output(80.0),
            "beta": _make_output(60.0),
        }
        weights = {"alpha": 2.0}  # beta not specified → weight 1.0
        # (80×2 + 60×1) / (2+1) = 220/3 ≈ 73.33
        result = calculate_composite_score(
            outputs, CompositeMethod.WEIGHTED_AVERAGE, weights=weights
        )
        assert result == pytest.approx(73.333, abs=0.01)

    def test_all_weights_zero_returns_zero(self):
        """Guard: total_weight=0 → returns 0.0 instead of dividing by zero."""
        outputs = {
            "alpha": _make_output(80.0),
            "beta": _make_output(60.0),
        }
        weights = {"alpha": 0.0, "beta": 0.0}
        result = calculate_composite_score(
            outputs, CompositeMethod.WEIGHTED_AVERAGE, weights=weights
        )
        assert result == 0.0


# ── Maximum Method ───────────────────────────────────────────────────


class TestMaximumMethod:
    """Tests for the MAXIMUM composite method."""

    def test_two_screeners_returns_higher(self):
        outputs = {
            "alpha": _make_output(90.0),
            "beta": _make_output(60.0),
        }
        assert calculate_composite_score(outputs, CompositeMethod.MAXIMUM) == 90.0

    def test_three_screeners_returns_highest(self):
        outputs = {
            "alpha": _make_output(70.0),
            "beta": _make_output(95.0),
            "gamma": _make_output(80.0),
        }
        assert calculate_composite_score(outputs, CompositeMethod.MAXIMUM) == 95.0


# ── Minimum Method ───────────────────────────────────────────────────


class TestMinimumMethod:
    """Tests for the MINIMUM composite method."""

    def test_two_screeners_returns_lower(self):
        outputs = {
            "alpha": _make_output(90.0),
            "beta": _make_output(60.0),
        }
        assert calculate_composite_score(outputs, CompositeMethod.MINIMUM) == 60.0

    def test_three_screeners_returns_lowest(self):
        outputs = {
            "alpha": _make_output(70.0),
            "beta": _make_output(95.0),
            "gamma": _make_output(45.0),
        }
        assert calculate_composite_score(outputs, CompositeMethod.MINIMUM) == 45.0


# ── Boundary Values ──────────────────────────────────────────────────


class TestBoundaryValues:
    """Boundary conditions for extreme score values."""

    @pytest.mark.parametrize("method", list(CompositeMethod))
    def test_all_scores_zero(self, method: CompositeMethod):
        outputs = {
            "alpha": _make_output(0.0),
            "beta": _make_output(0.0),
        }
        assert calculate_composite_score(outputs, method) == 0.0

    @pytest.mark.parametrize("method", list(CompositeMethod))
    def test_all_scores_hundred(self, method: CompositeMethod):
        outputs = {
            "alpha": _make_output(100.0),
            "beta": _make_output(100.0),
        }
        assert calculate_composite_score(outputs, method) == 100.0

    def test_mixed_zero_and_hundred_weighted_average(self):
        """(0 + 100) / 2 = 50."""
        outputs = {
            "alpha": _make_output(0.0),
            "beta": _make_output(100.0),
        }
        result = calculate_composite_score(
            outputs, CompositeMethod.WEIGHTED_AVERAGE
        )
        assert result == 50.0

    def test_mixed_zero_and_hundred_maximum(self):
        outputs = {
            "alpha": _make_output(0.0),
            "beta": _make_output(100.0),
        }
        assert calculate_composite_score(outputs, CompositeMethod.MAXIMUM) == 100.0

    def test_mixed_zero_and_hundred_minimum(self):
        outputs = {
            "alpha": _make_output(0.0),
            "beta": _make_output(100.0),
        }
        assert calculate_composite_score(outputs, CompositeMethod.MINIMUM) == 0.0
