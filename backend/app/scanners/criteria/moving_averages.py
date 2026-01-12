"""
Moving Average analysis and relationships.

Checks for Minervini-style MA alignment and trends.
"""
import pandas as pd
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class MovingAverageAnalyzer:
    """
    Analyze moving average relationships for stocks.

    Minervini Template requires:
    - Price > 50-day > 150-day > 200-day MA (perfect alignment)
    - 200-day MA trending up for at least 1 month
    - 50-day MA above both 150-day and 200-day MA
    """

    def __init__(self):
        """Initialize MA analyzer."""
        pass

    def check_ma_alignment(
        self,
        current_price: float,
        ma_50: float,
        ma_150: float,
        ma_200: float
    ) -> Dict:
        """
        Check if MAs are in perfect Minervini alignment.

        Perfect alignment: Price > 50 > 150 > 200

        Args:
            current_price: Current stock price
            ma_50: 50-day moving average
            ma_150: 150-day moving average
            ma_200: 200-day moving average

        Returns:
            Dict with alignment status and score
        """
        # Check each condition
        conditions = {
            "price_above_50": current_price > ma_50,
            "ma_50_above_150": ma_50 > ma_150,
            "ma_150_above_200": ma_150 > ma_200,
            "price_above_200": current_price > ma_200,
            "price_above_150": current_price > ma_150,
        }

        # Count how many conditions are met
        conditions_met = sum(conditions.values())

        # Perfect alignment requires all primary conditions
        perfect_alignment = (
            conditions["price_above_50"] and
            conditions["ma_50_above_150"] and
            conditions["ma_150_above_200"]
        )

        # Calculate alignment score (0-100)
        # Perfect alignment = 100, each condition = 20 points
        score = (conditions_met / len(conditions)) * 100

        return {
            "perfect_alignment": perfect_alignment,
            "alignment_score": round(score, 2),
            "conditions_met": conditions_met,
            "total_conditions": len(conditions),
            "details": conditions,
            "status": self._get_alignment_status(perfect_alignment, conditions_met),
        }

    def check_200ma_trend(
        self,
        ma_200_current: float,
        ma_200_month_ago: float,
        min_increase_pct: float = 1.0
    ) -> Dict:
        """
        Check if 200-day MA is trending up.

        Minervini requires 200-day MA to be rising for at least 1 month.

        Args:
            ma_200_current: Current 200-day MA
            ma_200_month_ago: 200-day MA from ~20 trading days ago
            min_increase_pct: Minimum % increase to consider "rising" (default: 1%)

        Returns:
            Dict with trend status
        """
        if ma_200_month_ago == 0 or pd.isna(ma_200_month_ago):
            return {
                "trending_up": False,
                "change_pct": None,
                "status": "insufficient_data",
            }

        change_pct = ((ma_200_current - ma_200_month_ago) / ma_200_month_ago) * 100
        trending_up = change_pct >= min_increase_pct

        return {
            "trending_up": trending_up,
            "change_pct": round(change_pct, 2),
            "status": "rising" if trending_up else "flat_or_declining",
            "meets_minervini": trending_up,
        }

    def check_50ma_position(
        self,
        ma_50: float,
        ma_150: float,
        ma_200: float
    ) -> Dict:
        """
        Check if 50-day MA is above both 150 and 200-day MAs.

        This is a Minervini template requirement.

        Args:
            ma_50: 50-day MA
            ma_150: 150-day MA
            ma_200: 200-day MA

        Returns:
            Dict with position status
        """
        above_150 = ma_50 > ma_150
        above_200 = ma_50 > ma_200
        both_above = above_150 and above_200

        return {
            "above_150": above_150,
            "above_200": above_200,
            "meets_minervini": both_above,
            "status": "strong" if both_above else "weak",
        }

    def calculate_ma_separation(
        self,
        current_price: float,
        ma_50: float,
        ma_200: float
    ) -> Dict:
        """
        Calculate separation between price and MAs.

        Useful for identifying overextended or consolidating stocks.

        Args:
            current_price: Current price
            ma_50: 50-day MA
            ma_200: 200-day MA

        Returns:
            Dict with separation metrics
        """
        if ma_50 == 0 or ma_200 == 0:
            return {
                "separation_from_50": None,
                "separation_from_200": None,
                "status": "insufficient_data",
            }

        sep_from_50 = ((current_price - ma_50) / ma_50) * 100
        sep_from_200 = ((current_price - ma_200) / ma_200) * 100

        # Determine if overextended (>20% above 50-day MA is stretched)
        overextended = sep_from_50 > 20

        return {
            "separation_from_50": round(sep_from_50, 2),
            "separation_from_200": round(sep_from_200, 2),
            "overextended": overextended,
            "status": "overextended" if overextended else "normal",
        }

    def comprehensive_ma_analysis(
        self,
        current_price: float,
        ma_50: float,
        ma_150: float,
        ma_200: float,
        ma_200_month_ago: float
    ) -> Dict:
        """
        Complete MA analysis combining all checks.

        Args:
            current_price: Current stock price
            ma_50: 50-day MA
            ma_150: 150-day MA
            ma_200: 200-day MA
            ma_200_month_ago: 200-day MA from 1 month ago

        Returns:
            Comprehensive analysis results
        """
        alignment = self.check_ma_alignment(current_price, ma_50, ma_150, ma_200)
        trend_200 = self.check_200ma_trend(ma_200, ma_200_month_ago)
        ma_50_pos = self.check_50ma_position(ma_50, ma_150, ma_200)
        separation = self.calculate_ma_separation(current_price, ma_50, ma_200)

        # Overall Minervini MA score (0-100)
        score = 0
        if alignment["perfect_alignment"]:
            score += 40
        if trend_200["trending_up"]:
            score += 30
        if ma_50_pos["meets_minervini"]:
            score += 30

        # Meets all Minervini MA criteria?
        meets_all_criteria = (
            alignment["perfect_alignment"] and
            trend_200["trending_up"] and
            ma_50_pos["meets_minervini"]
        )

        return {
            "minervini_ma_score": score,
            "meets_all_criteria": meets_all_criteria,
            "alignment": alignment,
            "ma_200_trend": trend_200,
            "ma_50_position": ma_50_pos,
            "separation": separation,
        }

    def _get_alignment_status(
        self,
        perfect: bool,
        conditions_met: int
    ) -> str:
        """Get status description for alignment."""
        if perfect:
            return "perfect"
        elif conditions_met >= 4:
            return "strong"
        elif conditions_met >= 3:
            return "moderate"
        elif conditions_met >= 2:
            return "weak"
        else:
            return "poor"
