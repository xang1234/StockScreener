"""
Weinstein Stage Analysis implementation.

Identifies which of the 4 market stages a stock is in:
- Stage 1: Basing (sideways/consolidating around FLATTENING 200-day MA, after prior decline)
- Stage 2: Advancing (uptrend, above RISING 200-day MA, higher highs and higher lows) - IDEAL
- Stage 3: Topping (choppy/erratic action, MA flattening/curving down after prior uptrend)
- Stage 4: Declining (downtrend, below FALLING 200-day MA, lower highs and lower lows)
"""
import pandas as pd
import numpy as np
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class WeinsteinstageAnalyzer:
    """
    Analyze stock stage using Weinstein methodology.

    Stage 2 (Advancing) is the ideal stage for buying according to both
    Weinstein and Minervini methodologies.
    """

    def __init__(self):
        """Initialize stage analyzer."""
        pass

    def calculate_ma_trend(
        self,
        ma_values: pd.Series,
        lookback: int = 20
    ) -> str:
        """
        Determine if moving average is rising, falling, or flat.

        Args:
            ma_values: Moving average series (most recent first)
            lookback: Number of periods to analyze trend

        Returns:
            "rising", "falling", or "flat"
        """
        if len(ma_values) < lookback:
            logger.warning(f"MA trend: insufficient data, len={len(ma_values)}, need={lookback}")
            return "unknown"

        current = ma_values.iloc[0]
        past = ma_values.iloc[lookback - 1]

        logger.debug(f"MA trend calculation: current={current}, past={past}, len={len(ma_values)}")

        if pd.isna(current) or pd.isna(past):
            logger.warning(f"MA trend: NaN values detected, current is NaN={pd.isna(current)}, past is NaN={pd.isna(past)}")
            return "unknown"

        change_pct = ((current - past) / past) * 100

        # Consider flat if change is < 1%
        if abs(change_pct) < 1.0:
            return "flat"
        elif change_pct > 0:
            return "rising"
        else:
            return "falling"

    def calculate_price_trend(
        self,
        prices: pd.Series,
        lookback: int = 60
    ) -> str:
        """
        Determine overall price trend.

        Args:
            prices: Price series (most recent first)
            lookback: Number of periods (default: 60 = ~3 months)

        Returns:
            "uptrend", "downtrend", or "sideways"
        """
        if len(prices) < lookback:
            return "unknown"

        # Simple linear regression to determine trend
        recent_prices = prices.iloc[:lookback].values
        x = np.arange(len(recent_prices))

        try:
            # Fit linear trend (higher slope = uptrend)
            slope, _ = np.polyfit(x, recent_prices, 1)

            # Normalize slope by average price
            # This gives daily change as percentage of average price
            avg_price = np.mean(recent_prices)
            normalized_slope = (slope / avg_price) * 100

            # Threshold: ~0.05% per day = ~3% over 60 days (reasonable uptrend)
            if normalized_slope > 0.05:
                return "uptrend"
            elif normalized_slope < -0.05:
                return "downtrend"
            else:
                return "sideways"

        except Exception as e:
            logger.error(f"Error calculating price trend: {e}")
            return "unknown"

    def _detect_swing_pattern(
        self,
        prices: pd.Series,
        lookback: int = 60,
        swing_window: int = 5
    ) -> str:
        """
        Detect if price is making higher highs/lows or lower highs/lows.

        This is a key Weinstein criteria:
        - Stage 2: Higher highs AND higher lows
        - Stage 4: Lower highs AND lower lows

        Args:
            prices: Price series (most recent first)
            lookback: Number of periods to analyze
            swing_window: Window size for detecting local peaks/troughs

        Returns:
            "higher_highs_lows", "lower_highs_lows", or "mixed"
        """
        if len(prices) < lookback:
            return "unknown"

        # Work with the lookback period, reverse to chronological order
        price_data = prices.iloc[:lookback].values[::-1]

        # Find swing highs (local maxima)
        swing_highs = []
        swing_lows = []

        for i in range(swing_window, len(price_data) - swing_window):
            # Check if this is a local maximum
            window = price_data[i - swing_window:i + swing_window + 1]
            if price_data[i] == max(window):
                swing_highs.append((i, price_data[i]))
            # Check if this is a local minimum
            if price_data[i] == min(window):
                swing_lows.append((i, price_data[i]))

        # Need at least 2 swing points to compare
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return "unknown"

        # Compare the last few swing highs (are they ascending?)
        recent_highs = [h[1] for h in swing_highs[-3:]]
        higher_highs = all(recent_highs[i] < recent_highs[i + 1]
                          for i in range(len(recent_highs) - 1))

        # Compare the last few swing lows (are they ascending?)
        recent_lows = [l[1] for l in swing_lows[-3:]]
        higher_lows = all(recent_lows[i] < recent_lows[i + 1]
                         for i in range(len(recent_lows) - 1))

        # Compare the last few swing highs (are they descending?)
        lower_highs = all(recent_highs[i] > recent_highs[i + 1]
                          for i in range(len(recent_highs) - 1))

        # Compare the last few swing lows (are they descending?)
        lower_lows = all(recent_lows[i] > recent_lows[i + 1]
                         for i in range(len(recent_lows) - 1))

        # Classify the pattern
        if higher_highs and higher_lows:
            return "higher_highs_lows"
        elif lower_highs and lower_lows:
            return "lower_highs_lows"
        else:
            return "mixed"

    def determine_stage(
        self,
        current_price: float,
        ma_200: float,
        ma_200_series: pd.Series,
        price_series: pd.Series,
        volume_series: Optional[pd.Series] = None
    ) -> Dict:
        """
        Determine Weinstein stage for a stock.

        Args:
            current_price: Current stock price
            ma_200: Current 200-day moving average
            ma_200_series: Series of 200-day MA values over time
            price_series: Price series
            volume_series: Volume series (optional, for validation)

        Returns:
            Dict with stage number and characteristics
        """
        # Determine MA trend
        ma_trend = self.calculate_ma_trend(ma_200_series, lookback=20)

        # Determine price trend
        price_trend = self.calculate_price_trend(price_series, lookback=60)

        # Detect swing pattern (higher highs/lows vs lower highs/lows)
        swing_pattern = self._detect_swing_pattern(price_series, lookback=60)

        # Check if price is above or below MA
        above_ma = current_price > ma_200

        # Determine stage based on criteria including swing pattern
        stage = self._classify_stage(above_ma, ma_trend, price_trend, swing_pattern)

        # Calculate confidence score
        confidence = self._calculate_confidence(
            stage, above_ma, ma_trend, price_trend, swing_pattern, volume_series
        )

        return {
            "stage": stage,
            "stage_name": self._get_stage_name(stage),
            "above_ma_200": above_ma,
            "ma_200_trend": ma_trend,
            "price_trend": price_trend,
            "swing_pattern": swing_pattern,
            "confidence": confidence,
            "description": self._get_stage_description(stage),
        }

    def _classify_stage(
        self,
        above_ma: bool,
        ma_trend: str,
        price_trend: str,
        swing_pattern: str = "unknown"
    ) -> int:
        """
        Classify Weinstein stage based on price position, trends, and swing pattern.

        Key Weinstein criteria:
        - Stage 1: FLAT MA (after decline), price consolidating around MA
        - Stage 2: RISING MA, price above MA, higher highs and higher lows
        - Stage 3: MA flattening/turning down, price choppy around MA
        - Stage 4: FALLING MA, price below MA, lower highs and lower lows

        Returns:
            Stage number (1, 2, 3, or 4)
        """
        # Stage 2: Price above RISING 200-day MA with uptrend
        # Core Weinstein criteria - swing pattern used for confidence only
        if above_ma and ma_trend == "rising" and price_trend == "uptrend":
            return 2

        # Stage 4: Price below FALLING 200-day MA with downtrend
        if not above_ma and ma_trend == "falling" and price_trend == "downtrend":
            return 4

        # Stage 3: Price above MA but MA is flattening/falling (distribution)
        # Or uptrend is weakening while still above MA
        if above_ma:
            # MA no longer rising = distribution/topping
            if ma_trend in ["flat", "falling"]:
                return 3
            # MA still rising but price trend weakening = early Stage 3
            if ma_trend == "rising" and price_trend in ["sideways", "downtrend"]:
                return 3

        # Stage 1: MA is FLAT (key Weinstein criteria for basing)
        # Price consolidates around flattening MA after prior decline
        if ma_trend == "flat":
            return 1

        # Stage 1: Below MA but MA is not falling (transitioning from Stage 4)
        # MA starting to flatten = basing beginning
        if not above_ma and ma_trend in ["flat", "rising"]:
            return 1

        # Stage 1: Below MA with falling MA but mixed swing pattern
        # May be bottoming process
        if not above_ma and swing_pattern == "mixed":
            return 1

        # Default classification based on price position
        if not above_ma:
            return 4  # Below MA defaults to Stage 4 (declining)
        else:
            return 3  # Above MA but unclear defaults to Stage 3 (topping)

    def _calculate_confidence(
        self,
        stage: int,
        above_ma: bool,
        ma_trend: str,
        price_trend: str,
        swing_pattern: str = "unknown",
        volume_series: Optional[pd.Series] = None
    ) -> float:
        """
        Calculate confidence score (0-100) for stage determination.

        Higher confidence when all indicators align, including swing pattern.
        """
        confidence = 50  # Base confidence

        # Stage 2 confidence boosters
        if stage == 2:
            if above_ma:
                confidence += 12
            if ma_trend == "rising":
                confidence += 12
            if price_trend == "uptrend":
                confidence += 12

            # Swing pattern alignment is key for Stage 2
            if swing_pattern == "higher_highs_lows":
                confidence += 10  # Strong confirmation
            elif swing_pattern == "mixed":
                confidence -= 10  # Warning sign - may be topping
            elif swing_pattern == "lower_highs_lows":
                confidence -= 15  # Danger - pattern breaking down

            # Check volume if available (should be expanding in Stage 2)
            if volume_series is not None and len(volume_series) > 50:
                recent_vol = volume_series.iloc[:20].mean()
                past_vol = volume_series.iloc[20:50].mean()
                if recent_vol > past_vol * 1.1:  # 10% higher volume
                    confidence += 4

        # Stage 4 confidence boosters
        elif stage == 4:
            if not above_ma:
                confidence += 12
            if ma_trend == "falling":
                confidence += 12
            if price_trend == "downtrend":
                confidence += 12

            # Swing pattern alignment for Stage 4
            if swing_pattern == "lower_highs_lows":
                confidence += 10  # Strong confirmation
            elif swing_pattern == "mixed":
                confidence -= 5  # May be bottoming

        # Stage 1 and 3 confidence based on flatness and pattern
        elif stage == 1:
            if ma_trend == "flat":
                confidence += 15  # Key criteria for Stage 1
            if swing_pattern == "mixed":
                confidence += 5  # Expected in basing

        elif stage == 3:
            if ma_trend in ["flat", "falling"]:
                confidence += 10
            if swing_pattern == "mixed":
                confidence += 5  # Expected choppy action in topping

        return max(0, min(100, confidence))

    def _get_stage_name(self, stage: int) -> str:
        """Get descriptive name for stage."""
        names = {
            1: "Basing",
            2: "Advancing",
            3: "Topping",
            4: "Declining"
        }
        return names.get(stage, "Unknown")

    def _get_stage_description(self, stage: int) -> str:
        """Get description of stage characteristics."""
        descriptions = {
            1: "Stock is basing, trading around flattening 200-day MA. Accumulation phase - watch for Stage 2 breakout.",
            2: "Stock is in uptrend above rising 200-day MA with higher highs/lows. Ideal for buying (Weinstein/Minervini).",
            3: "Stock is topping, choppy action around flattening 200-day MA. Distribution phase - consider reducing positions.",
            4: "Stock is in downtrend below declining 200-day MA with lower highs/lows. Avoid or sell."
        }
        return descriptions.get(stage, "Unknown stage")


