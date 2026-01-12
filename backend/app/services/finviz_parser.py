"""
finvizfinance Data Parser

Parses and transforms finvizfinance data into yfinance-compatible format.
"""
import logging
import re
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class FinvizParser:
    """Parser for finvizfinance data formats"""

    # Field mapping from finviz to database field names
    FUNDAMENTAL_FIELD_MAP = {
        # Valuation metrics
        'P/E': 'pe_ratio',
        'Forward P/E': 'forward_pe',
        'PEG': 'peg_ratio',
        'P/S': 'price_to_sales',
        'P/B': 'price_to_book',
        'P/C': 'price_to_cash',
        'P/FCF': 'price_to_fcf',
        'EV/EBITDA': 'ev_ebitda',
        'EV/Sales': 'ev_sales',
        'Target Price': 'target_price',

        # Profitability metrics
        'Profit Margin': 'profit_margin',
        'Oper. Margin': 'operating_margin',
        'Gross Margin': 'gross_margin',
        'ROE': 'roe',
        'ROA': 'roa',
        'ROIC': 'roic',

        # Financial health
        'Debt/Eq': 'debt_to_equity',
        'LT Debt/Eq': 'lt_debt_to_equity',
        'Current Ratio': 'current_ratio',
        'Quick Ratio': 'quick_ratio',

        # Market data
        'Market Cap': 'market_cap',
        'Shs Outstand': 'shares_outstanding',
        'Shs Float': 'shares_float',
        'Insider Own': 'insider_ownership',
        'Insider Trans': 'insider_transactions',
        'Inst Own': 'institutional_ownership',
        'Inst Trans': 'institutional_transactions',
        'Short Float': 'short_float',
        'Short Ratio': 'short_ratio',
        'Short Interest': 'short_interest',
        'Beta': 'beta',
        'Avg Volume': 'avg_volume',
        'Rel Volume': 'relative_volume',

        # Technical indicators
        'RSI (14)': 'rsi_14',
        'ATR (14)': 'atr_14',
        'SMA20': 'sma_20',
        'SMA50': 'sma_50',
        'SMA200': 'sma_200',
        'Volatility W': 'volatility_week',
        'Volatility M': 'volatility_month',

        # Performance metrics
        'Perf Week': 'perf_week',
        'Perf Month': 'perf_month',
        'Perf Quarter': 'perf_quarter',
        'Perf Half Y': 'perf_half_year',
        'Perf Year': 'perf_year',
        'Perf YTD': 'perf_ytd',

        # Growth metrics
        'EPS (ttm)': 'eps_current',
        'EPS next Y': 'eps_next_y',
        'EPS next 5Y': 'eps_next_5y',
        'EPS next Q': 'eps_next_q',
        'Sales': 'revenue_current',
        'Income': 'net_income',
        'EPS this Y': 'earnings_growth',
        'Sales past 5Y': 'sales_past_5y',

        # Dividend metrics
        'Dividend TTM': 'dividend_ttm',
        'Payout': 'payout_ratio',

        # Analyst recommendations
        'Recom': 'recommendation',

        # Company info
        'Sector': 'sector',
        'Industry': 'industry',
        'Country': 'country',
        'Employees': 'employees',
    }

    GROWTH_FIELD_MAP = {
        'EPS Q/Q': 'eps_growth_qq',
        'Sales Q/Q': 'sales_growth_qq',
        'EPS Y/Y TTM': 'eps_growth_yy',
        'Sales Y/Y TTM': 'sales_growth_yy',
    }

    @staticmethod
    def parse_percentage(value: str) -> Optional[float]:
        """
        Parse percentage string to float.

        Args:
            value: String like "91.14%" or "-2.25%"

        Returns:
            Float value (91.14 or -2.25) or None if invalid
        """
        if not value or value == '-':
            return None

        try:
            # Remove % sign and convert
            clean_value = value.strip().replace('%', '')
            return float(clean_value)
        except (ValueError, AttributeError):
            logger.debug(f"Could not parse percentage: {value}")
            return None

    @staticmethod
    def parse_number_with_suffix(value: str) -> Optional[float]:
        """
        Parse numbers with B/M/K suffixes.

        Args:
            value: String like "3949.13B", "500.5M", "10K", or "2500"

        Returns:
            Float value in base units or None if invalid
        """
        if not value or value == '-':
            return None

        try:
            value = value.strip().upper()

            # Determine multiplier
            multiplier = 1
            if value.endswith('B'):
                multiplier = 1_000_000_000
                value = value[:-1]
            elif value.endswith('M'):
                multiplier = 1_000_000
                value = value[:-1]
            elif value.endswith('K'):
                multiplier = 1_000
                value = value[:-1]

            # Remove any commas
            value = value.replace(',', '')

            # Convert to float and apply multiplier
            return float(value) * multiplier

        except (ValueError, AttributeError):
            logger.debug(f"Could not parse number: {value}")
            return None

    @staticmethod
    def parse_ratio(value: str) -> Optional[float]:
        """
        Parse simple ratio/decimal string.

        Args:
            value: String like "28.34" or "-5.12"

        Returns:
            Float value or None if invalid
        """
        if not value or value == '-':
            return None

        try:
            # Remove commas if present
            clean_value = value.strip().replace(',', '')
            return float(clean_value)
        except (ValueError, AttributeError):
            logger.debug(f"Could not parse ratio: {value}")
            return None

    @staticmethod
    def parse_multi_value(value: str, index: int = 0) -> Optional[float]:
        """
        Parse strings with multiple values separated by space.

        Args:
            value: String like "4.26% 4.98%" or "1.81% 8.71%"
            index: Which value to extract (0 or 1)

        Returns:
            Float value or None if invalid
        """
        if not value or value == '-':
            return None

        try:
            parts = value.strip().split()
            if len(parts) > index:
                return FinvizParser.parse_percentage(parts[index])
            return None
        except Exception:
            logger.debug(f"Could not parse multi-value: {value}")
            return None

    @classmethod
    def normalize_fundamentals(cls, finviz_data: Dict) -> Dict:
        """
        Convert finviz fundamental data to yfinance-compatible format.

        Args:
            finviz_data: Raw data dict from finvizfinance

        Returns:
            Normalized dict with yfinance field names and parsed values
        """
        normalized = {}

        for finviz_field, yf_field in cls.FUNDAMENTAL_FIELD_MAP.items():
            raw_value = finviz_data.get(finviz_field)

            if raw_value is None or raw_value == '-':
                continue

            # Determine parsing strategy based on field type
            parsed_value = None

            # Percentages
            if finviz_field in ['Profit Margin', 'Oper. Margin', 'Gross Margin',
                               'ROE', 'ROA', 'ROIC', 'Insider Own', 'Insider Trans',
                               'Inst Own', 'Inst Trans', 'Short Float', 'EPS this Y',
                               'EPS next Y', 'EPS next 5Y', 'Volatility W', 'Volatility M',
                               'Perf Week', 'Perf Month', 'Perf Quarter', 'Perf Half Y',
                               'Perf Year', 'Perf YTD', 'SMA20', 'SMA50', 'SMA200', 'Payout',
                               'EPS Q/Q', 'Sales Q/Q', 'EPS Y/Y TTM', 'Sales Y/Y TTM']:
                parsed_value = cls.parse_percentage(raw_value)

            # Numbers with suffixes (B/M/K)
            elif finviz_field in ['Market Cap', 'Shs Outstand', 'Shs Float',
                                 'Short Interest', 'Sales', 'Income', 'Avg Volume']:
                parsed_value = cls.parse_number_with_suffix(raw_value)

            # Multi-value fields (use second value for 5Y metrics)
            elif finviz_field in ['Sales past 5Y']:
                # "1.81% 8.71%" -> use second value (5Y)
                parsed_value = cls.parse_multi_value(raw_value, index=1)

            # Simple ratios
            else:
                parsed_value = cls.parse_ratio(raw_value)

            if parsed_value is not None:
                normalized[yf_field] = parsed_value

        # Add string fields (no parsing needed)
        for str_field in ['sector', 'industry', 'country']:
            finviz_key = str_field.capitalize() if str_field != 'industry' else 'Industry'
            if finviz_key in finviz_data:
                normalized[str_field] = finviz_data[finviz_key]

        # Parse employees if present
        if 'Employees' in finviz_data:
            normalized['employees'] = cls.parse_number_with_suffix(finviz_data['Employees'])

        # Parse 52-week high/low (format: "288.62 -9.10%")
        if '52W High' in finviz_data:
            parts = finviz_data['52W High'].split()
            if len(parts) >= 2:
                normalized['week_52_high'] = cls.parse_ratio(parts[0])
                normalized['week_52_high_distance'] = cls.parse_percentage(parts[1])

        if '52W Low' in finviz_data:
            parts = finviz_data['52W Low'].split()
            if len(parts) >= 2:
                normalized['week_52_low'] = cls.parse_ratio(parts[0])
                normalized['week_52_low_distance'] = cls.parse_percentage(parts[1])

        # Parse dividend yield from "Dividend TTM" (format: "1.03 (0.39%)")
        if 'Dividend TTM' in finviz_data:
            dividend_str = finviz_data['Dividend TTM']
            if '(' in dividend_str:
                parts = dividend_str.split('(')
                # dividend_ttm is already parsed above, extract yield
                if len(parts) == 2:
                    yield_str = parts[1].replace(')', '').strip()
                    normalized['dividend_yield'] = cls.parse_percentage(yield_str)

        # Store complete raw finviz data for future use
        normalized['_raw_data'] = finviz_data

        return normalized

    @classmethod
    def normalize_quarterly_growth(cls, finviz_data: Dict) -> Dict:
        """
        Extract quarterly and yearly growth metrics from finviz data.

        Args:
            finviz_data: Raw data dict from finvizfinance

        Returns:
            Dict with growth metrics
        """
        growth_data = {}

        for finviz_field, yf_field in cls.GROWTH_FIELD_MAP.items():
            raw_value = finviz_data.get(finviz_field)

            if raw_value:
                parsed_value = cls.parse_percentage(raw_value)
                if parsed_value is not None:
                    growth_data[yf_field] = parsed_value

        # Note: finviz doesn't provide quarter dates directly
        # We'll set these to None and let the caller handle it
        growth_data['recent_quarter_date'] = None
        growth_data['previous_quarter_date'] = None

        # Store complete raw finviz data for future use
        growth_data['_raw_data'] = finviz_data

        return growth_data

    @classmethod
    def get_field_mapping_info(cls) -> Dict:
        """
        Get information about field mappings for debugging.

        Returns:
            Dict with mapping statistics
        """
        return {
            'fundamental_fields': len(cls.FUNDAMENTAL_FIELD_MAP),
            'growth_fields': len(cls.GROWTH_FIELD_MAP),
            'total_mapped_fields': len(cls.FUNDAMENTAL_FIELD_MAP) + len(cls.GROWTH_FIELD_MAP),
        }
