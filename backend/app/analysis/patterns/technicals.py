"""Shared technical utilities for Setup Engine pattern math.

All helpers are pure, deterministic, and assume chronological input
(oldest row first, newest row last).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal


def _require_datetime_index(df: pd.DataFrame) -> None:
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("DataFrame index must be a DatetimeIndex")


def _resolve_column(df: pd.DataFrame, preferred: str, fallback: str) -> str:
    if preferred in df.columns:
        return preferred
    if fallback in df.columns:
        return fallback
    raise KeyError(f"Missing required column '{preferred}'/'{fallback}'")


def resample_ohlcv(
    df: pd.DataFrame,
    *,
    rule: str = "W-FRI",
    exclude_incomplete_last_period: bool = False,
    exchange: str = "NYSE",
    open_col: str = "Open",
    high_col: str = "High",
    low_col: str = "Low",
    close_col: str = "Close",
    volume_col: str = "Volume",
) -> pd.DataFrame:
    """Resample OHLCV bars using first/max/min/last/sum aggregation."""
    _require_datetime_index(df)
    ordered = df.sort_index()

    o = _resolve_column(ordered, open_col, open_col.lower())
    h = _resolve_column(ordered, high_col, high_col.lower())
    l = _resolve_column(ordered, low_col, low_col.lower())
    c = _resolve_column(ordered, close_col, close_col.lower())
    v = _resolve_column(ordered, volume_col, volume_col.lower())

    out = (
        ordered[[o, h, l, c, v]]
        .resample(rule)
        .agg({
            o: "first",
            h: "max",
            l: "min",
            c: "last",
            v: "sum",
        })
        .dropna(subset=[c])
    )
    if exclude_incomplete_last_period and has_incomplete_last_period(
        ordered.index,
        rule=rule,
        exchange=exchange,
    ):
        out = out.iloc[:-1]
    return out


def has_incomplete_last_period(
    index: pd.DatetimeIndex,
    *,
    rule: str,
    exchange: str = "NYSE",
) -> bool:
    """Return True when latest bar is before the last scheduled session in period."""
    if not isinstance(index, pd.DatetimeIndex):
        raise ValueError("index must be a DatetimeIndex")
    if len(index) == 0:
        return False

    normalized_index = _to_utc_naive(index)
    last_ts = normalized_index.max()

    # Exchange-aware path for weekly bars prevents false "incomplete" flags on
    # holiday-shortened weeks where Friday has no trading session.
    if str(rule).startswith("W-"):
        period = last_ts.to_period(rule)
        period_start = period.start_time.normalize()
        period_end = period.end_time.normalize()
        schedule = _get_exchange_calendar(exchange).schedule(
            start_date=period_start.date().isoformat(),
            end_date=period_end.date().isoformat(),
        )
        if not schedule.empty:
            scheduled_dates = _to_utc_naive(pd.DatetimeIndex(schedule.index))
            expected_last_session = scheduled_dates.max().normalize()
            return last_ts.normalize() < expected_last_session

        # Defensive fallback when schedule is unexpectedly empty.
        return last_ts.normalize() < period_end

    period_end = last_ts.to_period(rule).end_time
    if period_end.tzinfo is not None:
        period_end = period_end.tz_convert("UTC").tz_localize(None)
    return last_ts.normalize() < period_end.normalize()


@lru_cache(maxsize=4)
def _get_exchange_calendar(exchange: str):
    exchange_name = str(exchange).upper()
    try:
        return mcal.get_calendar(exchange_name)
    except Exception as exc:  # pragma: no cover - defensive bad input path
        raise ValueError(f"Unsupported exchange calendar: {exchange}") from exc


def _to_utc_naive(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    if index.tz is None:
        return index
    return index.tz_convert("UTC").tz_localize(None)


def true_range(
    high: pd.Series,
    low: pd.Series,
    previous_close: pd.Series,
) -> pd.Series:
    """Compute True Range from high/low and previous close."""
    ranges = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    )
    return ranges.max(axis=1)


def true_range_from_ohlc(
    df: pd.DataFrame,
    *,
    high_col: str = "High",
    low_col: str = "Low",
    close_col: str = "Close",
) -> pd.Series:
    """Compute True Range from an OHLC dataframe."""
    h = _resolve_column(df, high_col, high_col.lower())
    l = _resolve_column(df, low_col, low_col.lower())
    c = _resolve_column(df, close_col, close_col.lower())

    prev_close = df[c].shift(1)
    return true_range(df[h], df[l], prev_close)


def true_range_percent(
    df: pd.DataFrame,
    *,
    high_col: str = "High",
    low_col: str = "Low",
    close_col: str = "Close",
) -> pd.Series:
    """Compute true range as percentage of previous close."""
    tr = true_range_from_ohlc(
        df,
        high_col=high_col,
        low_col=low_col,
        close_col=close_col,
    )
    c = _resolve_column(df, close_col, close_col.lower())
    prev_close = df[c].shift(1).replace(0, np.nan)
    return (tr / prev_close.abs()) * 100.0


def average_true_range(
    df: pd.DataFrame,
    *,
    period: int = 14,
    method: Literal["wilder", "sma"] = "wilder",
    high_col: str = "High",
    low_col: str = "Low",
    close_col: str = "Close",
) -> pd.Series:
    """Compute ATR using Wilder EMA or simple moving average."""
    if period < 1:
        raise ValueError("period must be >= 1")

    tr = true_range_from_ohlc(
        df,
        high_col=high_col,
        low_col=low_col,
        close_col=close_col,
    )
    if method == "wilder":
        return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    if method == "sma":
        return tr.rolling(window=period, min_periods=period).mean()
    raise ValueError("method must be 'wilder' or 'sma'")


def bollinger_bands(
    close: pd.Series,
    *,
    window: int = 20,
    stddev: float = 2.0,
) -> pd.DataFrame:
    """Return Bollinger bands (middle/upper/lower)."""
    if window < 2:
        raise ValueError("window must be >= 2")
    if stddev <= 0:
        raise ValueError("stddev must be > 0")

    middle = close.rolling(window=window, min_periods=window).mean()
    sigma = close.rolling(window=window, min_periods=window).std(ddof=0)
    upper = middle + stddev * sigma
    lower = middle - stddev * sigma

    return pd.DataFrame(
        {
            "middle": middle,
            "upper": upper,
            "lower": lower,
        },
        index=close.index,
    )


def bollinger_band_width_percent(
    close: pd.Series,
    *,
    window: int = 20,
    stddev: float = 2.0,
) -> pd.Series:
    """Compute Bollinger band width as percent of middle band."""
    bands = bollinger_bands(close, window=window, stddev=stddev)
    middle = bands["middle"].replace(0, np.nan)
    return ((bands["upper"] - bands["lower"]) / middle.abs()) * 100.0


def rolling_linear_regression(
    series: pd.Series,
    *,
    window: int,
) -> pd.DataFrame:
    """Vectorized rolling OLS regression over equally spaced x=[0..window-1]."""
    if window < 2:
        raise ValueError("window must be >= 2")

    values = series.to_numpy(dtype=float)
    n = len(values)
    slopes = np.full(n, np.nan)
    intercepts = np.full(n, np.nan)
    r2_values = np.full(n, np.nan)
    if n < window:
        return pd.DataFrame(
            {"slope": slopes, "intercept": intercepts, "r2": r2_values},
            index=series.index,
        )

    windows = np.lib.stride_tricks.sliding_window_view(values, window)
    nan_mask = np.isnan(windows).any(axis=1)
    valid_idx = np.where(~nan_mask)[0]

    if valid_idx.size > 0:
        w = windows[valid_idx]
        x = np.arange(window, dtype=float)
        x_mean = x.mean()
        x_centered = x - x_mean
        denom = np.sum(x_centered * x_centered)

        y_mean = w.mean(axis=1, keepdims=True)
        y_centered = w - y_mean

        slopes_valid = np.sum(y_centered * x_centered, axis=1) / denom
        intercepts_valid = y_mean[:, 0] - slopes_valid * x_mean

        y_hat = intercepts_valid[:, None] + slopes_valid[:, None] * x[None, :]
        ss_res = np.sum((w - y_hat) ** 2, axis=1)
        ss_tot = np.sum((w - y_mean) ** 2, axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            r2_valid = 1.0 - (ss_res / ss_tot)
            r2_valid = np.where(ss_tot == 0, np.nan, r2_valid)

        out_idx = valid_idx + window - 1
        slopes[out_idx] = slopes_valid
        intercepts[out_idx] = intercepts_valid
        r2_values[out_idx] = r2_valid

    return pd.DataFrame(
        {"slope": slopes, "intercept": intercepts, "r2": r2_values},
        index=series.index,
    )


def rolling_slope(series: pd.Series, *, window: int) -> pd.Series:
    """Convenience wrapper: rolling regression slope only."""
    return rolling_linear_regression(series, window=window)["slope"]


def rolling_percentile_rank(series: pd.Series, *, window: int) -> pd.Series:
    """Percentile rank of the latest value within each rolling window (0..100)."""
    if window < 1:
        raise ValueError("window must be >= 1")

    values = series.to_numpy(dtype=float)
    out = np.full(len(values), np.nan)
    if len(values) < window:
        return pd.Series(out, index=series.index, name=series.name)

    windows = np.lib.stride_tricks.sliding_window_view(values, window)
    nan_mask = np.isnan(windows).any(axis=1)
    valid_idx = np.where(~nan_mask)[0]

    if valid_idx.size > 0:
        valid_windows = windows[valid_idx]
        latest = valid_windows[:, -1][:, None]
        rank_pct = (valid_windows <= latest).sum(axis=1) / float(window) * 100.0
        out[valid_idx + window - 1] = rank_pct

    return pd.Series(out, index=series.index, name=series.name)


def detect_swings(
    highs: pd.Series,
    lows: pd.Series,
    *,
    left: int = 2,
    right: int = 2,
) -> pd.DataFrame:
    """Detect strict local swing highs/lows using centered windows."""
    if left < 1 or right < 1:
        raise ValueError("left and right must be >= 1")
    if len(highs) != len(lows):
        raise ValueError("highs and lows must have identical length")

    n = len(highs)
    swing_high = np.zeros(n, dtype=bool)
    swing_low = np.zeros(n, dtype=bool)

    window = left + right + 1
    if n >= window:
        high_windows = np.lib.stride_tricks.sliding_window_view(
            highs.to_numpy(dtype=float),
            window,
        )
        low_windows = np.lib.stride_tricks.sliding_window_view(
            lows.to_numpy(dtype=float),
            window,
        )

        center_high = high_windows[:, left]
        center_low = low_windows[:, left]

        left_high = high_windows[:, :left].max(axis=1)
        right_high = high_windows[:, left + 1 :].max(axis=1)
        left_low = low_windows[:, :left].min(axis=1)
        right_low = low_windows[:, left + 1 :].min(axis=1)

        is_high = (center_high > left_high) & (center_high > right_high)
        is_low = (center_low < left_low) & (center_low < right_low)

        idx = np.arange(left, n - right)
        swing_high[idx] = is_high
        swing_low[idx] = is_low

    return pd.DataFrame(
        {
            "swing_high": swing_high,
            "swing_low": swing_low,
        },
        index=highs.index,
    )
