"""Golden regression tests for the Setup Engine aggregator pipeline.

3 aggregator-level tests that exercise multi-detector competition,
structural tie-breaking, and the "no pattern" deterministic baseline.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.analysis.patterns.aggregator import SetupEngineAggregator
from app.analysis.patterns.config import DEFAULT_SETUP_ENGINE_PARAMETERS
from app.analysis.patterns.detectors import (
    NR7InsideDayDetector,
    ThreeWeeksTightDetector,
    VCPDetector,
    default_pattern_detectors,
)

from .conftest import (
    assert_golden_aggregation_match,
    golden_detector_input,
    golden_ohlcv_frame,
    maybe_export_snapshot,
)


# ---------------------------------------------------------------------------
# Case A: Structural (3WT) vs Trigger (NR7) — structural wins tie-break
# ---------------------------------------------------------------------------


def test_golden_aggregator_competing_structural_vs_trigger(golden_update):
    """3WT on weekly + NR7 on daily: structural pattern preferred."""
    # Weekly frame: triggers three_weeks_tight (reuse case 1 data)
    weekly_index = pd.date_range("2023-01-06", periods=30, freq="W-FRI")
    weekly_uptrend = np.linspace(70, 95, 24)
    weekly_tight = np.array([100.0, 100.2, 99.9, 100.1, 100.0, 100.15])
    weekly_close = np.concatenate([weekly_uptrend, weekly_tight])
    weekly_frame = golden_ohlcv_frame(index=weekly_index, close=weekly_close)

    # Daily frame: triggers NR7 inside day (reuse case 3 data)
    daily_index = pd.bdate_range("2024-01-02", periods=50)
    daily_close = np.linspace(100, 112, 50)
    daily_high = daily_close * 1.01
    daily_low = daily_close * 0.99
    daily_volume = np.full(50, 1_000_000.0)

    # Day 48: mother bar
    daily_high[48] = 113.2
    daily_low[48] = 109.0
    # Day 49: inside + NR7
    daily_close[49] = 111.5
    daily_high[49] = 112.0
    daily_low[49] = 111.0
    daily_volume[49] = 400_000.0

    daily_frame = golden_ohlcv_frame(
        index=daily_index, close=daily_close,
        high=daily_high, low=daily_low, volume=daily_volume,
    )

    inp = golden_detector_input(
        symbol="GOLDEN_AGG_A",
        timeframe="daily",
        daily=daily_frame,
        weekly=weekly_frame,
    )

    aggregator = SetupEngineAggregator(
        detectors=[ThreeWeeksTightDetector(), NR7InsideDayDetector()]
    )
    output = aggregator.aggregate(inp, parameters=DEFAULT_SETUP_ENGINE_PARAMETERS)
    maybe_export_snapshot(
        "aggregator_structural_vs_trigger", output, golden_update,
        is_aggregation=True,
    )

    assert_golden_aggregation_match(output, {
        "pattern_primary": "three_weeks_tight",
        "candidate_count_min": 2,
        "passed_checks_superset": [
            "primary_pattern_selected",
            "cross_detector_calibration_applied",
            "detector_pipeline_executed",
        ],
        "detector_trace_count": 2,
    })


# ---------------------------------------------------------------------------
# Case B: VCP vs NR7 competition — VCP wins (structural + higher rank)
# ---------------------------------------------------------------------------


def test_golden_aggregator_vcp_vs_nr7(monkeypatch, golden_update):
    """VCP (high-confidence mock) vs NR7: VCP wins on structural + rank."""
    # Daily frame that triggers NR7 at the end
    daily_index = pd.bdate_range("2024-01-02", periods=220)
    daily_close = np.linspace(80, 130, 220)
    daily_high = daily_close * 1.01
    daily_low = daily_close * 0.99
    daily_volume = np.full(220, 1_000_000.0)

    # Set up NR7+inside day at the end
    daily_high[218] = daily_close[218] + 5.0  # Mother bar wide range
    daily_low[218] = daily_close[218] - 5.0
    daily_close[219] = daily_close[218]
    daily_high[219] = daily_close[219] + 0.3   # Very narrow range, inside previous
    daily_low[219] = daily_close[219] - 0.3
    daily_volume[219] = 400_000.0

    daily_frame = golden_ohlcv_frame(
        index=daily_index, close=daily_close,
        high=daily_high, low=daily_low, volume=daily_volume,
    )

    inp = golden_detector_input(
        symbol="GOLDEN_AGG_B",
        timeframe="daily",
        daily=daily_frame,
    )

    # Mock VCP legacy detector
    last_close = float(daily_close[-1])

    def mock_detect_vcp(self, prices, volumes):
        return {
            "vcp_detected": True,
            "vcp_score": 95.0,
            "num_bases": 4,
            "contracting_depth": True,
            "contraction_ratio": 0.55,
            "depth_score": 95.0,
            "contracting_volume": True,
            "volume_score": 90.0,
            "tight_near_highs": True,
            "tightness_score": 95.0,
            "atr_score": 85.0,
            "atr_contraction_ratio": 0.55,
            "pivot_info": {
                "pivot": last_close * 1.02,
                "distance_pct": 2.0,
                "ready_for_breakout": True,
            },
            "current_price": last_close,
            "distance_from_high_pct": 1.5,
        }

    from app.analysis.patterns import vcp_wrapper

    monkeypatch.setattr(vcp_wrapper.VCPDetector, "detect_vcp", mock_detect_vcp)

    aggregator = SetupEngineAggregator(
        detectors=[VCPDetector(), NR7InsideDayDetector()]
    )
    output = aggregator.aggregate(inp, parameters=DEFAULT_SETUP_ENGINE_PARAMETERS)
    maybe_export_snapshot(
        "aggregator_vcp_vs_nr7", output, golden_update,
        is_aggregation=True,
    )

    assert_golden_aggregation_match(output, {
        "pattern_primary": "vcp",
        "candidate_count_min": 2,
    })


# ---------------------------------------------------------------------------
# Case C: Deterministic linear data — no patterns detected
# ---------------------------------------------------------------------------


def test_golden_aggregator_no_patterns_linear(golden_update):
    """Exponential growth data with all 7 detectors: no patterns detected.

    Exponential (compound) growth ensures constant percentage changes at all
    price levels, avoiding pitfalls of linear data:
    - 0.6%/day → 27% max 40-bar return (under HTF's 100% pole threshold)
    - ~3% weekly band (above 3WT's 1.5% relaxed threshold)
    - MA21 lags ~5.6% behind price (Low never within 1.5% MA touch band)
    - Monotonic increasing ranges → no NR7, no inside days
    - No swing highs → no cup structure
    """
    daily_growth = 1.006  # 0.6% daily compound growth

    # Daily: 250 bars of exponential growth
    daily_index = pd.bdate_range("2023-01-02", periods=250)
    daily_close = 100.0 * (daily_growth ** np.arange(250))
    daily_high = daily_close * 1.02
    daily_low = daily_close * 0.98
    daily_volume = np.full(250, 1_000_000.0)

    daily_frame = golden_ohlcv_frame(
        index=daily_index, close=daily_close,
        high=daily_high, low=daily_low, volume=daily_volume,
    )

    # Weekly: exponential at 5-day compounding intervals
    weekly_index = pd.date_range("2023-01-06", periods=52, freq="W-FRI")
    weekly_close = 100.0 * (daily_growth ** (np.arange(52) * 5))
    weekly_high = weekly_close * 1.02
    weekly_low = weekly_close * 0.98
    weekly_volume = np.full(52, 5_000_000.0)

    weekly_frame = golden_ohlcv_frame(
        index=weekly_index, close=weekly_close,
        high=weekly_high, low=weekly_low, volume=weekly_volume,
    )

    inp = golden_detector_input(
        symbol="GOLDEN_AGG_C",
        timeframe="daily",
        daily=daily_frame,
        weekly=weekly_frame,
    )

    aggregator = SetupEngineAggregator(detectors=list(default_pattern_detectors()))
    output = aggregator.aggregate(inp, parameters=DEFAULT_SETUP_ENGINE_PARAMETERS)
    maybe_export_snapshot(
        "aggregator_no_patterns_linear", output, golden_update,
        is_aggregation=True,
    )

    assert_golden_aggregation_match(output, {
        "pattern_primary_is_none": True,
        "failed_checks_contains": ["no_primary_pattern"],
    })
