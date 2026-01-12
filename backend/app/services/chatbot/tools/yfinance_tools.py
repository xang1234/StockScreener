"""
YFinance Tools for the chatbot.
Provides access to external market data via yfinance.
"""
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from ...yfinance_service import YFinanceService

logger = logging.getLogger(__name__)


class YFinanceTools:
    """Wrapper around yfinance service for chatbot tool calls."""

    def __init__(self):
        self.service = YFinanceService()

    def get_current_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get current price and basic info for a symbol.

        Args:
            symbol: Stock ticker symbol

        Returns:
            Dict with current quote data
        """
        try:
            info = self.service.get_stock_info(symbol)
            if not info:
                return None

            return {
                "symbol": symbol.upper(),
                "name": info.get("name", ""),
                "price": info.get("current_price", 0),
                "market_cap": info.get("market_cap", 0),
                "pe_ratio": info.get("pe_ratio"),
                "sector": info.get("sector", ""),
                "industry": info.get("industry", ""),
            }
        except Exception as e:
            logger.error(f"Error getting quote for {symbol}: {e}")
            return None

    def get_fundamentals(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get fundamental metrics for a symbol.

        Args:
            symbol: Stock ticker symbol

        Returns:
            Dict with fundamental data
        """
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            info = ticker.info

            if not info:
                return None

            return {
                "symbol": symbol.upper(),
                "name": info.get("longName") or info.get("shortName", ""),
                "sector": info.get("sector", "Unknown"),
                "industry": info.get("industry", "Unknown"),
                "market_cap": info.get("marketCap", 0),
                "enterprise_value": info.get("enterpriseValue", 0),
                "pe_ratio": info.get("trailingPE"),
                "forward_pe": info.get("forwardPE"),
                "peg_ratio": info.get("pegRatio"),
                "price_to_book": info.get("priceToBook"),
                "price_to_sales": info.get("priceToSalesTrailing12Months"),
                "profit_margin": info.get("profitMargins"),
                "operating_margin": info.get("operatingMargins"),
                "return_on_equity": info.get("returnOnEquity"),
                "return_on_assets": info.get("returnOnAssets"),
                "revenue": info.get("totalRevenue", 0),
                "revenue_growth": info.get("revenueGrowth"),
                "earnings_growth": info.get("earningsGrowth"),
                "debt_to_equity": info.get("debtToEquity"),
                "current_ratio": info.get("currentRatio"),
                "book_value": info.get("bookValue"),
                "dividend_yield": info.get("dividendYield"),
                "shares_outstanding": info.get("sharesOutstanding", 0),
                "institutional_ownership": info.get("heldPercentInstitutions"),
            }
        except Exception as e:
            logger.error(f"Error getting fundamentals for {symbol}: {e}")
            return None

    def get_price_history(
        self,
        symbol: str,
        period: str = "3mo"
    ) -> Optional[Dict[str, Any]]:
        """
        Get historical price data with key statistics.

        Args:
            symbol: Stock ticker symbol
            period: Time period (1mo, 3mo, 6mo, 1y, 2y)

        Returns:
            Dict with price history and statistics
        """
        try:
            df = self.service.get_historical_data(symbol, period=period, interval="1d")
            if df is None or df.empty:
                return None

            # Calculate key statistics
            current_price = df["Close"].iloc[-1]
            high_52w = df["High"].max()
            low_52w = df["Low"].min()

            # Calculate moving averages
            ma_50 = df["Close"].rolling(window=50).mean().iloc[-1] if len(df) >= 50 else None
            ma_200 = df["Close"].rolling(window=200).mean().iloc[-1] if len(df) >= 200 else None

            # Calculate returns
            returns_1m = ((current_price / df["Close"].iloc[-22]) - 1) * 100 if len(df) >= 22 else None
            returns_3m = ((current_price / df["Close"].iloc[-66]) - 1) * 100 if len(df) >= 66 else None
            returns_6m = ((current_price / df["Close"].iloc[-132]) - 1) * 100 if len(df) >= 132 else None
            returns_ytd = ((current_price / df["Close"].iloc[0]) - 1) * 100

            return {
                "symbol": symbol.upper(),
                "current_price": float(current_price),
                "high_52w": float(high_52w),
                "low_52w": float(low_52w),
                "percent_from_high": float(((current_price - high_52w) / high_52w) * 100),
                "percent_from_low": float(((current_price - low_52w) / low_52w) * 100),
                "ma_50": float(ma_50) if ma_50 else None,
                "ma_200": float(ma_200) if ma_200 else None,
                "above_ma_50": current_price > ma_50 if ma_50 else None,
                "above_ma_200": current_price > ma_200 if ma_200 else None,
                "returns_1m": float(returns_1m) if returns_1m else None,
                "returns_3m": float(returns_3m) if returns_3m else None,
                "returns_6m": float(returns_6m) if returns_6m else None,
                "returns_ytd": float(returns_ytd),
                "avg_volume": float(df["Volume"].mean()),
                "data_points": len(df),
            }
        except Exception as e:
            logger.error(f"Error getting price history for {symbol}: {e}")
            return None

    def get_earnings(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get earnings history and estimates.

        Args:
            symbol: Stock ticker symbol

        Returns:
            Dict with earnings data
        """
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)

            # Get earnings history
            earnings = ticker.earnings_history
            if earnings is not None and not earnings.empty:
                recent_earnings = earnings.tail(4).to_dict("records")
            else:
                recent_earnings = []

            # Get earnings estimates
            estimates = ticker.earnings_dates
            if estimates is not None and not estimates.empty:
                upcoming = estimates.head(2).to_dict("records")
            else:
                upcoming = []

            return {
                "symbol": symbol.upper(),
                "recent_earnings": recent_earnings,
                "upcoming_earnings": upcoming,
                "earnings_count": len(recent_earnings),
            }
        except Exception as e:
            logger.error(f"Error getting earnings for {symbol}: {e}")
            return None

    def compare_stocks(self, symbols: List[str]) -> Optional[Dict[str, Any]]:
        """
        Compare multiple stocks on key metrics.

        Args:
            symbols: List of stock symbols to compare

        Returns:
            Dict with comparison data
        """
        try:
            comparison = []
            for symbol in symbols[:5]:  # Limit to 5 stocks
                fundamentals = self.get_fundamentals(symbol)
                price_data = self.get_price_history(symbol, period="1y")

                if fundamentals and price_data:
                    comparison.append({
                        "symbol": symbol.upper(),
                        "name": fundamentals.get("name", ""),
                        "price": price_data.get("current_price"),
                        "market_cap": fundamentals.get("market_cap"),
                        "pe_ratio": fundamentals.get("pe_ratio"),
                        "peg_ratio": fundamentals.get("peg_ratio"),
                        "revenue_growth": fundamentals.get("revenue_growth"),
                        "profit_margin": fundamentals.get("profit_margin"),
                        "returns_1m": price_data.get("returns_1m"),
                        "returns_3m": price_data.get("returns_3m"),
                        "returns_ytd": price_data.get("returns_ytd"),
                    })

            return {
                "stocks": comparison,
                "count": len(comparison),
            }
        except Exception as e:
            logger.error(f"Error comparing stocks: {e}")
            return None

    def get_tool_descriptions(self) -> List[Dict[str, Any]]:
        """Return tool descriptions for the action agent."""
        return [
            {
                "name": "yfinance_quote",
                "description": "Get current stock price and basic info from Yahoo Finance.",
                "parameters": {
                    "symbol": {"type": "string", "description": "Stock ticker symbol"},
                },
                "required": ["symbol"],
            },
            {
                "name": "yfinance_fundamentals",
                "description": "Get detailed fundamental metrics including P/E, margins, growth rates, and financial ratios.",
                "parameters": {
                    "symbol": {"type": "string", "description": "Stock ticker symbol"},
                },
                "required": ["symbol"],
            },
            {
                "name": "yfinance_history",
                "description": "Get historical price data with moving averages, returns, and key price levels.",
                "parameters": {
                    "symbol": {"type": "string", "description": "Stock ticker symbol"},
                    "period": {"type": "string", "description": "Time period: 1mo, 3mo, 6mo, 1y, 2y (default 3mo)"},
                },
                "required": ["symbol"],
            },
            {
                "name": "yfinance_earnings",
                "description": "Get recent earnings history and upcoming earnings dates.",
                "parameters": {
                    "symbol": {"type": "string", "description": "Stock ticker symbol"},
                },
                "required": ["symbol"],
            },
            {
                "name": "compare_stocks",
                "description": "Compare multiple stocks on key metrics side by side.",
                "parameters": {
                    "symbols": {"type": "array", "description": "List of stock symbols to compare (max 5)"},
                },
                "required": ["symbols"],
            },
        ]
