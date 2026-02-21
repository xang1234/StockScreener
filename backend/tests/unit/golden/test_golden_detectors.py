"""Golden regression tests for individual Setup Engine detectors.

12 curated cases: 6 positive detections + 6 near-misses.
Each case uses carefully crafted synthetic data with inline expectations.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.analysis.patterns.config import DEFAULT_SETUP_ENGINE_PARAMETERS
from app.analysis.patterns.detectors import (
    CupWithHandleDetector,
    FirstPullbackDetector,
    HighTightFlagDetector,
    NR7InsideDayDetector,
    ThreeWeeksTightDetector,
    VCPDetector,
)

from .conftest import (
    assert_golden_match,
    golden_detector_input,
    golden_ohlcv_frame,
    maybe_export_snapshot,
)

# ---------------------------------------------------------------------------
# Parametrized positive cases (4 non-VCP detectors)
# ---------------------------------------------------------------------------

_POSITIVE_CASES: list[tuple[str, dict, dict]] = []


def _build_three_weeks_tight_strict() -> tuple[dict, dict]:
    """Case 1: strict 3WT with < 1.0% band."""
    index = pd.date_range("2023-01-06", periods=30, freq="W-FRI")
    uptrend = np.linspace(70, 95, 24)
    tight = np.array([100.0, 100.2, 99.9, 100.1, 100.0, 100.15])
    close = np.concatenate([uptrend, tight])

    frame = golden_ohlcv_frame(index=index, close=close)
    inp = golden_detector_input(symbol="GOLDEN_3WT", timeframe="weekly", weekly=frame)

    detector = ThreeWeeksTightDetector()
    fixture = {"detector": detector, "input": inp}
    expectation = {
        "outcome": "detected",
        "candidate_count_min": 1,
        "pivot_type": "tight_area_high",
        "checks_true": ["weeks_tight_min_met", "tight_mode_strict"],
        "metrics_range": {"weeks_tight": (3, 6)},
        "quality_score": (80, 100),
        "confidence": (0.80, 0.95),
        "passed_checks_superset": ["tight_run_detected"],
    }
    return fixture, expectation


def _build_high_tight_flag_classic() -> tuple[dict, dict]:
    """Case 2: classic HTF with 109% pole return."""
    index = pd.bdate_range("2023-01-02", periods=220)
    gradual = np.linspace(40, 55, 150)
    pole = np.linspace(55, 115, 30)
    flag = np.linspace(113, 110, 16)
    stabilize = np.full(24, 112.0)
    close = np.concatenate([gradual, pole, flag, stabilize])

    vol_base = np.full(150, 1_000_000.0)
    vol_pole = np.full(30, 2_000_000.0)
    vol_flag = np.full(16, 500_000.0)
    vol_stab = np.full(24, 800_000.0)
    volume = np.concatenate([vol_base, vol_pole, vol_flag, vol_stab])

    frame = golden_ohlcv_frame(index=index, close=close, volume=volume)
    inp = golden_detector_input(symbol="GOLDEN_HTF", timeframe="daily", daily=frame)

    detector = HighTightFlagDetector()
    fixture = {"detector": detector, "input": inp}
    expectation = {
        "outcome": "detected",
        "candidate_count_min": 1,
        "pivot_type": "flag_high",
        "checks_true": [
            "pole_return_threshold_met",
            "flag_depth_in_range",
            "flag_in_upper_half",
            "flag_volume_contracting",
        ],
        "passed_checks_superset": [
            "pole_candidates_found",
            "flag_candidates_validated",
        ],
    }
    return fixture, expectation


def _build_nr7_inside_day_combined() -> tuple[dict, dict]:
    """Case 3: NR7 + inside day combined trigger."""
    index = pd.bdate_range("2024-01-02", periods=50)
    close = np.linspace(100, 112, 50)

    high = close * 1.01
    low = close * 0.99
    volume = np.full(50, 1_000_000.0)

    # Day 48: mother bar with wide range
    high[48] = 113.2
    low[48] = 109.0
    # Day 49: inside day AND narrowest range in 7
    close[49] = 111.5
    high[49] = 112.0
    low[49] = 111.0
    volume[49] = 400_000.0

    frame = golden_ohlcv_frame(index=index, close=close, high=high, low=low, volume=volume)
    inp = golden_detector_input(symbol="GOLDEN_NR7", timeframe="daily", daily=frame)

    detector = NR7InsideDayDetector()
    fixture = {"detector": detector, "input": inp}
    expectation = {
        "outcome": "detected",
        "candidate_count_min": 1,
        "pivot_type_contains": "trigger_high",
        "checks_true": [
            "trigger_detected",
            "trigger_is_nr7",
            "trigger_is_inside_day",
            "trigger_is_combined",
        ],
        "quality_score": (20, 65),
        "confidence": (0.20, 0.78),
    }
    return fixture, expectation


def _build_first_pullback_with_resumption() -> tuple[dict, dict]:
    """Case 4: first pullback to 21MA with resumption trigger."""
    index = pd.bdate_range("2023-06-01", periods=100)
    close = np.empty(100)
    ma_21 = np.empty(100)

    # Days 0-59: uptrend, MA far below price (10% gap prevents false MA touches)
    close[:60] = np.linspace(80, 115, 60)
    ma_21[:60] = close[:60] * 0.90

    # Days 60-65: pullback toward MA (low within 1.5% of ma_21)
    close[60:66] = np.array([112, 110, 108.5, 108.0, 107.5, 107.2])
    ma_21[60:66] = np.array([109, 108.5, 108.0, 107.5, 107.0, 106.8])

    # Days 66-75: resumption — price bounces, MA well below (no touch)
    close[66:76] = np.array([108.5, 109.5, 110.5, 111.5, 112.5, 113.0, 113.5, 114.0, 114.5, 115.0])
    ma_21[66:76] = close[66:76] * 0.93

    # Days 76-99: continuation upward, MA stays well below
    close[76:] = np.linspace(115.5, 125, 24)
    ma_21[76:] = close[76:] * 0.93

    # Volume: moderate, with resumption volume at least 0.9x average
    volume = np.full(100, 1_000_000.0)
    volume[60:66] = 600_000.0  # Lower volume on pullback
    volume[66:76] = 1_100_000.0  # Resumption volume above average

    frame = golden_ohlcv_frame(
        index=index,
        close=close,
        volume=volume,
        extra_cols={"ma_21": ma_21},
    )
    inp = golden_detector_input(symbol="GOLDEN_FPB", timeframe="daily", daily=frame)

    detector = FirstPullbackDetector()
    fixture = {"detector": detector, "input": inp}
    expectation = {
        "outcome": "detected",
        "candidate_count": 1,
        "pivot_type": "resumption_high",
        "checks_true": [
            "ma_touch_detected",
            "ma_touch_within_band",
            "resumption_trigger_confirmed",
            "is_first_test",
        ],
    }
    return fixture, expectation


def _build_cup_with_handle_classic() -> tuple[dict, dict]:
    """Case 6: classic cup-with-handle on weekly bars."""
    index = pd.date_range("2022-06-03", periods=55, freq="W-FRI")

    close = np.concatenate([
        np.array([88, 92, 96, 99]),            # Weeks 0-3: lead-in
        np.array([103]),                         # Week 4: left lip peak
        np.array([99, 95]),                      # Weeks 5-6: drop-off
        np.linspace(92, 72, 11),                 # Weeks 7-17: descent to cup low
        np.linspace(74, 97, 11),                 # Weeks 18-28: recovery
        np.array([101]),                          # Week 29: right lip peak
        np.array([99, 98]),                       # Weeks 30-31: handle start
        np.array([97, 98]),                       # Weeks 32-33: handle body
        np.array([99, 100]),                      # Weeks 34-35: handle exit
        np.linspace(100, 102, 19),               # Weeks 36-54: continuation
    ])

    # Override highs at swing peaks to ensure detect_swings(left=2, right=2)
    high = close * 1.01
    high[4] = 106.0   # Left lip: higher than 2 bars on each side
    high[29] = 104.0   # Right lip: higher than 2 bars on each side

    # Volume: declining through cup and handle
    volume = np.empty(55)
    volume[:5] = 1_500_000
    volume[5:18] = np.linspace(1_400_000, 800_000, 13)   # Cup descent
    volume[18:29] = np.linspace(900_000, 1_000_000, 11)  # Cup ascent
    volume[29:36] = np.linspace(700_000, 500_000, 7)      # Handle: lower volume
    volume[36:] = np.linspace(600_000, 800_000, 19)        # Post-handle

    frame = golden_ohlcv_frame(index=index, close=close, high=high, volume=volume)
    inp = golden_detector_input(symbol="GOLDEN_CUP", timeframe="weekly", weekly=frame)

    detector = CupWithHandleDetector()
    fixture = {"detector": detector, "input": inp}
    expectation = {
        "outcome": "detected",
        "candidate_count_min": 1,
        "pattern": "cup_with_handle",
        "pivot_type": "handle_high",
        "checks_true": [
            "cup_duration_in_range",
            "cup_depth_in_range",
            "cup_recovery_in_range",
            "handle_depth_in_range",
            "handle_volume_contracting",
        ],
        "passed_checks_superset": [
            "cup_structure_candidates_found",
            "handle_candidates_validated",
        ],
        "quality_score": (80, 100),
        "confidence": (0.85, 0.95),
    }
    return fixture, expectation


# Build all non-VCP positive cases
_POSITIVE_CASES = [
    ("three_weeks_tight_strict", *_build_three_weeks_tight_strict()),
    ("high_tight_flag_classic", *_build_high_tight_flag_classic()),
    ("nr7_inside_day_combined", *_build_nr7_inside_day_combined()),
    ("first_pullback_with_resumption", *_build_first_pullback_with_resumption()),
    ("cup_with_handle_classic", *_build_cup_with_handle_classic()),
]


@pytest.mark.parametrize(
    "case_id, fixture, expectation",
    _POSITIVE_CASES,
    ids=[c[0] for c in _POSITIVE_CASES],
)
def test_golden_positive(case_id, fixture, expectation, golden_update):
    """Golden positive detection cases (non-VCP)."""
    detector = fixture["detector"]
    inp = fixture["input"]

    result = detector.detect_safe(inp, DEFAULT_SETUP_ENGINE_PARAMETERS)
    maybe_export_snapshot(case_id, result, golden_update)
    assert_golden_match(result, expectation)


# ---------------------------------------------------------------------------
# VCP positive case (requires monkeypatch)
# ---------------------------------------------------------------------------


def test_golden_vcp_legacy_positive(monkeypatch, golden_update):
    """Case 5: VCP detected by legacy wrapper with mocked detect_vcp."""
    index = pd.bdate_range("2023-01-02", periods=220)
    close = np.linspace(80, 130, 220)
    frame = golden_ohlcv_frame(index=index, close=close)
    inp = golden_detector_input(symbol="GOLDEN_VCP", timeframe="daily", daily=frame)

    last_close = float(close[-1])

    def mock_detect_vcp(self, prices, volumes):
        return {
            "vcp_detected": True,
            "vcp_score": 82.5,
            "num_bases": 4,
            "contracting_depth": True,
            "contraction_ratio": 0.62,
            "depth_score": 88.0,
            "contracting_volume": True,
            "volume_score": 74.0,
            "tight_near_highs": True,
            "tightness_score": 90.0,
            "atr_score": 71.0,
            "atr_contraction_ratio": 0.68,
            "pivot_info": {
                "pivot": 132.25,
                "distance_pct": 1.8,
                "ready_for_breakout": True,
            },
            "current_price": last_close,
            "distance_from_high_pct": 1.2,
        }

    from app.analysis.patterns import vcp_wrapper

    monkeypatch.setattr(vcp_wrapper.VCPDetector, "detect_vcp", mock_detect_vcp)

    detector = VCPDetector()
    result = detector.detect_safe(inp, DEFAULT_SETUP_ENGINE_PARAMETERS)
    maybe_export_snapshot("vcp_legacy_positive", result, golden_update)

    assert_golden_match(result, {
        "outcome": "detected",
        "candidate_count": 1,
        "pattern": "vcp",
        "pivot_type": "vcp_pivot",
        "checks_true": ["vcp_detected_by_legacy"],
    })
    # VCP passes through legacy score directly
    candidate = result.candidates[0]
    assert candidate["quality_score"] == 82.5, (
        f"VCP quality_score: expected 82.5 (passthrough), got {candidate['quality_score']}"
    )


# ---------------------------------------------------------------------------
# Parametrized near-miss cases (4 non-VCP detectors)
# ---------------------------------------------------------------------------

_NEGATIVE_CASES: list[tuple[str, dict, dict]] = []


def _build_three_weeks_tight_too_wide() -> tuple[dict, dict]:
    """Case 7: tight band too wide (3% > relaxed 1.5%).

    Uptrend uses steep slope (20→95) so even 3-week windows have band > 1.5%.
    The 3WT band formula is (max-min)/(2*median), so we need step/median > 3%.
    """
    index = pd.date_range("2023-01-06", periods=30, freq="W-FRI")
    uptrend = np.linspace(20, 95, 24)
    wide_tight = np.array([100, 108, 92, 107, 93, 106])
    close = np.concatenate([uptrend, wide_tight])

    frame = golden_ohlcv_frame(index=index, close=close)
    inp = golden_detector_input(symbol="GOLDEN_3WT_MISS", timeframe="weekly", weekly=frame)

    detector = ThreeWeeksTightDetector()
    fixture = {"detector": detector, "input": inp}
    expectation = {
        "outcome": "not_detected",
        "failed_checks_contains": ["tight_run_not_found"],
    }
    return fixture, expectation


def _build_high_tight_flag_weak_pole() -> tuple[dict, dict]:
    """Case 8: pole return only 80% (below 100% threshold)."""
    index = pd.bdate_range("2023-01-02", periods=220)
    base = np.linspace(50, 55, 150)
    pole = np.linspace(55, 90, 30)  # 80% return (55 -> 90 is ~63%), need 50 -> 90 = 80%
    # Adjust: start lower for exact 80% return
    base = np.linspace(40, 50, 150)
    pole = np.linspace(50, 90, 30)  # 80% return from 50
    flag = np.linspace(88, 85, 16)
    rest = np.full(24, 86.0)
    close = np.concatenate([base, pole, flag, rest])

    frame = golden_ohlcv_frame(index=index, close=close)
    inp = golden_detector_input(symbol="GOLDEN_HTF_MISS", timeframe="daily", daily=frame)

    detector = HighTightFlagDetector()
    fixture = {"detector": detector, "input": inp}
    expectation = {
        "outcome": "not_detected",
        "failed_checks_contains": ["pole_return_below_threshold"],
    }
    return fixture, expectation


def _build_nr7_inside_day_expanding_ranges() -> tuple[dict, dict]:
    """Case 9: ranges linearly expand — no NR7, no inside day."""
    index = pd.bdate_range("2024-01-02", periods=50)
    close = np.linspace(100, 112, 50)

    # Each bar wider than the last: no bar can be narrowest in 7
    widths = 0.5 + np.arange(50) * 0.1
    high = close + widths
    low = close - widths

    frame = golden_ohlcv_frame(index=index, close=close, high=high, low=low)
    inp = golden_detector_input(symbol="GOLDEN_NR7_MISS", timeframe="daily", daily=frame)

    detector = NR7InsideDayDetector()
    fixture = {"detector": detector, "input": inp}
    expectation = {
        "outcome": "not_detected",
        "failed_checks_contains": ["nr7_inside_day_trigger_not_found"],
    }
    return fixture, expectation


def _build_first_pullback_no_ma_test() -> tuple[dict, dict]:
    """Case 10: MA 15% below price — low never within 1.5% band."""
    index = pd.bdate_range("2023-06-01", periods=90)
    close = np.linspace(80, 120, 90)
    ma_21 = close * 0.85  # MA far below price

    frame = golden_ohlcv_frame(
        index=index,
        close=close,
        extra_cols={"ma_21": ma_21},
    )
    inp = golden_detector_input(symbol="GOLDEN_FPB_MISS", timeframe="daily", daily=frame)

    detector = FirstPullbackDetector()
    fixture = {"detector": detector, "input": inp}
    expectation = {
        "outcome": "not_detected",
        "failed_checks_contains": ["no_ma_tests_detected"],
    }
    return fixture, expectation


def _build_cup_with_handle_too_shallow() -> tuple[dict, dict]:
    """Case 12: cup depth only ~5% (below 8% minimum).

    No High overrides — default High=close*1.01 keeps left lip at ~104.
    Cup low close=98, Low=98*0.99=97.02. Depth=(104.03-97.02)/104.03=6.7%.
    Below the 8% _CUP_MIN_DEPTH_PCT threshold.
    """
    index = pd.date_range("2022-06-03", periods=55, freq="W-FRI")

    close = np.concatenate([
        np.array([88, 92, 96, 99]),            # Weeks 0-3: lead-in
        np.array([103]),                         # Week 4: left lip peak
        np.array([101, 100]),                    # Weeks 5-6: slight decline
        np.linspace(99, 98, 11),                 # Weeks 7-17: shallow cup (low ~98)
        np.linspace(98.5, 101, 11),              # Weeks 18-28: recovery
        np.array([102]),                          # Week 29: right lip
        np.array([101, 100.5]),                   # Weeks 30-31
        np.array([100, 100.5]),                   # Weeks 32-33
        np.array([101, 101.5]),                   # Weeks 34-35
        np.linspace(101.5, 102.5, 19),           # Weeks 36-54
    ])

    # No High overrides: default High=close*1.01 keeps depth < 8%
    frame = golden_ohlcv_frame(index=index, close=close)
    inp = golden_detector_input(symbol="GOLDEN_CUP_MISS", timeframe="weekly", weekly=frame)

    detector = CupWithHandleDetector()
    fixture = {"detector": detector, "input": inp}
    expectation = {
        "outcome": "not_detected",
        "failed_checks_contains": ["cup_structure_not_found"],
    }
    return fixture, expectation


_NEGATIVE_CASES = [
    ("three_weeks_tight_too_wide", *_build_three_weeks_tight_too_wide()),
    ("high_tight_flag_weak_pole", *_build_high_tight_flag_weak_pole()),
    ("nr7_inside_day_expanding_ranges", *_build_nr7_inside_day_expanding_ranges()),
    ("first_pullback_no_ma_test", *_build_first_pullback_no_ma_test()),
    ("cup_with_handle_too_shallow", *_build_cup_with_handle_too_shallow()),
]


@pytest.mark.parametrize(
    "case_id, fixture, expectation",
    _NEGATIVE_CASES,
    ids=[c[0] for c in _NEGATIVE_CASES],
)
def test_golden_negative(case_id, fixture, expectation, golden_update):
    """Golden near-miss cases (non-VCP)."""
    detector = fixture["detector"]
    inp = fixture["input"]

    result = detector.detect_safe(inp, DEFAULT_SETUP_ENGINE_PARAMETERS)
    maybe_export_snapshot(case_id, result, golden_update)
    assert_golden_match(result, expectation)


# ---------------------------------------------------------------------------
# VCP near-miss case (requires monkeypatch)
# ---------------------------------------------------------------------------


def test_golden_vcp_legacy_not_detected(monkeypatch, golden_update):
    """Case 11: VCP legacy returns vcp_detected=False."""
    index = pd.bdate_range("2023-01-02", periods=220)
    close = np.linspace(80, 130, 220)
    frame = golden_ohlcv_frame(index=index, close=close)
    inp = golden_detector_input(symbol="GOLDEN_VCP_MISS", timeframe="daily", daily=frame)

    def mock_detect_vcp(self, prices, volumes):
        return {
            "vcp_detected": False,
            "vcp_score": 40,
            "num_bases": 2,
            "contracting_depth": False,
            "contraction_ratio": 0.95,
            "depth_score": 35.0,
            "contracting_volume": True,
            "volume_score": 60.0,
            "tight_near_highs": False,
            "tightness_score": 30.0,
            "atr_score": 45.0,
            "atr_contraction_ratio": 0.90,
            "pivot_info": None,
            "current_price": float(close[-1]),
            "distance_from_high_pct": 8.5,
        }

    from app.analysis.patterns import vcp_wrapper

    monkeypatch.setattr(vcp_wrapper.VCPDetector, "detect_vcp", mock_detect_vcp)

    detector = VCPDetector()
    result = detector.detect_safe(inp, DEFAULT_SETUP_ENGINE_PARAMETERS)
    maybe_export_snapshot("vcp_legacy_not_detected", result, golden_update)

    assert_golden_match(result, {
        "outcome": "not_detected",
        "failed_checks_contains": ["vcp_insufficient_bases"],
    })
