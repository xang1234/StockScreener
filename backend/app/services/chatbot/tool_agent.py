"""
Tool Agent for the chatbot.
Uses LiteLLM for unified LLM access with automatic fallbacks.
"""
import json
import logging
import re
from typing import Dict, Any, List, AsyncGenerator, Optional, Tuple

from sqlalchemy.orm import Session

from ...config import settings
from ..llm import LLMService, LLMError, LLMRateLimitError, LLMContextWindowError
from .tool_definitions import CHATBOT_TOOLS
from .tool_executor import ToolExecutor
from .prompts import TOOL_AGENT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class ToolAgent:
    """Agent that uses LLMService for tool calling with automatic fallbacks."""

    MAX_TOOL_ITERATIONS = 5  # Prevent infinite tool calling loops

    def __init__(self, db: Session):
        self.db = db
        self.llm = LLMService(use_case="chatbot")
        self.tool_executor = ToolExecutor(db)
        logger.info("ToolAgent initialized with LLMService (chatbot preset)")

    def _filter_tools(self, enabled_tools: Optional[List[str]]) -> List[Dict]:
        """
        Filter tools based on enabled list.

        Args:
            enabled_tools: List of enabled tool names, or None for all tools

        Returns:
            Filtered list of tool definitions
        """
        if not enabled_tools:
            return CHATBOT_TOOLS

        enabled_set = set(enabled_tools)
        return [t for t in CHATBOT_TOOLS if t["function"]["name"] in enabled_set]

    async def process_message(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
        enabled_tools: Optional[List[str]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process a user message with native tool calling.

        Args:
            message: User's message
            history: Previous conversation messages
            enabled_tools: List of enabled tool names, or None for all tools

        Yields:
            Stream chunks with progress and results:
            - {"type": "thinking", "content": "..."}
            - {"type": "tool_call", "tool": "...", "args": {...}}
            - {"type": "tool_result", "tool": "...", "result": {...}}
            - {"type": "content", "content": "..."}
        """
        # Filter tools based on enabled list
        tools = self._filter_tools(enabled_tools)

        # Build message list
        messages = [
            {"role": "system", "content": TOOL_AGENT_SYSTEM_PROMPT}
        ]

        # Add conversation history
        if history:
            for msg in history[-10:]:  # Keep last 10 messages for context
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })

        # Add current user message
        messages.append({"role": "user", "content": message})

        yield {"type": "thinking", "content": "Analyzing your question..."}

        try:
            # First LLM call with tools
            response = await self._call_llm_with_tools(messages, tools)

            # Process tool calls iteratively
            iteration = 0
            ref_counter = 1  # Track reference numbers for INDIVIDUAL references (not tool calls)
            while response.choices[0].message.tool_calls and iteration < self.MAX_TOOL_ITERATIONS:
                iteration += 1
                assistant_message = response.choices[0].message

                # Add assistant's response (with tool calls) to messages
                messages.append({
                    "role": "assistant",
                    "content": assistant_message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in assistant_message.tool_calls
                    ]
                })

                # Execute each tool call
                for tool_call in assistant_message.tool_calls:
                    tool_name = tool_call.function.name
                    try:
                        tool_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        tool_args = {}

                    yield {
                        "type": "tool_call",
                        "tool": tool_name,
                        "args": tool_args
                    }

                    # Execute the tool
                    result = await self.tool_executor.execute(tool_call)

                    # Number individual references within the result (not the tool call itself)
                    numbered_refs = []
                    if isinstance(result, dict) and "references" in result:
                        for ref in result["references"]:
                            ref_with_num = {**ref, "reference_number": ref_counter}
                            numbered_refs.append(ref_with_num)
                            ref_counter += 1
                        # Update result with numbered references
                        result["references"] = numbered_refs

                    # Summarize result for streaming
                    summarized_result = self._summarize_result(result)

                    # Yield tool result with numbered references
                    tool_result_yield = {
                        "type": "tool_result",
                        "tool": tool_name,
                        "result": summarized_result,
                    }
                    if numbered_refs:
                        tool_result_yield["references"] = numbered_refs
                    yield tool_result_yield

                    # Add tool result to messages with reference metadata for LLM
                    tool_content = {
                        "source_type": self._get_source_type(tool_name),
                        "data": result
                    }
                    # Tell LLM exactly which reference numbers to use
                    if numbered_refs:
                        tool_content["citation_instructions"] = f"When citing information from this result, use these exact reference numbers: {[r['reference_number'] for r in numbered_refs]}. Each article/source has its own number."
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": json.dumps(tool_content, default=str)
                    })

                # Get next response (may have more tool calls or final answer)
                yield {"type": "thinking", "content": "Processing results..."}
                response = await self._call_llm_with_tools(messages, tools)

            # Extract final answer and reasoning
            message = response.choices[0].message
            final_content = message.content or ""

            # Extract reasoning - check parsed format first, then fallback to <think> tags
            reasoning = None

            # Check for parsed reasoning (from reasoning_format="parsed")
            if hasattr(message, 'reasoning') and message.reasoning:
                reasoning = message.reasoning
            elif hasattr(message, 'reasoning_content') and message.reasoning_content:
                reasoning = message.reasoning_content
            else:
                # Fallback: extract from <think> tags if present in content
                reasoning, final_content = self._extract_reasoning(final_content)

            # Yield reasoning as thinking (if present)
            if reasoning:
                yield {"type": "thinking", "content": reasoning}

            # Stream the final response
            if final_content:
                yield {"type": "content", "content": final_content}
            else:
                yield {
                    "type": "content",
                    "content": "I apologize, but I couldn't generate a response. Please try rephrasing your question."
                }

        except Exception as e:
            logger.error(f"Error in tool agent: {e}", exc_info=True)
            yield {
                "type": "error",
                "error": str(e)
            }

    async def _call_llm_with_tools(self, messages: List[Dict], tools: List[Dict]) -> Any:
        """
        Call LLM with tools using LLMService.

        Args:
            messages: Message list
            tools: List of tool definitions to use

        Returns:
            LLM API response
        """
        # Format messages for the API
        formatted_messages = self._format_messages_for_api(messages)

        try:
            response = await self.llm.completion(
                messages=formatted_messages,
                tools=tools,
                tool_choice="auto",
                max_tokens=8000,
            )
            return response

        except LLMContextWindowError as e:
            logger.error(f"Context window exceeded: {e}")
            raise

        except LLMRateLimitError as e:
            logger.error(f"Rate limit exhausted: {e}")
            raise

        except LLMError as e:
            logger.error(f"LLM error: {e}")
            raise

    def _format_messages_for_api(self, messages: List[Dict]) -> List[Dict]:
        """
        Format messages for LLM API.

        Handles special cases like tool_calls and tool results.
        """
        formatted = []
        for msg in messages:
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                # Assistant message with tool calls
                formatted.append({
                    "role": "assistant",
                    "content": msg.get("content") or None,
                    "tool_calls": msg["tool_calls"]
                })
            elif msg.get("role") == "tool":
                # Tool result message
                formatted.append({
                    "role": "tool",
                    "tool_call_id": msg["tool_call_id"],
                    "name": msg.get("name", ""),
                    "content": msg["content"]
                })
            else:
                # Regular message
                formatted.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        return formatted

    def _summarize_result(self, result: Any) -> Any:
        """Summarize result for streaming (reduce payload size)."""
        if not result:
            return None

        if isinstance(result, dict):
            # Check if this is a search/news result - return full results for display
            if "results" in result and "query" in result:
                # This is a web_search/search_news/search_finance result
                # Return full results so frontend can display them
                summary = {
                    "query": result.get("query"),
                    "total_results": result.get("total_results", len(result.get("results", []))),
                    "results": result.get("results", []),
                    "provider": result.get("provider"),
                }
                # Preserve references for the orchestrator
                if "references" in result:
                    summary["references"] = result["references"]
                return summary

            # Keep only key fields for streaming updates
            summary = {}
            important_keys = [
                "symbol", "name", "price", "current_price", "score",
                "rating", "status", "total_results", "query", "error",
                "market_cap", "pe_ratio", "count"
            ]
            for key in important_keys:
                if key in result:
                    summary[key] = result[key]

            # Always preserve references for source tracking
            if "references" in result:
                summary["references"] = result["references"]

            # For lists, show count
            for key, value in result.items():
                if isinstance(value, list) and key != "references":
                    summary[f"{key}_count"] = len(value)

            return summary if summary else {"data": "received"}

        if isinstance(result, list):
            return {"items": len(result)}

        return result

    def _get_source_type(self, tool_name: str) -> str:
        """Map tool name to source type for citations."""
        if tool_name in ["search_news"]:
            return "news"
        elif tool_name in ["web_search", "search_finance"]:
            return "web"
        elif tool_name in ["get_sec_10k", "read_ir_pdf"]:
            return "document"
        else:
            return "data"

    def _extract_reasoning(self, content: str) -> Tuple[Optional[str], str]:
        """
        Extract reasoning from <think> tags in Groq response.

        Args:
            content: Raw response content that may contain <think>...</think> tags

        Returns:
            Tuple of (reasoning, clean_content) where reasoning is the extracted
            thinking content and clean_content is the response without think tags.
        """
        if not content:
            return None, content

        # Pattern to match <think>...</think> tags (can span multiple lines)
        think_pattern = r'<think>(.*?)</think>'
        matches = re.findall(think_pattern, content, re.DOTALL)

        if matches:
            # Join all thinking sections
            reasoning = '\n'.join(match.strip() for match in matches)
            # Remove think tags from content
            clean_content = re.sub(think_pattern, '', content, flags=re.DOTALL).strip()
            return reasoning, clean_content

        return None, content

    async def process_simple_query(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Process a query without streaming (for sync API).

        Returns:
            Dict with full response
        """
        result = {
            "message": "",
            "tool_calls": [],
            "errors": []
        }

        async for chunk in self.process_message(message, history):
            chunk_type = chunk.get("type")

            if chunk_type == "content":
                result["message"] += chunk.get("content", "")
            elif chunk_type == "tool_call":
                result["tool_calls"].append({
                    "tool": chunk.get("tool"),
                    "args": chunk.get("args")
                })
            elif chunk_type == "tool_result":
                # Update the last tool call with result
                if result["tool_calls"]:
                    result["tool_calls"][-1]["result"] = chunk.get("result")
            elif chunk_type == "error":
                result["errors"].append(chunk.get("error"))

        return result

    async def close(self):
        """Clean up resources."""
        await self.tool_executor.close()
