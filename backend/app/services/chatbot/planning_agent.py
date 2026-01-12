"""
Planning Agent for the multi-agent chatbot.
Decomposes user queries into structured research plans.
"""
import json
import logging
import os
from typing import Dict, Any, Optional, List

from groq import Groq

from ...config import settings
from .prompts import PLANNING_AGENT_PROMPT

logger = logging.getLogger(__name__)


class PlanningAgent:
    """Agent that creates research plans from user queries."""

    GROQ_MODELS = [
        "qwen/qwen3-32b",  # Primary model
        "llama-3.3-70b-versatile",  # Fallback
    ]

    def __init__(self):
        self._init_client()

    def _init_client(self):
        """Initialize the Groq client."""
        groq_api_key = settings.groq_api_key or os.environ.get("GROQ_API_KEY")

        if not groq_api_key:
            raise ValueError("GROQ_API_KEY not configured")

        self.client = Groq(api_key=groq_api_key)
        self.model = self.GROQ_MODELS[0]
        logger.info(f"PlanningAgent initialized with model: {self.model}")

    async def create_plan(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Create a research plan for the given query.

        Args:
            query: User's question
            conversation_history: Previous messages for context

        Returns:
            Dict with the research plan
        """
        try:
            # Build messages
            messages = [
                {"role": "system", "content": PLANNING_AGENT_PROMPT}
            ]

            # Add conversation history for context
            if conversation_history:
                for msg in conversation_history[-5:]:  # Last 5 messages
                    messages.append({
                        "role": msg.get("role", "user"),
                        "content": msg.get("content", "")
                    })

            messages.append({
                "role": "user",
                "content": f"Create a research plan for: {query}"
            })

            # Call Groq with Qwen
            response = await self._generate(messages)

            # Parse the JSON response
            plan = self._parse_plan(response)

            logger.info(f"Created plan with {len(plan.get('steps', []))} steps")
            return plan

        except Exception as e:
            logger.error(f"Error creating plan: {e}")
            # Return a simple default plan
            return self._default_plan(query)

    async def _generate(self, messages: List[Dict[str, str]]) -> str:
        """Generate response using Groq."""
        for model in self.GROQ_MODELS:
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.3,
                    max_tokens=1500,
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                logger.warning(f"Model {model} failed: {e}")
                continue

        raise RuntimeError("All Groq models failed")

    def _parse_plan(self, response: str) -> Dict[str, Any]:
        """Parse the plan JSON from the response."""
        try:
            # Try to find JSON in the response
            response = response.strip()

            # Handle markdown code blocks
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                response = response[start:end].strip()
            elif "```" in response:
                start = response.find("```") + 3
                end = response.find("```", start)
                response = response[start:end].strip()

            plan = json.loads(response)

            # Validate required fields
            if "steps" not in plan:
                plan["steps"] = []
            if "intent" not in plan:
                plan["intent"] = "unknown"

            return plan

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse plan JSON: {e}")
            return {
                "intent": "parse_error",
                "complexity": "simple",
                "steps": [],
                "error": str(e),
                "raw_response": response[:500]
            }

    def _default_plan(self, query: str) -> Dict[str, Any]:
        """Create a default plan for error cases."""
        # Simple heuristics for default plan
        query_lower = query.lower()

        steps = []

        # Check for stock symbols (uppercase 1-5 letters)
        import re
        symbols = re.findall(r'\b[A-Z]{1,5}\b', query)
        if symbols:
            symbol = symbols[0]
            steps.append({
                "step": 1,
                "action": "query_database",
                "tool": "get_scan_results",
                "params": {"symbol": symbol},
                "reason": "Get internal analysis"
            })
            steps.append({
                "step": 2,
                "action": "fetch_external",
                "tool": "yfinance_quote",
                "params": {"symbol": symbol},
                "reason": "Get current price"
            })

        # Check for theme queries
        if any(word in query_lower for word in ["theme", "trend", "sector"]):
            steps.append({
                "step": len(steps) + 1,
                "action": "query_database",
                "tool": "get_trending_themes",
                "params": {"limit": 10},
                "reason": "Get trending themes"
            })

        # Check for market breadth queries
        if any(word in query_lower for word in ["market", "breadth", "advance", "decline"]):
            steps.append({
                "step": len(steps) + 1,
                "action": "query_database",
                "tool": "get_breadth_data",
                "params": {"period": "1m"},
                "reason": "Get market breadth"
            })

        # Check for top stocks queries
        if any(word in query_lower for word in ["best", "top", "strong"]):
            steps.append({
                "step": len(steps) + 1,
                "action": "query_database",
                "tool": "get_top_rated_stocks",
                "params": {"limit": 10},
                "reason": "Get top rated stocks"
            })

        # Default to web search if nothing else matches
        if not steps:
            steps.append({
                "step": 1,
                "action": "web_search",
                "tool": "web_search",
                "params": {"query": query, "max_results": 5},
                "reason": "Search for relevant information"
            })

        return {
            "intent": "auto_generated",
            "complexity": "simple",
            "steps": steps,
            "expected_output": "Response based on gathered data"
        }

    def estimate_complexity(self, query: str) -> str:
        """Estimate query complexity for resource planning."""
        query_lower = query.lower()

        # Complex queries
        if any(word in query_lower for word in ["compare", "analysis", "detailed", "comprehensive"]):
            return "complex"

        # Moderate queries
        if any(word in query_lower for word in ["list", "find", "search", "show"]):
            return "moderate"

        # Simple queries
        return "simple"
