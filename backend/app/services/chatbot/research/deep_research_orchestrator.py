"""
Deep Research Orchestrator - Main entry point for research mode.
Coordinates planning, parallel research, compression, and report writing.
"""
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, AsyncGenerator

from sqlalchemy.orm import Session

from ....config import settings
from ....models.chatbot import Conversation, Message
from ....services.llm import LLMService, LLMError
from .config import research_settings
from .models import (
    ResearchState,
    ResearchPhase,
    ResearchOutline,
    ResearchUnitResult,
    CompressedFindings,
    SubQuestion,
)
from .prompts import FOLLOW_UP_QUESTION_SYSTEM_PROMPT, FOLLOW_UP_QUESTION_USER_PROMPT
from .research_planner import ResearchPlanner
from .research_supervisor import ResearchSupervisor
from .compression_agent import CompressionAgent
from .report_writer import ReportWriter

logger = logging.getLogger(__name__)


class DeepResearchOrchestrator:
    """
    Orchestrates the deep research pipeline.

    Pipeline:
    1. Planning - Create research outline with sub-questions
    2. Researching - Run parallel research units
    3. Compressing - Consolidate findings
    4. Writing - Generate final report with citations
    """

    def __init__(self, db: Session):
        self.db = db
        self.planner = ResearchPlanner()
        self.supervisor = ResearchSupervisor(db)
        self.compressor = CompressionAgent()
        self.writer = ReportWriter()
        # LLM service for follow-up question generation
        self.llm = LLMService(use_case="research")

    async def research(
        self,
        conversation_id: str,
        query: str,
        history: Optional[List[Dict[str, str]]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute the full research pipeline.

        Args:
            conversation_id: Parent conversation ID
            query: User's research question
            history: Previous conversation messages for context

        Yields:
            Stream chunks with progress and results
        """
        # Initialize state
        state = ResearchState(
            conversation_id=conversation_id,
            query=query,
            phase=ResearchPhase.PLANNING
        )

        # Save user message to database
        self._save_user_message(conversation_id, query)

        try:
            # ================================================================
            # Phase 1: Planning
            # ================================================================
            yield {
                "type": "research_phase",
                "phase": "planning",
                "message": "Creating research plan..."
            }

            logger.info(f"Starting research: {query[:50]}...")

            outline = await self.planner.create_plan(query, history)
            state.outline = outline

            yield {
                "type": "thinking",
                "content": f"Research strategy: {outline.research_strategy}\n\nSub-questions:\n" +
                          "\n".join([f"- {sq.question}" for sq in outline.sub_questions])
            }

            yield {
                "type": "research_plan",
                "phase": "planning",
                "main_question": outline.main_question,
                "sub_questions": [sq.question for sq in outline.sub_questions],
                "expected_sources": outline.expected_sources
            }

            # ================================================================
            # Phase 2: Parallel Research
            # ================================================================
            state.phase = ResearchPhase.RESEARCHING
            yield {
                "type": "research_phase",
                "phase": "researching",
                "message": f"Researching {len(outline.sub_questions)} questions in parallel..."
            }

            unit_results: List[ResearchUnitResult] = []
            all_notes = []

            async for event in self.supervisor.run_units(outline.sub_questions):
                # Pass through progress events
                if event.get("type") == "research_complete":
                    unit_results = event.get("results", [])
                    state.unit_results = unit_results
                    state.total_tool_calls = event.get("total_tool_calls", 0)

                    # Collect all notes
                    all_notes = self.supervisor.collect_all_notes(unit_results)

                    yield {
                        "type": "research_progress",
                        "phase": "researching",
                        "status": "complete",
                        "total_notes": len(all_notes),
                        "total_tool_calls": state.total_tool_calls
                    }
                else:
                    yield event

            # Create source index
            source_index = self.supervisor.create_source_index(all_notes)
            state.all_references = source_index
            state.total_sources = len(source_index)

            # ================================================================
            # Phase 3: Compression
            # ================================================================
            state.phase = ResearchPhase.COMPRESSING
            yield {
                "type": "research_phase",
                "phase": "compressing",
                "message": "Consolidating research findings..."
            }

            compressed = await self.compressor.compress(
                query, unit_results, source_index
            )
            state.compressed_findings = compressed

            yield {
                "type": "thinking",
                "content": f"Key findings identified: {len(compressed.key_findings)}\n" +
                          "Consolidating from " + str(len(source_index)) + " sources..."
            }

            # ================================================================
            # Phase 3.5: Follow-Up Research (if gaps identified)
            # ================================================================
            if (
                research_settings.follow_up_enabled
                and compressed.gaps_identified
                and len(compressed.gaps_identified) > 0
            ):
                state.phase = ResearchPhase.FOLLOW_UP
                yield {
                    "type": "research_phase",
                    "phase": "follow_up",
                    "message": f"Investigating {len(compressed.gaps_identified)} identified gaps..."
                }

                # Generate follow-up questions from gaps
                follow_up_questions = await self._generate_follow_up_questions(
                    query, compressed.gaps_identified, compressed.key_findings
                )

                if follow_up_questions:
                    yield {
                        "type": "thinking",
                        "content": f"Follow-up questions:\n" +
                                  "\n".join([f"- {sq.question}" for sq in follow_up_questions])
                    }

                    # Run focused research on follow-up questions
                    follow_up_results: List[ResearchUnitResult] = []
                    async for event in self.supervisor.run_units(
                        follow_up_questions,
                        max_tool_calls=research_settings.follow_up_max_tool_calls_per_unit
                    ):
                        if event.get("type") == "research_complete":
                            follow_up_results = event.get("results", [])
                            follow_up_notes = self.supervisor.collect_all_notes(follow_up_results)
                            all_notes.extend(follow_up_notes)
                        else:
                            yield event

                    # Update source index with new sources
                    source_index = self.supervisor.create_source_index(all_notes)
                    state.all_references = source_index
                    state.total_sources = len(source_index)

                    # Re-compress with new findings
                    all_unit_results = unit_results + follow_up_results
                    compressed = await self.compressor.compress(
                        query, all_unit_results, source_index
                    )
                    state.compressed_findings = compressed

                    yield {
                        "type": "thinking",
                        "content": f"Follow-up research complete. Now {len(compressed.key_findings)} key findings from {len(source_index)} sources."
                    }

            # ================================================================
            # Phase 4: Report Writing
            # ================================================================
            state.phase = ResearchPhase.WRITING
            yield {
                "type": "research_phase",
                "phase": "writing",
                "message": "Writing research report..."
            }

            full_report = ""
            async for chunk in self.writer.write_report(query, compressed, source_index):
                full_report += chunk
                yield {
                    "type": "content",
                    "content": chunk
                }

            state.final_report = full_report
            state.phase = ResearchPhase.DONE
            state.completed_at = datetime.utcnow()

            # ================================================================
            # Completion
            # ================================================================
            # Format references for the done event
            formatted_refs = []
            for source in source_index:
                formatted_refs.append({
                    "reference_number": int(source["index"]),  # Convert to int for frontend Map lookup
                    "type": source.get("type", "web"),
                    "title": source.get("title", "Unknown"),
                    "url": source.get("url", ""),
                })

            # Save assistant message with full report
            self._save_assistant_message(
                conversation_id=conversation_id,
                content=full_report,
                source_references=formatted_refs
            )

            # Update conversation metadata
            self._update_conversation(conversation_id, query)

            yield {
                "type": "done",
                "references": formatted_refs,
                "stats": {
                    "total_sources": state.total_sources,
                    "total_tool_calls": state.total_tool_calls,
                    "sub_questions_researched": len(unit_results),
                    "key_findings": len(compressed.key_findings),
                    "research_duration_seconds": (
                        (state.completed_at - state.started_at).total_seconds()
                        if state.completed_at else 0
                    )
                }
            }

            logger.info(
                f"Research complete: {state.total_sources} sources, "
                f"{state.total_tool_calls} tool calls"
            )

        except Exception as e:
            logger.error(f"Research orchestrator error: {e}", exc_info=True)
            yield {
                "type": "error",
                "error": str(e)
            }

    async def research_simple(
        self,
        conversation_id: str,
        query: str,
        history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Execute research and return complete result (non-streaming).

        Returns:
            Dict with complete research result
        """
        result = {
            "report": "",
            "references": [],
            "stats": {}
        }

        async for chunk in self.research(conversation_id, query, history):
            chunk_type = chunk.get("type")

            if chunk_type == "content":
                result["report"] += chunk.get("content", "")
            elif chunk_type == "done":
                result["references"] = chunk.get("references", [])
                result["stats"] = chunk.get("stats", {})
            elif chunk_type == "error":
                result["error"] = chunk.get("error")

        return result

    def _save_user_message(self, conversation_id: str, content: str) -> Message:
        """Save user message to database."""
        # Ensure conversation exists
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

        message = Message(
            conversation_id=conversation_id,
            role="user",
            content=content
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def _save_assistant_message(
        self,
        conversation_id: str,
        content: str,
        source_references: List[Dict] = None
    ) -> Message:
        """Save assistant message to database."""
        message = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=content,
            agent_type="deep_research",
            source_references=source_references
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

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
            if not conversation.title or conversation.title == "New Conversation":
                conversation.title = first_message[:50] + "..." if len(first_message) > 50 else first_message
            self.db.commit()

    async def _generate_follow_up_questions(
        self,
        original_query: str,
        gaps: List[str],
        key_findings: List[str]
    ) -> List[SubQuestion]:
        """
        Generate focused follow-up questions from identified gaps.

        Args:
            original_query: The original research question
            gaps: List of gaps identified during compression
            key_findings: List of key findings already gathered

        Returns:
            List of SubQuestion objects for follow-up research
        """
        # Limit gaps to most important ones
        limited_gaps = gaps[:research_settings.follow_up_max_questions + 1]

        # Format the prompts
        gaps_text = "\n".join([f"- {gap}" for gap in limited_gaps])
        findings_text = "\n".join([f"- {finding}" for finding in key_findings[:10]])

        user_prompt = FOLLOW_UP_QUESTION_USER_PROMPT.format(
            main_question=original_query,
            gaps=gaps_text,
            key_findings=findings_text
        )

        try:
            # Call LLM to generate follow-up questions
            response = await self.llm.completion(
                messages=[
                    {"role": "system", "content": FOLLOW_UP_QUESTION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=1000,
                response_format={"type": "json_object"},
                num_retries=2,
            )

            content = LLMService.extract_content(response)
            result = json.loads(content)

            follow_up_questions = []
            for q in result.get("follow_up_questions", [])[:research_settings.follow_up_max_questions]:
                follow_up_questions.append(SubQuestion(
                    question=q.get("question", ""),
                    search_queries=q.get("search_queries", []),
                    priority=q.get("priority", 1),
                    rationale=q.get("rationale", "")
                ))

            logger.info(f"Generated {len(follow_up_questions)} follow-up questions from {len(gaps)} gaps")
            return follow_up_questions

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse follow-up questions response: {e}")
            return []
        except LLMError as e:
            logger.error(f"LLM error generating follow-up questions: {e}")
            return []
        except Exception as e:
            logger.error(f"Error generating follow-up questions: {e}")
            return []
