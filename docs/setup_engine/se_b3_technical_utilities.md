# SE-B3 Shared Technical Utilities

## Module
- `backend/app/analysis/patterns/technicals.py`

## Provided Helpers
- Resampling:
  - `resample_ohlcv(...)` (`W-FRI` compatible OHLCV aggregation)
- Volatility / range:
  - `true_range(...)`
  - `true_range_from_ohlc(...)`
  - `true_range_percent(...)`
  - `average_true_range(...)`
- Bollinger helpers:
  - `bollinger_bands(...)`
  - `bollinger_band_width_percent(...)`
- Trend/regression:
  - `rolling_linear_regression(...)`
  - `rolling_slope(...)`
- Ranking and pivots:
  - `rolling_percentile_rank(...)`
  - `detect_swings(...)`

## Design Properties
- Pure functions with explicit validation.
- Chronological data orientation (oldest -> newest).
- Vectorized numpy/pandas operations (`sliding_window_view` for rolling math).

## Test Coverage
- `backend/tests/unit/test_pattern_technical_utils.py`
