"""Temporal integrity tests to prevent forward-looking feature leakage."""

import numpy as np
import pandas as pd

from app.analysis.patterns.technicals import (
    has_incomplete_last_period,
    resample_ohlcv,
    rolling_linear_regression,
    rolling_percentile_rank,
)


def _sample_series(length: int = 40) -> pd.Series:
    idx = pd.bdate_range("2025-01-02", periods=length)
    return pd.Series(np.linspace(100.0, 140.0, length), index=idx)


def _sample_ohlcv_daily(length: int = 30) -> pd.DataFrame:
    idx = pd.bdate_range("2025-01-06", periods=length)
    close = np.linspace(50.0, 65.0, length)
    return pd.DataFrame(
        {
            "Open": close * 0.995,
            "High": close * 1.01,
            "Low": close * 0.99,
            "Close": close,
            "Volume": np.full(length, 1_000_000.0),
        },
        index=idx,
    )


def test_rolling_percentile_rank_is_prefix_stable_against_future_changes():
    series = _sample_series()
    t = 24
    baseline = rolling_percentile_rank(series, window=10)

    shifted = series.copy()
    shifted.iloc[t + 1 :] = shifted.iloc[t + 1 :] * 10.0
    recomputed = rolling_percentile_rank(shifted, window=10)

    assert np.allclose(
        baseline.iloc[: t + 1].to_numpy(dtype=float),
        recomputed.iloc[: t + 1].to_numpy(dtype=float),
        equal_nan=True,
    )


def test_rolling_linear_regression_is_prefix_stable_against_future_changes():
    series = _sample_series()
    t = 24
    baseline = rolling_linear_regression(series, window=12)

    shifted = series.copy()
    shifted.iloc[t + 1 :] = shifted.iloc[t + 1 :] * -3.0
    recomputed = rolling_linear_regression(shifted, window=12)

    assert np.allclose(
        baseline["slope"].iloc[: t + 1].to_numpy(dtype=float),
        recomputed["slope"].iloc[: t + 1].to_numpy(dtype=float),
        equal_nan=True,
    )


def test_weekly_resample_can_exclude_incomplete_current_week():
    daily = _sample_ohlcv_daily(length=23)
    # Trim to Wednesday so the final W-FRI period is incomplete.
    daily = daily.loc[: "2025-02-05"]
    assert has_incomplete_last_period(daily.index, rule="W-FRI") is True

    with_incomplete = resample_ohlcv(daily, rule="W-FRI")
    without_incomplete = resample_ohlcv(
        daily,
        rule="W-FRI",
        exclude_incomplete_last_period=True,
    )

    assert len(without_incomplete) + 1 == len(with_incomplete)
    assert without_incomplete.index.max() < with_incomplete.index.max()


def test_holiday_shortened_week_is_not_marked_incomplete():
    idx = pd.DatetimeIndex(
        ["2025-04-14", "2025-04-15", "2025-04-16", "2025-04-17"]
    )
    daily = _sample_ohlcv_daily(length=4).copy()
    daily.index = idx

    assert has_incomplete_last_period(idx, rule="W-FRI", exchange="NYSE") is False
    assert has_incomplete_last_period(idx, rule="W-FRI", exchange="NASDAQ") is False

    with_last = resample_ohlcv(daily, rule="W-FRI")
    without_last = resample_ohlcv(
        daily,
        rule="W-FRI",
        exclude_incomplete_last_period=True,
        exchange="NYSE",
    )
    assert len(with_last) == len(without_last)


def test_incomplete_period_check_handles_tz_aware_index():
    idx = pd.DatetimeIndex(
        ["2025-02-03 00:00:00", "2025-02-04 00:00:00", "2025-02-05 00:00:00"],
        tz="US/Eastern",
    )
    assert has_incomplete_last_period(idx, rule="W-FRI", exchange="NYSE") is True