def quick_stage_check(
    current_price: float,
    ma_50: float,
    ma_150: float,
    ma_200: float,
    ma_200_month_ago: float
) -> int:
    """
    Quick stage determination using Weinstein/Minervini-style criteria.

    Args:
        current_price: Current stock price
        ma_50: 50-day MA
        ma_150: 150-day MA
        ma_200: Current 200-day MA
        ma_200_month_ago: 200-day MA from 1 month ago

    Returns:
        Stage number (1-4)
    """
    # Check MA alignment and trend
    above_200 = current_price > ma_200

    # Calculate MA trend (flat threshold: ~1% change over a month)
    ma_change_pct = ((ma_200 - ma_200_month_ago) / ma_200_month_ago) * 100 if ma_200_month_ago > 0 else 0
    ma_200_rising = ma_change_pct > 1.0
    ma_200_falling = ma_change_pct < -1.0
    ma_200_flat = not ma_200_rising and not ma_200_falling

    # Stage 2: Perfect Minervini alignment with rising MA
    if (current_price > ma_50 > ma_150 > ma_200 and ma_200_rising):
        return 2

    # Stage 4: Below FALLING 200-day MA (key Weinstein criteria)
    if not above_200 and ma_200_falling:
        return 4

    # Stage 1: MA is FLAT (key Weinstein criteria for basing)
    # Price can be above or below the flattening MA
    if ma_200_flat:
        return 1

    # Stage 3: Above MA but MA flattening/falling OR MAs misaligned
    if above_200 and (not ma_200_rising or ma_50 < ma_200):
        return 3

    # Stage 1: Below MA but MA is rising (transitioning from basing)
    if not above_200 and ma_200_rising:
        return 1

    # Default based on price position
    return 4 if not above_200 else 3
