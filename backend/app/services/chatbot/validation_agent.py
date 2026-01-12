"""
Validation Agent for the multi-agent chatbot.
Verifies that gathered data is complete and accurate.
"""
import json
import logging
import os
from typing import Dict, Any, Optional, List

from groq import Groq

from ...config import settings
from .prompts import VALIDATION_AGENT_PROMPT

logger = logging.getLogger(__name__)


class ValidationAgent:
    """Agent that validates gathered research data."""

    GROQ_MODELS = [
        "qwen/qwen3-32b",
        "llama-3.3-70b-versatile",
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

    async def validate(
        self,
        query: str,
        plan: Dict[str, Any],
        results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Validate the gathered data.

        Args:
            query: Original user query
            plan: The research plan
            results: Results from executed steps

        Returns:
            Validation result with completeness assessment
        """
        try:
            # Use heuristic validation for speed
            # Only call LLM for complex queries
            if plan.get("complexity") in ["simple", "moderate"]:
                return self._heuristic_validate(query, plan, results)

            return await self._llm_validate(query, plan, results)

        except Exception as e:
            logger.error(f"Error validating: {e}")
            return self._fallback_validation(results)

    def _heuristic_validate(
        self,
        query: str,
        plan: Dict[str, Any],
        results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Fast heuristic-based validation."""
        successful_steps = [r for r in results if r.get("status") == "success"]
        failed_steps = [r for r in results if r.get("status") == "error"]

        # Calculate completeness
        total_steps = len(results)
        success_ratio = len(successful_steps) / total_steps if total_steps > 0 else 0

        # Check data quality
        has_price = any(
            r.get("result", {}).get("price") or
            r.get("result", {}).get("current_price")
            for r in results if isinstance(r.get("result"), dict)
        )

        has_fundamental = any(
            r.get("tool") in ["yfinance_fundamentals", "get_scan_results"]
            and r.get("status") == "success"
            for r in results
        )

        has_technical = any(
            r.get("result", {}).get("rs_rating") or
            r.get("result", {}).get("ma_50")
            for r in results if isinstance(r.get("result"), dict)
        )

        has_sentiment = any(
            r.get("tool") in ["web_search", "search_news", "search_finance"]
            and r.get("status") == "success"
            for r in results
        )

        # Determine if we need more research
        needs_more = success_ratio < 0.5 or (
            plan.get("complexity") == "complex" and success_ratio < 0.7
        )

        # Collect issues
        issues = []
        if failed_steps:
            issues.extend([f"Tool {r.get('tool')} failed: {r.get('error', 'unknown')}" for r in failed_steps])

        empty_results = [r for r in results if r.get("status") == "empty"]
        if empty_results:
            issues.extend([f"Tool {r.get('tool')} returned no data" for r in empty_results])

        return {
            "is_valid": success_ratio >= 0.5,
            "completeness_score": success_ratio,
            "data_quality": {
                "has_price_data": has_price,
                "has_fundamental_data": has_fundamental,
                "has_technical_data": has_technical,
                "has_sentiment_data": has_sentiment,
            },
            "issues": issues,
            "missing_data": self._identify_missing_data(plan, results),
            "needs_more_research": needs_more,
            "additional_steps": self._suggest_additional_steps(plan, results) if needs_more else [],
            "ready_for_answer": success_ratio >= 0.3  # Allow answers with partial data
        }

    async def _llm_validate(
        self,
        query: str,
        plan: Dict[str, Any],
        results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """LLM-based validation for complex queries."""
        # Prepare context for the LLM
        context = {
            "query": query,
            "plan": plan,
            "results": [
                {
                    "tool": r.get("tool"),
                    "status": r.get("status"),
                    "has_data": bool(r.get("result")),
                    "error": r.get("error"),
                }
                for r in results
            ]
        }

        messages = [
            {"role": "system", "content": VALIDATION_AGENT_PROMPT},
            {"role": "user", "content": f"Validate this research:\n{json.dumps(context, indent=2)}"}
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2,
                max_tokens=1000,
            )

            content = response.choices[0].message.content.strip()
            return self._parse_validation(content)

        except Exception as e:
            logger.warning(f"LLM validation failed: {e}")
            return self._heuristic_validate(query, plan, results)

    def _parse_validation(self, response: str) -> Dict[str, Any]:
        """Parse validation response from LLM."""
        try:
            # Handle markdown code blocks
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                response = response[start:end].strip()
            elif "```" in response:
                start = response.find("```") + 3
                end = response.find("```", start)
                response = response[start:end].strip()

            return json.loads(response)
        except json.JSONDecodeError:
            logger.warning("Failed to parse validation JSON")
            return self._fallback_validation([])

    def _identify_missing_data(
        self,
        plan: Dict[str, Any],
        results: List[Dict[str, Any]]
    ) -> List[str]:
        """Identify what data is missing from results."""
        missing = []

        # Check what was planned vs what succeeded
        planned_tools = {step.get("tool") for step in plan.get("steps", [])}
        successful_tools = {r.get("tool") for r in results if r.get("status") == "success"}

        failed_tools = planned_tools - successful_tools
        for tool in failed_tools:
            missing.append(f"Data from {tool}")

        return missing

    def _suggest_additional_steps(
        self,
        plan: Dict[str, Any],
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Suggest additional research steps."""
        suggestions = []

        # If database query failed, suggest external data
        for r in results:
            if r.get("status") == "error" and r.get("alternative"):
                suggestions.append({
                    "tool": r.get("alternative"),
                    "params": r.get("params", {}),
                    "reason": f"Alternative for failed {r.get('tool')}"
                })

        return suggestions[:3]  # Limit to 3 suggestions

    def _fallback_validation(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Fallback validation when everything else fails."""
        has_any_data = any(r.get("status") == "success" for r in results)

        return {
            "is_valid": has_any_data,
            "completeness_score": 0.3 if has_any_data else 0.0,
            "data_quality": {
                "has_price_data": False,
                "has_fundamental_data": False,
                "has_technical_data": False,
                "has_sentiment_data": False,
            },
            "issues": ["Validation could not be completed properly"],
            "missing_data": [],
            "needs_more_research": False,
            "additional_steps": [],
            "ready_for_answer": has_any_data
        }
