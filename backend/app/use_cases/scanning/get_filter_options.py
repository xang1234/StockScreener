"""GetFilterOptionsUseCase — retrieve categorical filter values for a scan.

This use case owns the business rules for retrieving filter dropdown options:
  1. Verify the scan exists (raise EntityNotFoundError if not)
  2. If bound to a feature run → query the feature store
  3. Otherwise → fall back to scan_results table
  4. Return FilterOptions

The use case depends ONLY on domain ports — never on SQLAlchemy,
FastAPI, or any other infrastructure.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.domain.common.uow import UnitOfWork
from app.domain.scanning.models import FilterOptions

from ._resolve import resolve_scan

logger = logging.getLogger(__name__)


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
            scan, run_id = resolve_scan(uow, query.scan_id)

            if run_id:
                logger.info(
                    "Scan %s: querying filter options from feature_store (run_id=%d)",
                    query.scan_id,
                    run_id,
                )
                options = uow.feature_store.get_filter_options_for_run(run_id)
            else:
                logger.info(
                    "Scan %s: reading filter options from scan_results (no feature run)",
                    query.scan_id,
                )
                options = uow.scan_results.get_filter_options(query.scan_id)

        return GetFilterOptionsResult(options=options)
