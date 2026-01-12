"""
Report Writer - Generates final markdown report with citations.
"""
import logging
import re
from typing import Dict, Any, List, AsyncGenerator

from ....config import settings
from ....services.llm import LLMService, LLMError, LLMRateLimitError, LLMContextWindowError
from .config import research_settings
from .models import CompressedFindings
from .prompts import REPORT_WRITER_SYSTEM_PROMPT, REPORT_WRITER_USER_PROMPT

logger = logging.getLogger(__name__)


class ReportWriter:
    """Generates markdown reports with inline citations."""

    def __init__(self):
        self.llm = LLMService(use_case="report")

    def _strip_think_tags(self, content: str) -> str:
        """Remove <think>...</think> blocks from content."""
        return re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()

    async def write_report(
        self,
        main_question: str,
        compressed_findings: CompressedFindings,
        source_index: List[Dict[str, Any]]
    ) -> AsyncGenerator[str, None]:
        """
        Write the final research report with streaming.

        Args:
            main_question: The original research question
            compressed_findings: Consolidated research findings
            source_index: Numbered source index for citations

        Yields:
            Report text chunks
        """
        # Format compressed findings
        findings_text = self._format_findings(compressed_findings)

        # Format source index
        source_index_text = self._format_source_index(source_index)

        user_prompt = REPORT_WRITER_USER_PROMPT.format(
            main_question=main_question,
            compressed_findings=findings_text,
            source_index=source_index_text
        )

        try:
            # Collect full report from streaming response
            full_report = ""
            # Must await completion() first to get the async generator
            stream = await self.llm.completion(
                messages=[
                    {"role": "system", "content": REPORT_WRITER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.4,
                max_tokens=research_settings.deep_research_report_max_tokens,
                stream=True,
                num_retries=research_settings.groq_max_retries,
            )
            async for chunk in stream:
                if hasattr(chunk, 'choices') and chunk.choices:
                    delta = chunk.choices[0].delta
                    if hasattr(delta, 'content') and delta.content:
                        full_report += delta.content

            # Strip <think>...</think> blocks from the complete report
            cleaned_report = self._strip_think_tags(full_report)

            # Yield cleaned content in chunks for streaming effect
            chunk_size = 50
            for i in range(0, len(cleaned_report), chunk_size):
                yield cleaned_report[i:i+chunk_size]

            logger.info(f"Report written: {len(cleaned_report)} characters")

        except LLMContextWindowError as e:
            logger.warning(f"Report request too large: {e}")
            # Yield fallback report
            fallback = self._generate_fallback_report(
                main_question, compressed_findings, source_index
            )
            yield fallback

        except LLMRateLimitError as e:
            logger.error(f"Report writer rate limit exhausted: {e}")
            # Yield fallback report
            fallback = self._generate_fallback_report(
                main_question, compressed_findings, source_index
            )
            yield fallback

        except LLMError as e:
            logger.error(f"Report writer LLM error: {e}")
            # Yield fallback report
            fallback = self._generate_fallback_report(
                main_question, compressed_findings, source_index
            )
            yield fallback

        except Exception as e:
            logger.error(f"Report writer error: {e}", exc_info=True)
            # Yield fallback report
            fallback = self._generate_fallback_report(
                main_question, compressed_findings, source_index
            )
            yield fallback

    def _format_findings(self, compressed: CompressedFindings) -> str:
        """Format compressed findings for the prompt."""
        parts = []

        parts.append("### Key Findings")
        for i, finding in enumerate(compressed.key_findings, 1):
            parts.append(f"{i}. {finding}")

        if compressed.supporting_evidence:
            parts.append("\n### Evidence with Sources")
            for evidence in compressed.supporting_evidence:
                finding = evidence.get("finding", "")
                sources = evidence.get("sources", [])
                confidence = evidence.get("confidence", "")
                source_refs = ", ".join([f"[{s}]" for s in sources]) if sources else ""
                parts.append(f"- {finding} (Sources: {source_refs}, Confidence: {confidence})")

        if compressed.gaps_identified:
            parts.append("\n### Information Gaps")
            for gap in compressed.gaps_identified:
                parts.append(f"- {gap}")

        return "\n".join(parts)

    def _format_source_index(self, source_index: List[Dict[str, Any]]) -> str:
        """Format source index for the prompt."""
        lines = []
        for source in source_index:
            idx = source.get("index", "?")
            title = source.get("title", "Unknown")
            url = source.get("url", "")
            source_type = source.get("type", "web")
            lines.append(f"[{idx}] {title} ({source_type}) - {url}")
        return "\n".join(lines)

    def _generate_sources_section(self, source_index: List[Dict[str, Any]]) -> str:
        """Generate the sources section for the report."""
        if not source_index:
            return ""

        lines = ["\n\n---\n\n## Sources\n"]

        for source in source_index:
            idx = source.get("index", "?")
            title = source.get("title", "Unknown Source")
            url = source.get("url", "")

            if url:
                lines.append(f"{idx}. [{title}]({url})")
            else:
                lines.append(f"{idx}. {title}")

        return "\n".join(lines)

    def _generate_fallback_report(
        self,
        main_question: str,
        compressed: CompressedFindings,
        source_index: List[Dict[str, Any]]
    ) -> str:
        """Generate a basic fallback report when LLM fails."""
        parts = []

        parts.append(f"## Research Report: {main_question}\n")

        parts.append("### Summary\n")
        parts.append("This report summarizes findings from automated research.\n")

        if compressed.key_findings:
            parts.append("### Key Findings\n")
            for i, finding in enumerate(compressed.key_findings, 1):
                parts.append(f"{i}. {finding}")
            parts.append("")

        if compressed.gaps_identified:
            parts.append("### Notes\n")
            for gap in compressed.gaps_identified:
                parts.append(f"- {gap}")
            parts.append("")

        return "\n".join(parts)

    async def write_report_sync(
        self,
        main_question: str,
        compressed_findings: CompressedFindings,
        source_index: List[Dict[str, Any]]
    ) -> str:
        """
        Write the complete report without streaming.

        Returns:
            Complete report text
        """
        parts = []
        async for chunk in self.write_report(main_question, compressed_findings, source_index):
            parts.append(chunk)
        return "".join(parts)
