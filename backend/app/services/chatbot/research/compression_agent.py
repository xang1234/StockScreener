"""
Compression Agent - Consolidates findings from multiple research units.
"""
import json
import logging
from typing import Dict, Any, List

from ....config import settings
from ....services.llm import LLMService, LLMError, LLMRateLimitError, LLMContextWindowError
from .config import research_settings
from .models import SourceNote, CompressedFindings, ResearchUnitResult
from .prompts import COMPRESSION_AGENT_SYSTEM_PROMPT, COMPRESSION_AGENT_USER_PROMPT

logger = logging.getLogger(__name__)


class CompressionAgent:
    """Consolidates and compresses research findings."""

    def __init__(self):
        self.llm = LLMService(use_case="compression")

    async def compress(
        self,
        main_question: str,
        unit_results: List[ResearchUnitResult],
        source_index: List[Dict[str, Any]]
    ) -> CompressedFindings:
        """
        Compress findings from all research units into a coherent summary.

        Args:
            main_question: The original research question
            unit_results: Results from all research units
            source_index: Numbered source index for citations

        Returns:
            CompressedFindings with consolidated key findings
        """
        # Format research notes for the prompt
        research_notes = self._format_research_notes(unit_results, source_index)

        user_prompt = COMPRESSION_AGENT_USER_PROMPT.format(
            main_question=main_question,
            num_units=len(unit_results),
            research_notes=research_notes
        )

        try:
            # Call LLM with automatic fallbacks
            response = await self.llm.completion(
                messages=[
                    {"role": "system", "content": COMPRESSION_AGENT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=research_settings.deep_research_notes_max_tokens,
                response_format={"type": "json_object"},
                num_retries=research_settings.groq_max_retries,
            )

            content = LLMService.extract_content(response)
            data = json.loads(content)

            # Normalize source_summary to ensure indices are strings (LLM may return integers)
            raw_source_summary = data.get("source_summary", source_index)
            normalized_source_summary = []
            for s in raw_source_summary:
                normalized_source_summary.append({
                    "index": str(s.get("index", "?")),
                    "title": str(s.get("title", "")),
                    "url": str(s.get("url", "")),
                    "type": str(s.get("type", "web"))
                })

            # Parse the compressed findings
            compressed = CompressedFindings(
                main_question=main_question,
                key_findings=data.get("key_findings", []),
                supporting_evidence=data.get("supporting_evidence", []),
                gaps_identified=data.get("gaps_identified", []),
                source_summary=normalized_source_summary,
                total_sources=len(source_index)
            )

            logger.info(f"Compressed {len(unit_results)} units into {len(compressed.key_findings)} key findings")
            return compressed

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse compression JSON: {e}")
            return self._create_fallback_compression(main_question, unit_results, source_index)

        except LLMContextWindowError as e:
            logger.warning(f"Compression request too large: {e}")
            return self._create_fallback_compression(main_question, unit_results, source_index)

        except LLMRateLimitError as e:
            logger.error(f"Compression rate limit exhausted: {e}")
            return self._create_fallback_compression(main_question, unit_results, source_index)

        except LLMError as e:
            logger.error(f"Compression LLM error: {e}")
            return self._create_fallback_compression(main_question, unit_results, source_index)

        except Exception as e:
            logger.error(f"Compression agent error: {e}", exc_info=True)
            return self._create_fallback_compression(main_question, unit_results, source_index)

    def _format_research_notes(
        self,
        unit_results: List[ResearchUnitResult],
        source_index: List[Dict[str, Any]]
    ) -> str:
        """Format research notes for the compression prompt."""
        # Create URL to index mapping
        url_to_index = {s["url"]: s["index"] for s in source_index}

        formatted_parts = []

        for i, result in enumerate(unit_results):
            formatted_parts.append(f"\n### Unit {i+1}: {result.sub_question}\n")

            if result.error:
                formatted_parts.append(f"Error: {result.error}\n")
                continue

            for note in result.notes:
                source_num = url_to_index.get(note.source_url, "?")
                formatted_parts.append(f"\n**Source [{source_num}]: {note.source_title}**")
                formatted_parts.append(f"Summary: {note.content_summary}")

                if note.key_facts:
                    formatted_parts.append("Key Facts:")
                    for fact in note.key_facts:
                        formatted_parts.append(f"  - {fact}")

        return "\n".join(formatted_parts)

    def _create_fallback_compression(
        self,
        main_question: str,
        unit_results: List[ResearchUnitResult],
        source_index: List[Dict[str, Any]]
    ) -> CompressedFindings:
        """Create a basic fallback compression when LLM fails."""
        # Extract all key facts from notes
        all_facts = []
        for result in unit_results:
            for note in result.notes:
                all_facts.extend(note.key_facts)

        # Deduplicate and limit
        unique_facts = list(set(all_facts))[:10]

        # Ensure source_index uses string indices (for pydantic model compatibility)
        normalized_source_index = []
        for s in source_index:
            normalized_source_index.append({
                "index": str(s.get("index", "?")),
                "title": s.get("title", ""),
                "url": s.get("url", ""),
                "type": s.get("type", "web")
            })

        return CompressedFindings(
            main_question=main_question,
            key_findings=unique_facts if unique_facts else ["Unable to extract key findings"],
            supporting_evidence=[],
            gaps_identified=["Compression failed - raw notes used"],
            source_summary=normalized_source_index,
            total_sources=len(source_index)
        )

    def format_for_report(self, compressed: CompressedFindings) -> str:
        """Format compressed findings for the report writer."""
        parts = []

        parts.append(f"## Key Findings\n")
        for i, finding in enumerate(compressed.key_findings, 1):
            parts.append(f"{i}. {finding}")

        if compressed.supporting_evidence:
            parts.append(f"\n## Supporting Evidence\n")
            for evidence in compressed.supporting_evidence:
                finding = evidence.get("finding", "")
                sources = evidence.get("sources", [])
                confidence = evidence.get("confidence", "medium")
                source_refs = "".join([f"[{s}]" for s in sources])
                parts.append(f"- {finding} {source_refs} ({confidence} confidence)")

        if compressed.gaps_identified:
            parts.append(f"\n## Information Gaps\n")
            for gap in compressed.gaps_identified:
                parts.append(f"- {gap}")

        return "\n".join(parts)
