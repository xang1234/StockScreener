"""
Web Search Tool for the chatbot.
Uses ddgs metasearch library - no API keys required.
"""
import asyncio
import logging
from typing import Dict, Any, List

from ddgs import DDGS

logger = logging.getLogger(__name__)


class WebSearchTool:
    """Web search using ddgs metasearch library."""

    def __init__(self):
        pass  # No API keys needed

    async def search(
        self,
        query: str,
        max_results: int = 5,
        search_type: str = "general"
    ) -> Dict[str, Any]:
        """
        Execute web search.

        Args:
            query: Search query
            max_results: Maximum number of results to return
            search_type: Type of search (general, news, finance)

        Returns:
            Dict with search results and metadata
        """
        if search_type == "news":
            return await self.search_news(query, max_results)
        elif search_type == "finance":
            return await self.search_finance(query, max_results)

        # Run synchronous ddgs in thread pool
        results = await asyncio.to_thread(
            self._text_search, query, max_results
        )
        return self._format_results(query, results)

    def _text_search(self, query: str, max_results: int) -> List[Dict[str, str]]:
        """Execute text search using ddgs (synchronous)."""
        try:
            return DDGS().text(
                query,
                region="us-en",
                safesearch="moderate",
                max_results=max_results,
                backend="auto"
            )
        except Exception as e:
            logger.error(f"ddgs text search failed: {e}")
            return []

    def _news_search(self, query: str, max_results: int) -> List[Dict[str, str]]:
        """Execute news search using ddgs (synchronous)."""
        try:
            return DDGS().news(
                query,
                region="us-en",
                safesearch="off",
                timelimit="w",  # Last week
                max_results=max_results,
                backend="auto"
            )
        except Exception as e:
            logger.error(f"ddgs news search failed: {e}")
            return []

    def _format_results(self, query: str, results: List[Dict[str, str]], search_type: str = "web") -> Dict[str, Any]:
        """Normalize results to expected format with references."""
        formatted = []
        references = []

        for item in results:
            title = item.get("title", "")
            url = item.get("href") or item.get("url", "")
            snippet = item.get("body") or item.get("snippet", "")

            formatted.append({
                "title": title,
                "url": url,
                "snippet": snippet,
                "score": 0,
            })

            # Add to references
            if url:
                references.append({
                    "type": "news" if search_type == "news" else "web",
                    "title": title or url,
                    "url": url,
                    "snippet": snippet[:150] + "..." if len(snippet) > 150 else snippet,
                })

        return {
            "query": query,
            "answer": None,
            "results": formatted,
            "total_results": len(formatted),
            "provider": "ddgs",
            "references": references,
        }

    async def search_news(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """Search for recent news articles."""
        results = await asyncio.to_thread(
            self._news_search, query, max_results
        )
        return self._format_results(query, results, search_type="news")

    async def search_finance(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """Search with finance context."""
        finance_query = f"{query} stock finance"
        results = await asyncio.to_thread(
            self._text_search, finance_query, max_results
        )
        return self._format_results(query, results, search_type="finance")

    async def close(self):
        """No resources to close."""
        pass

    def get_tool_description(self) -> Dict[str, Any]:
        """Return tool description for the action agent."""
        return {
            "name": "web_search",
            "description": "Search the web for information. Use for current events, news, and external data not in the database.",
            "parameters": {
                "query": {"type": "string", "description": "The search query"},
                "max_results": {"type": "integer", "description": "Max results (default 5)", "default": 5},
                "search_type": {"type": "string", "description": "Type: general, news, finance", "default": "general"},
            },
            "required": ["query"],
        }
