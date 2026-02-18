"""ListFeatureRunsUseCase — list feature runs with row counts and status.

Provides a paginated, filterable listing of feature runs for
monitoring/admin dashboards.  Single SQL query, no N+1.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from app.domain.common.errors import ValidationError
from app.domain.common.uow import UnitOfWork
from app.domain.feature_store.models import RunStats, RunStatus


# ── Query (input) ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class ListRunsQuery:
    """Immutable value object describing the list-runs request."""

    status: str | None = None  # filter by RunStatus value
    date_from: date | None = None  # inclusive
    date_to: date | None = None  # inclusive
    limit: int = 50

    def __post_init__(self) -> None:
        if not 1 <= self.limit <= 200:
            raise ValidationError("limit must be between 1 and 200")
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValidationError("date_from must be <= date_to")


# ── Result (output) ────────────────────────────────────────────────────


@dataclass(frozen=True)
class FeatureRunSummary:
    """Summary row for a single feature run."""

    id: int
    as_of_date: date
    run_type: str
    status: str
    created_at: datetime
    completed_at: datetime | None
    published_at: datetime | None
    row_count: int
    is_latest_published: bool
    stats: RunStats | None
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ListRunsResult:
    """What the use case returns to the caller."""

    runs: tuple[FeatureRunSummary, ...]


# ── Use Case ───────────────────────────────────────────────────────────


class ListFeatureRunsUseCase:
    """List feature runs with aggregate row counts."""

    def execute(self, uow: UnitOfWork, query: ListRunsQuery) -> ListRunsResult:
        with uow:
            status_enum = RunStatus(query.status) if query.status else None
            rows = uow.feature_runs.list_runs_with_counts(
                status=status_enum,
                date_from=query.date_from,
                date_to=query.date_to,
                limit=query.limit,
            )
            summaries = tuple(
                FeatureRunSummary(
                    id=run.id,
                    as_of_date=run.as_of_date,
                    run_type=run.run_type.value,
                    status=run.status.value,
                    created_at=run.created_at,
                    completed_at=run.completed_at,
                    published_at=run.published_at,
                    row_count=row_count,
                    is_latest_published=is_latest,
                    stats=run.stats,
                    warnings=run.warnings,
                )
                for run, row_count, is_latest in rows
            )
        return ListRunsResult(runs=summaries)
