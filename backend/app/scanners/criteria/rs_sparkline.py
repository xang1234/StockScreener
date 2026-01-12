"""
RS Sparkline Calculator.

Calculates the RS ratio (stock_price / SPY_price) for the last 30 trading days
for sparkline visualization in the bulk screener results.
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class RSSparklineCalculator:
    """
    Calculate RS ratio series for sparkline visualization.

    Replicates Google Sheets formula:
    =SPARKLINE(QUERY(HSTACK(
      GOOGLEFINANCE(stock,"price",WORKDAY(TODAY(),-30),TODAY()),
      GOOGLEFINANCE(SPY,"price",WORKDAY(TODAY(),-30),TODAY())
    ),"SELECT Col2/Col4"))

    This gets stock and SPY prices for last 30 trading days,
    divides stock by SPY to get RS ratio.
    """

    SPARKLINE_DAYS = 30  # Number of trading days for sparkline

    def calculate_rs_sparkline(
        self,
        stock_prices: pd.Series,
        spy_prices: pd.Series,
        normalize: bool = True
    ) -> Dict:
        """
        Calculate RS ratio series for the last 30 trading days.

        Args:
            stock_prices: Stock closing prices (chronological order, oldest first)
            spy_prices: SPY closing prices (chronological order, oldest first)
            normalize: If True, normalize to start at 1.0 for better visual comparison

        Returns:
            Dict with:
            - rs_data: List of 30 RS ratio values (or None if insufficient data)
            - rs_trend: -1 (declining), 0 (flat), 1 (improving)
        """
        if len(stock_prices) < self.SPARKLINE_DAYS or len(spy_prices) < self.SPARKLINE_DAYS:
            logger.debug(
                f"Insufficient data for RS sparkline: stock={len(stock_prices)}, spy={len(spy_prices)}"
            )
            return {
                "rs_data": None,
                "rs_trend": 0,
            }

        try:
            # Get last 30 trading days (most recent data)
            stock_last_30 = stock_prices.iloc[-self.SPARKLINE_DAYS:].values
            spy_last_30 = spy_prices.iloc[-self.SPARKLINE_DAYS:].values

            # Calculate RS ratio (stock / SPY)
            rs_ratio = stock_last_30 / spy_last_30

            # Handle any NaN or inf values
            rs_ratio = np.nan_to_num(rs_ratio, nan=1.0, posinf=1.0, neginf=1.0)

            # Normalize to start at 1.0 if requested (better for visual comparison)
            if normalize and rs_ratio[0] != 0:
                rs_ratio = rs_ratio / rs_ratio[0]

            # Calculate trend using linear regression slope
            x = np.arange(len(rs_ratio))
            slope, _ = np.polyfit(x, rs_ratio, 1)

            # Determine trend direction
            # Threshold: slope must be significant relative to the data range
            data_range = np.max(rs_ratio) - np.min(rs_ratio)
            slope_threshold = data_range * 0.01 if data_range > 0 else 0.0001

            if slope > slope_threshold:
                trend = 1  # Improving
            elif slope < -slope_threshold:
                trend = -1  # Declining
            else:
                trend = 0  # Flat

            # Round values for JSON storage efficiency (4 decimal places)
            rs_data = [round(float(v), 4) for v in rs_ratio]

            return {
                "rs_data": rs_data,
                "rs_trend": trend,
            }

        except Exception as e:
            logger.warning(f"Error calculating RS sparkline: {e}")
            return {
                "rs_data": None,
                "rs_trend": 0,
            }
