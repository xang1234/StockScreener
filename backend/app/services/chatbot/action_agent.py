"""
Action Agent for the multi-agent chatbot.
Executes tools based on the research plan.
"""
import json
import logging
from typing import Dict, Any, Optional, List

from sqlalchemy.orm import Session

from .tools.web_search import WebSearchTool
from .tools.database_tools import DatabaseTools
from .tools.yfinance_tools import YFinanceTools

logger = logging.getLogger(__name__)


class ActionAgent:
    """Agent that executes tools to gather data."""

    def __init__(self, db: Session):
        self.db = db
        self.web_search = WebSearchTool()
        self.database_tools = DatabaseTools(db)
        self.yfinance_tools = YFinanceTools()

        # Map tool names to methods
        self.tool_map = {
            # Database tools
            "get_scan_results": self._execute_get_scan_results,
            "search_stocks": self._execute_search_stocks,
            "get_theme_data": self._execute_get_theme_data,
            "get_trending_themes": self._execute_get_trending_themes,
            "get_breadth_data": self._execute_get_breadth_data,
            "get_top_rated_stocks": self._execute_get_top_rated_stocks,
            # YFinance tools
            "yfinance_quote": self._execute_yfinance_quote,
            "yfinance_fundamentals": self._execute_yfinance_fundamentals,
            "yfinance_history": self._execute_yfinance_history,
            "yfinance_earnings": self._execute_yfinance_earnings,
            "compare_stocks": self._execute_compare_stocks,
            # Web search tools
            "web_search": self._execute_web_search,
            "search_news": self._execute_search_news,
            "search_finance": self._execute_search_finance,
        }

    async def execute_step(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single plan step.

        Args:
            step: Step from the plan with tool and params

        Returns:
            Dict with execution results
        """
        tool_name = step.get("tool", "")
        params = step.get("params", {})

        logger.info(f"Executing tool: {tool_name} with params: {params}")

        if tool_name not in self.tool_map:
            return {
                "tool": tool_name,
                "params": params,
                "status": "error",
                "error": f"Unknown tool: {tool_name}",
                "result": None
            }

        try:
            result = await self.tool_map[tool_name](params)
            return {
                "tool": tool_name,
                "params": params,
                "status": "success" if result else "empty",
                "result": result,
                "notes": self._generate_notes(tool_name, result)
            }
        except Exception as e:
            logger.error(f"Error executing {tool_name}: {e}")
            return {
                "tool": tool_name,
                "params": params,
                "status": "error",
                "error": str(e),
                "result": None,
                "alternative": self._suggest_alternative(tool_name, params)
            }

    async def execute_plan(self, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Execute all steps in a plan.

        Args:
            plan: Research plan with steps

        Returns:
            List of results from each step
        """
        results = []
        steps = plan.get("steps", [])

        for step in steps:
            result = await self.execute_step(step)
            results.append(result)

            # If a critical step fails, log but continue
            if result.get("status") == "error":
                logger.warning(f"Step {step.get('step')} failed: {result.get('error')}")

        return results

    def _generate_notes(self, tool_name: str, result: Any) -> Optional[str]:
        """Generate notes about the tool result."""
        if not result:
            return "No data returned"

        if isinstance(result, dict):
            if "error" in result:
                return f"Partial data with error: {result['error']}"
            if "total_results" in result and result["total_results"] == 0:
                return "Search returned no results"

        if isinstance(result, list) and len(result) == 0:
            return "Empty result set"

        return None

    def _suggest_alternative(self, tool_name: str, params: Dict) -> Optional[str]:
        """Suggest an alternative tool if the primary fails."""
        alternatives = {
            "get_scan_results": "yfinance_quote",
            "yfinance_fundamentals": "yfinance_quote",
            "web_search": "search_finance",
            "search_news": "web_search",
        }
        return alternatives.get(tool_name)

    # Database tool executors
    async def _execute_get_scan_results(self, params: Dict) -> Optional[Dict]:
        """Execute get_scan_results tool."""
        symbol = params.get("symbol", "")
        return self.database_tools.get_stock_scan_results(symbol)

    async def _execute_search_stocks(self, params: Dict) -> List[Dict]:
        """Execute search_stocks tool."""
        return self.database_tools.search_stocks_by_criteria(
            min_score=params.get("min_score"),
            min_rs_rating=params.get("min_rs_rating"),
            stage=params.get("stage"),
            sector=params.get("sector"),
            industry_group=params.get("industry_group"),
            rating=params.get("rating"),
            limit=params.get("limit", 20)
        )

    async def _execute_get_theme_data(self, params: Dict) -> List[Dict]:
        """Execute get_theme_data tool."""
        return self.database_tools.get_theme_data(
            theme_name=params.get("theme_name"),
            limit=params.get("limit", 10)
        )

    async def _execute_get_trending_themes(self, params: Dict) -> List[Dict]:
        """Execute get_trending_themes tool."""
        return self.database_tools.get_trending_themes(
            limit=params.get("limit", 10)
        )

    async def _execute_get_breadth_data(self, params: Dict) -> Optional[Dict]:
        """Execute get_breadth_data tool."""
        return self.database_tools.get_breadth_data(
            period=params.get("period", "1m"),
            market=params.get("market", "NYSE")
        )

    async def _execute_get_top_rated_stocks(self, params: Dict) -> List[Dict]:
        """Execute get_top_rated_stocks tool."""
        return self.database_tools.get_top_rated_stocks(
            limit=params.get("limit", 10),
            rating=params.get("rating", "Strong Buy")
        )

    # YFinance tool executors
    async def _execute_yfinance_quote(self, params: Dict) -> Optional[Dict]:
        """Execute yfinance_quote tool."""
        symbol = params.get("symbol", "")
        return self.yfinance_tools.get_current_quote(symbol)

    async def _execute_yfinance_fundamentals(self, params: Dict) -> Optional[Dict]:
        """Execute yfinance_fundamentals tool."""
        symbol = params.get("symbol", "")
        return self.yfinance_tools.get_fundamentals(symbol)

    async def _execute_yfinance_history(self, params: Dict) -> Optional[Dict]:
        """Execute yfinance_history tool."""
        symbol = params.get("symbol", "")
        period = params.get("period", "3mo")
        return self.yfinance_tools.get_price_history(symbol, period)

    async def _execute_yfinance_earnings(self, params: Dict) -> Optional[Dict]:
        """Execute yfinance_earnings tool."""
        symbol = params.get("symbol", "")
        return self.yfinance_tools.get_earnings(symbol)

    async def _execute_compare_stocks(self, params: Dict) -> Optional[Dict]:
        """Execute compare_stocks tool."""
        symbols = params.get("symbols", [])
        return self.yfinance_tools.compare_stocks(symbols)

    # Web search tool executors
    async def _execute_web_search(self, params: Dict) -> Dict:
        """Execute web_search tool."""
        query = params.get("query", "")
        max_results = params.get("max_results", 5)
        return await self.web_search.search(query, max_results)

    async def _execute_search_news(self, params: Dict) -> Dict:
        """Execute search_news tool."""
        query = params.get("query", "")
        max_results = params.get("max_results", 5)
        return await self.web_search.search_news(query, max_results)

    async def _execute_search_finance(self, params: Dict) -> Dict:
        """Execute search_finance tool."""
        query = params.get("query", "")
        max_results = params.get("max_results", 5)
        return await self.web_search.search_finance(query, max_results)

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get descriptions of all available tools."""
        tools = []
        tools.extend(self.database_tools.get_tool_descriptions())
        tools.extend(self.yfinance_tools.get_tool_descriptions())
        tools.append(self.web_search.get_tool_description())
        return tools

    async def close(self):
        """Clean up resources."""
        await self.web_search.close()
