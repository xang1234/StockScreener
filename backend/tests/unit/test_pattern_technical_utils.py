"""Tests for shared technical utilities used by pattern detectors."""

import numpy as np
import pandas as pd
import pytest

from app.analysis.patterns.technicals import (
    average_true_range,
    bollinger_band_width_percent,
    detect_swings,
    resample_ohlcv,
    rolling_linear_regression,
    rolling_percentile_rank,
    true_range_percent,
)


def _sample_ohlcv() -> pd.DataFrame:
    dates = pd.bdate_range("2026-01-05", periods=10)
    return pd.DataFrame(
        {
            "Open": [10, 11, 12, 11, 12, 13, 14, 15, 15, 16],
            "High": [11, 12, 13, 12, 13, 14, 15, 16, 16, 17],
            "Low": [9, 10, 11, 10, 11, 12, 13, 14, 14, 15],
            "Close": [10.5, 11.5, 12.5, 11.2, 12.8, 13.6, 14.4, 15.2, 15.1, 16.3],
            "Volume": [100, 120, 130, 110, 140, 150, 160, 170, 165, 180],
        },
        index=dates,
    )


def test_resample_ohlcv_weekly_aggregates_correctly():
    weekly = resample_ohlcv(_sample_ohlcv(), rule="W-FRI")

    assert len(weekly) == 2
    assert weekly.iloc[0]["Open"] == 10
    assert weekly.iloc[0]["High"] == 13
    assert weekly.iloc[0]["Low"] == 9
    assert weekly.iloc[0]["Close"] == pytest.approx(12.8)
    assert weekly.iloc[0]["Volume"] == 600


def test_true_range_percent_returns_expected_series():
    tr_pct = true_range_percent(_sample_ohlcv())
    assert tr_pct.iloc[0] != tr_pct.iloc[0]  # NaN for first row (no prev close)
    assert tr_pct.iloc[-1] > 0


def test_average_true_range_sma_and_wilder():
    df = _sample_ohlcv()
    atr_sma = average_true_range(df, period=3, method="sma")
    atr_wilder = average_true_range(df, period=3, method="wilder")

    assert atr_sma.notna().sum() >= 7
    assert atr_wilder.notna().sum() >= 7


def test_bollinger_width_zero_on_flat_series():
    s = pd.Series([10.0] * 30, index=pd.bdate_range("2026-01-01", periods=30))
    width = bollinger_band_width_percent(s, window=20)
    assert width.dropna().eq(0.0).all()


def test_rolling_linear_regression_slope_for_linear_series():
    s = pd.Series(np.arange(30, dtype=float) * 2.0 + 5.0)
    reg = rolling_linear_regression(s, window=10)
    slope = reg["slope"].dropna()

    assert len(slope) == 21
    assert np.allclose(slope.values, 2.0)


def test_rolling_percentile_rank_for_strictly_increasing_series():
    s = pd.Series([1, 2, 3, 4, 5, 6], dtype=float)
    ranks = rolling_percentile_rank(s, window=3)
    assert np.allclose(ranks.dropna().values, np.array([100.0, 100.0, 100.0, 100.0]))


def test_detect_swings_identifies_local_extrema():
    highs = pd.Series([1, 3, 2, 4, 1], dtype=float)
    lows = pd.Series([1, 2, 1, 3, 0], dtype=float)

    swings = detect_swings(highs, lows, left=1, right=1)
    high_idx = swings.index[swings["swing_high"]].tolist()
    low_idx = swings.index[swings["swing_low"]].tolist()

    assert high_idx == [1, 3]
    assert low_idx == [2]
