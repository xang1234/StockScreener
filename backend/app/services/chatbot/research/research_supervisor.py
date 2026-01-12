"""
Research Supervisor - Manages parallel research units with semaphore control.
"""
import asyncio
import logging
from typing import Dict, Any, List, AsyncGenerator, Optional

from sqlalchemy.orm import Session

from .config import research_settings
from .models import SubQuestion, ResearchUnitResult, SourceNote
from .research_unit import ResearchUnit

logger = logging.getLogger(__name__)


class ResearchSupervisor:
    """Coordinates parallel execution of research units."""

    def __init__(self, db: Session):
        self.db = db
        self.semaphore = asyncio.Semaphore(
            research_settings.deep_research_max_concurrent_units
        )

    async def run_units(
        self,
        sub_questions: List[SubQuestion],
        max_tool_calls: Optional[int] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Run research units in parallel with semaphore control.

        Yields progress events and final results.

        Args:
            sub_questions: List of sub-questions to research
            max_tool_calls: Optional override for max tool calls per unit (for follow-up research)

        Yields:
            Progress events and results
        """
        logger.info(f"Starting {len(sub_questions)} research units (max concurrent: {research_settings.deep_research_max_concurrent_units})")

        # Create tasks for all units
        tasks = []
        result_queues = []

        for i, sq in enumerate(sub_questions):
            queue = asyncio.Queue()
            result_queues.append(queue)
            task = asyncio.create_task(
                self._run_unit_with_semaphore(sq, i, queue, max_tool_calls)
            )
            tasks.append(task)

        # Yield initial status
        yield {
            "type": "research_progress",
            "phase": "researching",
            "total_units": len(sub_questions),
            "started": len(sub_questions),
            "message": f"Starting {len(sub_questions)} parallel research units"
        }

        # Collect results and yield progress events
        completed = 0
        all_results: List[ResearchUnitResult] = []

        # Process events from all queues concurrently
        while completed < len(sub_questions):
            # Check each queue for events
            for i, queue in enumerate(result_queues):
                try:
                    while True:
                        event = queue.get_nowait()

                        if event.get("type") == "unit_complete":
                            completed += 1
                            result = event.get("result")
                            if result:
                                all_results.append(result)

                            yield {
                                "type": "research_progress",
                                "phase": "researching",
                                "unit": i,
                                "total_units": len(sub_questions),
                                "completed": completed,
                                "status": "complete",
                                "notes_count": len(result.notes) if result else 0,
                                "message": f"Unit {i+1}/{len(sub_questions)} complete"
                            }
                        else:
                            # Pass through progress events
                            yield event

                except asyncio.QueueEmpty:
                    continue

            # Small delay to avoid busy-waiting
            await asyncio.sleep(0.1)

        # Wait for all tasks to complete (they should already be done)
        await asyncio.gather(*tasks, return_exceptions=True)

        # Yield final results summary
        total_notes = sum(len(r.notes) for r in all_results)
        total_tool_calls = sum(r.tool_calls_made for r in all_results)

        yield {
            "type": "research_complete",
            "phase": "researching",
            "total_units": len(sub_questions),
            "completed_units": completed,
            "total_notes": total_notes,
            "total_tool_calls": total_tool_calls,
            "results": all_results
        }

    async def _run_unit_with_semaphore(
        self,
        sub_question: SubQuestion,
        unit_index: int,
        queue: asyncio.Queue,
        max_tool_calls: Optional[int] = None
    ):
        """Run a single research unit with semaphore control."""
        async with self.semaphore:
            logger.info(f"Unit {unit_index} starting: {sub_question.question[:50]}...")

            await queue.put({
                "type": "research_unit_start",
                "unit": unit_index,
                "question": sub_question.question
            })

            try:
                unit = ResearchUnit(self.db, sub_question, unit_index, max_tool_calls)

                # Collect events and get final result
                result = None
                async for event in unit.execute():
                    if isinstance(event, ResearchUnitResult):
                        result = event
                    else:
                        await queue.put(event)

                # If no result returned via generator, create one
                if result is None:
                    result = ResearchUnitResult(
                        sub_question=sub_question.question,
                        notes=unit.notes,
                        iterations=0,
                        completed=len(unit.notes) > 0,
                        tool_calls_made=unit.tool_calls_count
                    )

                logger.info(f"Unit {unit_index} completed: {len(result.notes)} notes")

                await queue.put({
                    "type": "unit_complete",
                    "unit": unit_index,
                    "result": result
                })

            except Exception as e:
                logger.error(f"Unit {unit_index} failed: {e}", exc_info=True)

                await queue.put({
                    "type": "unit_complete",
                    "unit": unit_index,
                    "result": ResearchUnitResult(
                        sub_question=sub_question.question,
                        notes=[],
                        iterations=0,
                        completed=False,
                        error=str(e),
                        tool_calls_made=0
                    )
                })

    def collect_all_notes(self, results: List[ResearchUnitResult]) -> List[SourceNote]:
        """Collect all notes from research results."""
        all_notes = []
        for result in results:
            all_notes.extend(result.notes)
        return all_notes

    def create_source_index(self, notes: List[SourceNote]) -> List[Dict[str, Any]]:
        """Create a numbered source index from notes, deduplicating by URL."""
        seen_urls = set()
        source_index = []

        for note in notes:
            if note.source_url not in seen_urls:
                seen_urls.add(note.source_url)
                source_index.append({
                    "index": str(len(source_index) + 1),
                    "title": note.source_title,
                    "url": note.source_url,
                    "type": note.source_type
                })

        return source_index
