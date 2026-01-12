"""
Tool Executor for the chatbot.
Executes tool calls from Groq's native tool calling API.
"""
import json
import logging
from typing import Dict, Any, Optional

from sqlalchemy.orm import Session

from .tools.yfinance_tools import YFinanceTools
from .tools.database_tools import DatabaseTools
from .tools.web_search import WebSearchTool
from .tools.document_tools import DocumentTools

logger = logging.getLogger(__name__)


class ToolExecutor:
    """Executes tool calls from the LLM."""

    def __init__(self, db: Session):
        self.db = db
        self.yfinance_tools = YFinanceTools()
        self.database_tools = DatabaseTools(db)
        self.web_search = WebSearchTool()
        self.document_tools = DocumentTools(db)

        # Map tool names to executor methods
        self.tool_map = {
            # YFinance tools
            "yfinance_quote": self._exec_yfinance_quote,
            "yfinance_fundamentals": self._exec_yfinance_fundamentals,
            "yfinance_history": self._exec_yfinance_history,
            "yfinance_earnings": self._exec_yfinance_earnings,
            "compare_stocks": self._exec_compare_stocks,
            # Database tools
            "get_scan_results": self._exec_get_scan_results,
            "search_stocks": self._exec_search_stocks,
            "get_theme_data": self._exec_get_theme_data,
            "get_trending_themes": self._exec_get_trending_themes,
            "get_breadth_data": self._exec_get_breadth_data,
            "get_top_rated_stocks": self._exec_get_top_rated_stocks,
            # New database tools (internal data)
            "get_db_fundamentals": self._exec_get_db_fundamentals,
            "get_db_price_history": self._exec_get_db_price_history,
            "advanced_stock_search": self._exec_advanced_stock_search,
            # Web search tools
            "web_search": self._exec_web_search,
            "search_news": self._exec_search_news,
            "search_finance": self._exec_search_finance,
            # Document tools (SEC filings and IR PDFs)
            "get_sec_10k": self._exec_get_sec_10k,
            "read_ir_pdf": self._exec_read_ir_pdf,
            # Theme research tools
            "research_theme": self._exec_research_theme,
            "discover_themes": self._exec_discover_themes,
        }

    async def execute(self, tool_call) -> Dict[str, Any]:
        """
        Execute a tool call from the LLM.

        Args:
            tool_call: Tool call object from Groq API with:
                - function.name: str
                - function.arguments: str (JSON)

        Returns:
            Dict with tool result or error
        """
        name = tool_call.function.name

        try:
            args = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse tool arguments for {name}: {e}")
            return {"error": f"Invalid arguments: {e}"}

        logger.info(f"Executing tool: {name} with args: {args}")

        if name not in self.tool_map:
            logger.warning(f"Unknown tool: {name}")
            return {"error": f"Unknown tool: {name}"}

        try:
            result = await self.tool_map[name](args)

            if result is None:
                logger.warning(f"Tool {name} returned None")
                return {"error": f"No data returned from {name}"}

            logger.info(f"Tool {name} completed successfully")
            return result

        except Exception as e:
            logger.error(f"Error executing tool {name}: {e}", exc_info=True)
            return {"error": str(e)}

    # YFinance tool executors
    async def _exec_yfinance_quote(self, args: Dict[str, Any]) -> Optional[Dict]:
        """Get current stock quote."""
        symbol = args.get("symbol", "").upper()
        if not symbol:
            return {"error": "Symbol is required"}
        return self.yfinance_tools.get_current_quote(symbol)

    async def _exec_yfinance_fundamentals(self, args: Dict[str, Any]) -> Optional[Dict]:
        """Get stock fundamentals."""
        symbol = args.get("symbol", "").upper()
        if not symbol:
            return {"error": "Symbol is required"}
        return self.yfinance_tools.get_fundamentals(symbol)

    async def _exec_yfinance_history(self, args: Dict[str, Any]) -> Optional[Dict]:
        """Get price history."""
        symbol = args.get("symbol", "").upper()
        period = args.get("period", "3mo")
        if not symbol:
            return {"error": "Symbol is required"}
        return self.yfinance_tools.get_price_history(symbol, period)

    async def _exec_yfinance_earnings(self, args: Dict[str, Any]) -> Optional[Dict]:
        """Get earnings data."""
        symbol = args.get("symbol", "").upper()
        if not symbol:
            return {"error": "Symbol is required"}
        return self.yfinance_tools.get_earnings(symbol)

    async def _exec_compare_stocks(self, args: Dict[str, Any]) -> Optional[Dict]:
        """Compare multiple stocks."""
        symbols = args.get("symbols", [])
        if not symbols:
            return {"error": "Symbols list is required"}
        return self.yfinance_tools.compare_stocks(symbols)

    # Database tool executors
    async def _exec_get_scan_results(self, args: Dict[str, Any]) -> Optional[Dict]:
        """Get scan results for a symbol."""
        symbol = args.get("symbol", "").upper()
        if not symbol:
            return {"error": "Symbol is required"}
        return self.database_tools.get_stock_scan_results(symbol)

    async def _exec_search_stocks(self, args: Dict[str, Any]) -> Dict:
        """Search stocks by criteria."""
        results = self.database_tools.search_stocks_by_criteria(
            min_score=args.get("min_score"),
            min_rs_rating=args.get("min_rs_rating"),
            stage=args.get("stage"),
            sector=args.get("sector"),
            industry_group=args.get("industry_group"),
            rating=args.get("rating"),
            limit=args.get("limit", 20)
        )
        return {"stocks": results, "count": len(results)}

    async def _exec_get_theme_data(self, args: Dict[str, Any]) -> Dict:
        """Get theme data."""
        results = self.database_tools.get_theme_data(
            theme_name=args.get("theme_name"),
            limit=args.get("limit", 10)
        )
        return {"themes": results, "count": len(results)}

    async def _exec_get_trending_themes(self, args: Dict[str, Any]) -> Dict:
        """Get trending themes."""
        results = self.database_tools.get_trending_themes(
            limit=args.get("limit", 10)
        )
        return {"themes": results, "count": len(results)}

    async def _exec_get_breadth_data(self, args: Dict[str, Any]) -> Optional[Dict]:
        """Get market breadth data."""
        return self.database_tools.get_breadth_data(
            period=args.get("period", "1m"),
            market=args.get("market", "NYSE")
        )

    async def _exec_get_top_rated_stocks(self, args: Dict[str, Any]) -> Dict:
        """Get top rated stocks."""
        results = self.database_tools.get_top_rated_stocks(
            limit=args.get("limit", 10),
            rating=args.get("rating", "Strong Buy")
        )
        return {"stocks": results, "count": len(results)}

    # Web search tool executors
    async def _exec_web_search(self, args: Dict[str, Any]) -> Dict:
        """Execute web search."""
        query = args.get("query", "")
        if not query:
            return {"error": "Query is required"}
        return await self.web_search.search(
            query=query,
            max_results=args.get("max_results", 5),
            search_type="general"
        )

    async def _exec_search_news(self, args: Dict[str, Any]) -> Dict:
        """Search for news."""
        query = args.get("query", "")
        if not query:
            return {"error": "Query is required"}
        return await self.web_search.search_news(
            query=query,
            max_results=args.get("max_results", 5)
        )

    async def _exec_search_finance(self, args: Dict[str, Any]) -> Dict:
        """Search with finance context."""
        query = args.get("query", "")
        if not query:
            return {"error": "Query is required"}
        return await self.web_search.search_finance(
            query=query,
            max_results=args.get("max_results", 5)
        )

    # New database tool executors
    async def _exec_get_db_fundamentals(self, args: Dict[str, Any]) -> Optional[Dict]:
        """Get cached fundamentals from database."""
        symbol = args.get("symbol", "").upper()
        if not symbol:
            return {"error": "Symbol is required"}
        return self.database_tools.get_db_fundamentals(symbol)

    async def _exec_get_db_price_history(self, args: Dict[str, Any]) -> Optional[Dict]:
        """Get cached price history from database."""
        symbol = args.get("symbol", "").upper()
        if not symbol:
            return {"error": "Symbol is required"}
        return self.database_tools.get_db_price_history(
            symbol=symbol,
            days=args.get("days", 30)
        )

    async def _exec_advanced_stock_search(self, args: Dict[str, Any]) -> Dict:
        """Search stocks with advanced fundamental criteria."""
        results = self.database_tools.advanced_stock_search(
            min_eps_rating=args.get("min_eps_rating"),
            max_pe=args.get("max_pe"),
            min_profit_margin=args.get("min_profit_margin"),
            min_revenue_growth=args.get("min_revenue_growth"),
            min_roe=args.get("min_roe"),
            sector=args.get("sector"),
            has_description=args.get("has_description"),
            limit=args.get("limit", 20)
        )
        return {"stocks": results, "count": len(results)}

    # Document tool executors
    async def _exec_get_sec_10k(self, args: Dict[str, Any]) -> Dict:
        """Get SEC 10-K filing for a company."""
        symbol = args.get("symbol", "").upper()
        if not symbol:
            return {"error": "Symbol is required"}
        return await self.document_tools.get_sec_10k(
            symbol=symbol,
            year=args.get("year"),
            query=args.get("query"),
        )

    async def _exec_read_ir_pdf(self, args: Dict[str, Any]) -> Dict:
        """Read investor relations PDF from URL."""
        url = args.get("url", "")
        if not url:
            return {"error": "URL is required"}
        return await self.document_tools.read_ir_pdf(
            url=url,
            query=args.get("query"),
        )

    # Theme research tool executors
    async def _exec_research_theme(self, args: Dict[str, Any]) -> Optional[Dict]:
        """Deep research on a specific theme."""
        theme_name = args.get("theme_name", "")
        if not theme_name:
            return {"error": "theme_name is required"}
        result = self.database_tools.research_theme(
            theme_name=theme_name,
            include_sources=args.get("include_sources", True),
            include_history=args.get("include_history", False),
            max_sources=args.get("max_sources", 10),
            max_constituents=args.get("max_constituents", 20)
        )
        if result is None:
            return {"error": f"Theme '{theme_name}' not found"}
        return result

    async def _exec_discover_themes(self, args: Dict[str, Any]) -> Dict:
        """Discover and compare themes."""
        mode = args.get("mode", "trending")
        return self.database_tools.discover_themes(
            mode=mode,
            theme_names=args.get("theme_names"),
            min_velocity=args.get("min_velocity", 1.0),
            category=args.get("category"),
            limit=args.get("limit", 10)
        )

    async def close(self):
        """Clean up resources."""
        await self.web_search.close()
