"""GetFilterOptionsUseCase — retrieve categorical filter values for a scan.

This use case owns the business rules for retrieving filter dropdown options:
  1. Verify the scan exists (raise EntityNotFoundError if not)
  2. Delegate to ScanResultRepository.get_filter_options()
  3. Return FilterOptions

The use case depends ONLY on domain ports — never on SQLAlchemy,
FastAPI, or any other infrastructure.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.common.errors import EntityNotFoundError
from app.domain.common.uow import UnitOfWork
from app.domain.scanning.models import FilterOptions


# ── Query (input) ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class GetFilterOptionsQuery:
    """Immutable value object describing what the caller wants to read."""

    scan_id: str


# ── Result (output) ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class GetFilterOptionsResult:
    """What the use case returns to the caller."""

    options: FilterOptions


# ── Use Case ────────────────────────────────────────────────────────────


class GetFilterOptionsUseCase:
    """Retrieve categorical filter options for a scan's results."""

    def execute(
        self, uow: UnitOfWork, query: GetFilterOptionsQuery
    ) -> GetFilterOptionsResult:
        with uow:
            scan = uow.scans.get_by_scan_id(query.scan_id)
            if scan is None:
                raise EntityNotFoundError("Scan", query.scan_id)

            options = uow.scan_results.get_filter_options(
                scan_id=query.scan_id,
            )

        return GetFilterOptionsResult(options=options)
