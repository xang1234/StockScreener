"""
Answer Agent for the multi-agent chatbot.
Synthesizes gathered data into clear, actionable responses.
"""
import json
import logging
import os
from typing import Dict, Any, Optional, List, AsyncGenerator

from groq import Groq

from ...config import settings
from .prompts import ANSWER_AGENT_PROMPT

logger = logging.getLogger(__name__)


class AnswerAgent:
    """Agent that synthesizes research into responses."""

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

    async def generate_answer(
        self,
        query: str,
        plan: Dict[str, Any],
        results: List[Dict[str, Any]],
        validation: Dict[str, Any]
    ) -> str:
        """
        Generate the final answer from gathered data.

        Args:
            query: Original user query
            plan: The research plan
            results: Results from executed steps
            validation: Validation results

        Returns:
            Formatted answer string
        """
        try:
            # Prepare the data context
            context = self._prepare_context(query, plan, results, validation)

            messages = [
                {"role": "system", "content": ANSWER_AGENT_PROMPT},
                {"role": "user", "content": context}
            ]

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.4,
                max_tokens=2000,
            )

            answer = response.choices[0].message.content.strip()

            # Add data quality disclaimer if needed
            if validation.get("completeness_score", 1.0) < 0.7:
                answer += "\n\n*Note: Some data could not be retrieved. Response is based on partial information.*"

            return answer

        except Exception as e:
            logger.error(f"Error generating answer: {e}")
            return self._fallback_answer(query, results)

    async def generate_answer_streaming(
        self,
        query: str,
        plan: Dict[str, Any],
        results: List[Dict[str, Any]],
        validation: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """
        Generate the final answer with streaming.

        Yields:
            Chunks of the answer as they're generated
        """
        try:
            context = self._prepare_context(query, plan, results, validation)

            messages = [
                {"role": "system", "content": ANSWER_AGENT_PROMPT},
                {"role": "user", "content": context}
            ]

            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.4,
                max_tokens=2000,
                stream=True,
            )

            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

            # Add disclaimer if needed
            if validation.get("completeness_score", 1.0) < 0.7:
                yield "\n\n*Note: Some data could not be retrieved. Response is based on partial information.*"

        except Exception as e:
            logger.error(f"Error in streaming answer: {e}")
            yield self._fallback_answer(query, results)

    def _prepare_context(
        self,
        query: str,
        plan: Dict[str, Any],
        results: List[Dict[str, Any]],
        validation: Dict[str, Any]
    ) -> str:
        """Prepare context for the answer generation."""
        # Format results for the LLM
        formatted_results = []
        for r in results:
            if r.get("status") == "success" and r.get("result"):
                formatted_results.append({
                    "source": r.get("tool"),
                    "data": self._summarize_result(r.get("result"))
                })

        context = f"""USER QUESTION: {query}

RESEARCH INTENT: {plan.get('intent', 'Answer the user question')}

GATHERED DATA:
{json.dumps(formatted_results, indent=2, default=str)}

DATA QUALITY:
- Completeness: {validation.get('completeness_score', 0) * 100:.0f}%
- Has price data: {validation.get('data_quality', {}).get('has_price_data', False)}
- Has fundamental data: {validation.get('data_quality', {}).get('has_fundamental_data', False)}
- Has technical data: {validation.get('data_quality', {}).get('has_technical_data', False)}

ISSUES: {', '.join(validation.get('issues', [])) or 'None'}

Based on this data, provide a clear, helpful answer to the user's question. Use markdown formatting."""

        return context

    def _summarize_result(self, result: Any) -> Any:
        """Summarize a result to reduce context size."""
        if not isinstance(result, dict):
            return result

        # Limit nested data
        summarized = {}
        for key, value in result.items():
            if isinstance(value, list) and len(value) > 5:
                summarized[key] = value[:5]  # Keep first 5 items
                summarized[f"{key}_count"] = len(value)
            elif isinstance(value, dict) and len(value) > 10:
                # Keep only important keys
                important_keys = ["symbol", "name", "price", "score", "rating", "status"]
                summarized[key] = {k: v for k, v in value.items() if k in important_keys}
            else:
                summarized[key] = value

        return summarized

    def _fallback_answer(self, query: str, results: List[Dict[str, Any]]) -> str:
        """Generate a fallback answer when LLM fails."""
        # Try to extract any useful data
        data_points = []

        for r in results:
            if r.get("status") == "success" and r.get("result"):
                result = r.get("result")
                if isinstance(result, dict):
                    if "symbol" in result:
                        data_points.append(f"**{result.get('symbol')}**: Price ${result.get('price', result.get('current_price', 'N/A'))}")
                    if "name" in result and "velocity" in result:
                        data_points.append(f"Theme: **{result.get('name')}** (velocity: {result.get('velocity', 'N/A')})")

        if data_points:
            return f"Here's what I found:\n\n" + "\n".join(data_points)

        return f"I apologize, but I couldn't retrieve enough data to answer your question about: *{query}*. Please try rephrasing your question or asking about a specific stock symbol."

    async def generate_quick_answer(self, query: str, data: Dict[str, Any]) -> str:
        """Generate a quick answer for simple queries without full pipeline."""
        if not data:
            return "I couldn't find any data for that query."

        # Simple template-based responses for common queries
        if "symbol" in data and "price" in data:
            symbol = data.get("symbol", "")
            price = data.get("price", data.get("current_price", "N/A"))
            rating = data.get("rating", "N/A")
            score = data.get("composite_score", "N/A")

            response = f"**{symbol}** is currently trading at **${price}**"
            if rating != "N/A":
                response += f" with a rating of **{rating}**"
            if score != "N/A":
                response += f" (score: {score})"

            # Add more details if available
            if data.get("rs_rating"):
                response += f"\n- RS Rating: {data.get('rs_rating')}"
            if data.get("stage"):
                response += f"\n- Stage: {data.get('stage')}"
            if data.get("gics_sector"):
                response += f"\n- Sector: {data.get('gics_sector')}"

            return response

        # For theme data
        if isinstance(data, list) and data and "name" in data[0]:
            themes = [f"- **{t.get('name')}**: {t.get('description', 'N/A')[:100]}" for t in data[:5]]
            return "Here are the themes I found:\n\n" + "\n".join(themes)

        return f"Here's what I found:\n```json\n{json.dumps(data, indent=2, default=str)[:1000]}\n```"
