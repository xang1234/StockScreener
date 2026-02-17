"""GetScanResultsUseCase — paginated, filtered, sorted query of scan results.

This use case owns the business rules for retrieving scan results:
  1. Verify the scan exists (raise EntityNotFoundError if not)
  2. Delegate to ScanResultRepository.query() with the QuerySpec
  3. Return a ResultPage

The use case depends ONLY on domain ports — never on SQLAlchemy,
FastAPI, or any other infrastructure.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.common.errors import EntityNotFoundError
from app.domain.common.uow import UnitOfWork
from app.domain.scanning.filter_spec import QuerySpec
from app.domain.scanning.models import ResultPage


# ── Query (input) ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class GetScanResultsQuery:
    """Immutable value object describing what the caller wants to read."""

    scan_id: str
    query_spec: QuerySpec = field(default_factory=QuerySpec)
    include_sparklines: bool = True


# ── Result (output) ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class GetScanResultsResult:
    """What the use case returns to the caller."""

    page: ResultPage


# ── Use Case ────────────────────────────────────────────────────────────


class GetScanResultsUseCase:
    """Retrieve a filtered, sorted, paginated page of scan results."""

    def execute(
        self, uow: UnitOfWork, query: GetScanResultsQuery
    ) -> GetScanResultsResult:
        with uow:
            # Verify scan exists
            scan = uow.scans.get_by_scan_id(query.scan_id)
            if scan is None:
                raise EntityNotFoundError("Scan", query.scan_id)

            # Delegate to repository
            result_page = uow.scan_results.query(
                scan_id=query.scan_id,
                spec=query.query_spec,
                include_sparklines=query.include_sparklines,
            )

        return GetScanResultsResult(page=result_page)
