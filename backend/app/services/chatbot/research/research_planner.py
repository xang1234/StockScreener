"""
Research Planner - Creates research outline with sub-questions.
"""
import json
import logging
from typing import Dict, Any, List, Optional

from ....config import settings
from ...llm import LLMService, LLMError, LLMRateLimitError, LLMContextWindowError
from .config import research_settings
from .models import ResearchOutline, SubQuestion
from .prompts import RESEARCH_PLANNER_SYSTEM_PROMPT, RESEARCH_PLANNER_USER_PROMPT

logger = logging.getLogger(__name__)


class ResearchPlanner:
    """Creates structured research plans from user queries."""

    def __init__(self):
        self.llm = LLMService(use_case="research")

    async def create_plan(
        self,
        query: str,
        history: Optional[List[Dict[str, str]]] = None
    ) -> ResearchOutline:
        """
        Create a research plan for the given query.

        Args:
            query: User's research question
            history: Previous conversation messages for context

        Returns:
            ResearchOutline with sub-questions and strategy
        """
        # Format history context
        history_context = "None"
        if history:
            history_context = "\n".join([
                f"{msg['role']}: {msg['content'][:200]}..."
                if len(msg.get('content', '')) > 200
                else f"{msg['role']}: {msg.get('content', '')}"
                for msg in history[-5:]  # Last 5 messages
            ])

        # Build prompt
        user_prompt = RESEARCH_PLANNER_USER_PROMPT.format(
            query=query,
            history_context=history_context
        )

        try:
            # Call LLM with automatic fallbacks
            response = await self.llm.completion(
                messages=[
                    {"role": "system", "content": RESEARCH_PLANNER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=2000,
                response_format={"type": "json_object"},
                num_retries=research_settings.groq_max_retries,
            )

            content = LLMService.extract_content(response)
            plan_data = json.loads(content)

            # Parse sub-questions
            sub_questions = []
            for sq_data in plan_data.get("sub_questions", []):
                sq = SubQuestion(
                    question=sq_data.get("question", ""),
                    search_queries=sq_data.get("search_queries", []),
                    priority=sq_data.get("priority", 1),
                    rationale=sq_data.get("rationale")
                )
                sub_questions.append(sq)

            # Limit number of sub-questions
            if len(sub_questions) > research_settings.research_max_sub_questions:
                sub_questions = sub_questions[:research_settings.research_max_sub_questions]

            # Ensure minimum sub-questions
            if len(sub_questions) < research_settings.research_min_sub_questions:
                # Add a general research sub-question
                sub_questions.append(SubQuestion(
                    question=f"What are the key facts about: {query}",
                    search_queries=[query],
                    priority=2,
                    rationale="General background research"
                ))

            # Sort by priority
            sub_questions.sort(key=lambda x: x.priority)

            outline = ResearchOutline(
                main_question=plan_data.get("main_question", query),
                sub_questions=sub_questions,
                research_strategy=plan_data.get("research_strategy", ""),
                expected_sources=plan_data.get("expected_sources", ["web", "news"])
            )

            logger.info(f"Created research plan with {len(sub_questions)} sub-questions")
            return outline

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse planner JSON response: {e}")
            # Return a fallback plan
            return self._create_fallback_plan(query)

        except LLMContextWindowError as e:
            logger.warning(f"Research planner request too large: {e}")
            return self._create_fallback_plan(query)

        except LLMRateLimitError as e:
            logger.error(f"Research planner rate limit exhausted: {e}")
            return self._create_fallback_plan(query)

        except LLMError as e:
            logger.error(f"Research planner LLM error: {e}")
            return self._create_fallback_plan(query)

        except Exception as e:
            logger.error(f"Research planner error: {e}", exc_info=True)
            return self._create_fallback_plan(query)

    def _create_fallback_plan(self, query: str) -> ResearchOutline:
        """Create a basic fallback plan when LLM fails."""
        return ResearchOutline(
            main_question=query,
            sub_questions=[
                SubQuestion(
                    question=query,
                    search_queries=[query, f"{query} latest news", f"{query} analysis"],
                    priority=1,
                    rationale="Main research question"
                ),
                SubQuestion(
                    question=f"Recent developments related to: {query}",
                    search_queries=[f"{query} recent", f"{query} 2024"],
                    priority=2,
                    rationale="Recent context and updates"
                )
            ],
            research_strategy="Direct search with news and web sources",
            expected_sources=["web", "news"]
        )
