"""Additional SE-G1 detector fixture coverage."""

import numpy as np
import pandas as pd

from app.analysis.patterns.config import DEFAULT_SETUP_ENGINE_PARAMETERS
from app.analysis.patterns.detectors import DetectorOutcome, PatternDetectorInput
from app.analysis.patterns.detectors.double_bottom import DoubleBottomDetector
from app.analysis.patterns.first_pullback import FirstPullbackDetector


def _ohlcv_frame(index: pd.DatetimeIndex, close: np.ndarray) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Open": close * 0.995,
            "High": close * 1.01,
            "Low": close * 0.99,
            "Close": close,
            "Volume": np.full(len(close), 1_000_000.0),
        },
        index=index,
    )


def test_double_bottom_stub_returns_not_implemented_with_sufficient_data():
    weekly_idx = pd.date_range("2024-01-05", periods=20, freq="W-FRI")
    daily_idx = pd.bdate_range("2024-01-02", periods=200)
    weekly = _ohlcv_frame(weekly_idx, np.linspace(80.0, 95.0, len(weekly_idx)))
    daily = _ohlcv_frame(daily_idx, np.linspace(70.0, 100.0, len(daily_idx)))

    result = DoubleBottomDetector().detect_safe(
        PatternDetectorInput(
            symbol="DB",
            timeframe="daily",
            daily_bars=len(daily),
            weekly_bars=len(weekly),
            features={"daily_ohlcv": daily, "weekly_ohlcv": weekly},
        ),
        DEFAULT_SETUP_ENGINE_PARAMETERS,
    )

    assert result.outcome == DetectorOutcome.NOT_IMPLEMENTED
    assert "not_implemented" in result.failed_checks


def test_double_bottom_reports_explicit_insufficient_reasons():
    result = DoubleBottomDetector().detect_safe(
        PatternDetectorInput(
            symbol="DB",
            timeframe="daily",
            daily_bars=20,
            weekly_bars=5,
            features={},
        ),
        DEFAULT_SETUP_ENGINE_PARAMETERS,
    )

    assert result.outcome == DetectorOutcome.INSUFFICIENT_DATA
    assert "daily_bars_lt_80" in result.failed_checks
    assert "weekly_bars_lt_10" in result.failed_checks


def test_first_pullback_near_miss_emits_no_ma_tests_reason():
    idx = pd.bdate_range("2025-01-02", periods=90)
    close = np.linspace(100.0, 130.0, len(idx))
    frame = _ohlcv_frame(idx, close)
    frame["ma_21"] = frame["Close"] * 0.85

    result = FirstPullbackDetector().detect_safe(
        PatternDetectorInput(
            symbol="PB",
            timeframe="daily",
            daily_bars=len(frame),
            weekly_bars=60,
            features={"daily_ohlcv": frame},
        ),
        DEFAULT_SETUP_ENGINE_PARAMETERS,
    )

    assert result.outcome == DetectorOutcome.NOT_DETECTED
    assert "no_ma_tests_detected" in result.failed_checks
