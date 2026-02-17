"""Publish-readiness evaluation for feature store runs.

Pure policy function that decides whether a feature run may be
promoted to PUBLISHED.  No I/O, no side effects.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .models import DQSeverity, RunStatus
from .quality import DQResult


# ---------------------------------------------------------------------------
# Publish Decision Value Object
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PublishDecision:
    """Result of evaluating whether a run is ready for publishing."""

    allowed: bool
    blocking_checks: tuple[DQResult, ...]  # empty if allowed
    warnings: tuple[DQResult, ...]  # non-blocking failures

    @property
    def reason(self) -> str:
        if self.allowed:
            return "All critical checks passed"
        names = ", ".join(r.check_name for r in self.blocking_checks)
        return f"Blocked by: {names}"


# ---------------------------------------------------------------------------
# Policy Function
# ---------------------------------------------------------------------------


def evaluate_publish_readiness(
    status: RunStatus,
    dq_results: Sequence[DQResult],
) -> PublishDecision:
    """Evaluate whether a run is ready for publishing.

    Only COMPLETED runs can be published.  CRITICAL DQ failures block.
    Returns a PublishDecision with blocking_checks and warnings separated.
    """
    if status != RunStatus.COMPLETED:
        return PublishDecision(
            allowed=False,
            blocking_checks=(),
            warnings=(),
        )

    blocking = tuple(
        r
        for r in dq_results
        if r.severity == DQSeverity.CRITICAL and not r.passed
    )
    warnings = tuple(
        r
        for r in dq_results
        if r.severity == DQSeverity.WARNING and not r.passed
    )

    return PublishDecision(
        allowed=len(blocking) == 0,
        blocking_checks=blocking,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "PublishDecision",
    "evaluate_publish_readiness",
]
