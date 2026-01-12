"""
Agent Orchestrator for the multi-agent chatbot.
Uses native tool calling via ToolAgent for reliable data access.
"""
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List, AsyncGenerator

from sqlalchemy.orm import Session

from ...models.chatbot import Conversation, Message, AgentExecution
from .tool_agent import ToolAgent

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Orchestrates the chatbot using native tool calling."""

    def __init__(self, db: Session):
        self.db = db
        self.tool_agent = ToolAgent(db)

    async def process_message(
        self,
        conversation_id: str,
        message: str,
        enabled_tools: Optional[List[str]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process a user message through the tool-calling agent.

        Yields stream chunks for real-time updates:
        - {"type": "thinking", "content": "..."}
        - {"type": "tool_call", "tool": "...", "args": {...}}
        - {"type": "tool_result", "tool": "...", "result": {...}}
        - {"type": "content", "content": "..."}
        - {"type": "done", "message_id": ...}
        - {"type": "error", "error": "..."}

        Args:
            conversation_id: ID of the conversation
            message: User's message content
            enabled_tools: List of enabled tool names, or None for all tools

        Yields:
            Stream chunks with progress and results
        """
        try:
            # Get or create conversation
            conversation = self._get_or_create_conversation(conversation_id)

            # Save user message
            user_msg = self._save_message(
                conversation_id=conversation_id,
                role="user",
                content=message
            )

            # Get conversation history for context
            history = self._get_conversation_history(conversation_id, limit=10)

            # Track tool calls, thinking traces, and references for logging
            tool_calls_log = []
            thinking_traces_log = []
            references_log = []
            full_answer = ""

            # Process through the tool agent
            async for chunk in self.tool_agent.process_message(message, history, enabled_tools):
                chunk_type = chunk.get("type")

                if chunk_type == "thinking":
                    thinking_content = chunk.get("content", "")
                    thinking_traces_log.append({
                        "content": thinking_content,
                        "agent": "tool_agent"
                    })
                    yield {
                        "type": "thinking",
                        "agent": "tool_agent",
                        "content": thinking_content
                    }

                elif chunk_type == "tool_call":
                    tool_calls_log.append({
                        "tool": chunk.get("tool"),
                        "args": chunk.get("args")
                    })
                    yield {
                        "type": "tool_call",
                        "agent": "tool_agent",
                        "tool": chunk.get("tool"),
                        "params": chunk.get("args", {})
                    }

                elif chunk_type == "tool_result":
                    result = chunk.get("result")
                    # Update the last tool call with result
                    if tool_calls_log:
                        tool_calls_log[-1]["result"] = result

                    # Extract references WITH their assigned reference_numbers
                    # First check chunk-level references (preferred - has numbered refs)
                    if "references" in chunk:
                        for ref in chunk["references"]:
                            # Deduplicate by URL, preserve reference_number
                            if not any(r.get("url") == ref.get("url") for r in references_log):
                                references_log.append(ref)
                    # Then check result-level references as fallback
                    elif result and isinstance(result, dict) and "references" in result:
                        for ref in result["references"]:
                            # Deduplicate by URL, preserve reference_number
                            if not any(r.get("url") == ref.get("url") for r in references_log):
                                references_log.append(ref)

                    yield {
                        "type": "tool_result",
                        "agent": "tool_agent",
                        "tool": chunk.get("tool"),
                        "status": "success" if result else "empty",
                        "result": result
                    }

                elif chunk_type == "content":
                    content = chunk.get("content", "")
                    full_answer += content
                    yield {
                        "type": "content",
                        "agent": "tool_agent",
                        "content": content
                    }

                elif chunk_type == "error":
                    yield {
                        "type": "error",
                        "error": chunk.get("error")
                    }

            # Sort references by their assigned reference_number for consistent ordering
            if references_log:
                references_log.sort(key=lambda r: r.get("reference_number", 999))

            # Save assistant message
            assistant_msg = self._save_message(
                conversation_id=conversation_id,
                role="assistant",
                content=full_answer,
                agent_type="tool_agent",
                reasoning=json.dumps({
                    "tool_calls": tool_calls_log
                }, default=str),
                tool_calls=tool_calls_log if tool_calls_log else None,
                thinking_traces=thinking_traces_log if thinking_traces_log else None,
                source_references=references_log if references_log else None
            )

            # Update conversation
            self._update_conversation(conversation_id, message)

            yield {
                "type": "done",
                "message_id": assistant_msg.id,
                "conversation_id": conversation_id,
                "references": references_log if references_log else None
            }

        except Exception as e:
            logger.error(f"Error in orchestrator: {e}", exc_info=True)
            yield {
                "type": "error",
                "error": str(e)
            }

    async def process_simple_query(
        self,
        conversation_id: str,
        message: str
    ) -> Dict[str, Any]:
        """
        Process a simple query without streaming.
        Used for non-streaming API calls.

        Returns:
            Dict with the response
        """
        full_response = {
            "conversation_id": conversation_id,
            "message": "",
            "tool_calls": [],
            "references": [],
        }

        async for chunk in self.process_message(conversation_id, message):
            chunk_type = chunk.get("type")

            if chunk_type == "content":
                full_response["message"] += chunk.get("content", "")
            elif chunk_type == "tool_call":
                full_response["tool_calls"].append({
                    "tool": chunk.get("tool"),
                    "params": chunk.get("params")
                })
            elif chunk_type == "tool_result":
                # Update the last tool call with result
                if full_response["tool_calls"]:
                    full_response["tool_calls"][-1]["status"] = chunk.get("status")
                    full_response["tool_calls"][-1]["result"] = chunk.get("result")
            elif chunk_type == "done":
                full_response["message_id"] = chunk.get("message_id")
                # Collect references from the done chunk
                if chunk.get("references"):
                    full_response["references"] = chunk["references"]
            elif chunk_type == "error":
                full_response["error"] = chunk.get("error")

        return full_response

    def _get_or_create_conversation(self, conversation_id: str) -> Conversation:
        """Get existing conversation or create new one."""
        conversation = (
            self.db.query(Conversation)
            .filter(Conversation.conversation_id == conversation_id)
            .first()
        )

        if not conversation:
            conversation = Conversation(
                conversation_id=conversation_id,
                title="New Conversation",
                is_active=True,
                message_count=0
            )
            self.db.add(conversation)
            self.db.commit()
            self.db.refresh(conversation)

        return conversation

    def _save_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        agent_type: Optional[str] = None,
        tool_name: Optional[str] = None,
        tool_input: Optional[Dict] = None,
        tool_output: Optional[Dict] = None,
        reasoning: Optional[str] = None,
        tool_calls: Optional[List[Dict]] = None,
        thinking_traces: Optional[List[Dict]] = None,
        source_references: Optional[List[Dict]] = None
    ) -> Message:
        """Save a message to the database."""
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            agent_type=agent_type,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_output=tool_output,
            reasoning=reasoning,
            tool_calls=tool_calls,
            thinking_traces=thinking_traces,
            source_references=source_references
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def _get_conversation_history(
        self,
        conversation_id: str,
        limit: int = 10
    ) -> List[Dict[str, str]]:
        """Get recent conversation history."""
        messages = (
            self.db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .filter(Message.role.in_(["user", "assistant"]))
            .order_by(Message.created_at.desc())
            .limit(limit)
            .all()
        )

        # Return in chronological order
        return [
            {"role": msg.role, "content": msg.content}
            for msg in reversed(messages)
        ]

    def _update_conversation(self, conversation_id: str, first_message: str):
        """Update conversation metadata."""
        conversation = (
            self.db.query(Conversation)
            .filter(Conversation.conversation_id == conversation_id)
            .first()
        )

        if conversation:
            conversation.message_count = (
                self.db.query(Message)
                .filter(Message.conversation_id == conversation_id)
                .count()
            )

            # Set title from first message if not set
            if not conversation.title or conversation.title == "New Conversation":
                conversation.title = first_message[:50] + "..." if len(first_message) > 50 else first_message

            self.db.commit()

    async def close(self):
        """Clean up resources."""
        await self.tool_agent.close()


def create_conversation_id() -> str:
    """Create a new conversation ID."""
    return str(uuid.uuid4())
