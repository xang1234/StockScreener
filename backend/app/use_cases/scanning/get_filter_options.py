"""GetFilterOptionsUseCase — retrieve categorical filter values for a scan.

This use case owns the business rules for retrieving filter dropdown options:
  1. Verify the scan exists (raise EntityNotFoundError if not)
  2. Verify the scan is bound to a feature run
  3. Query the feature store for filter options
  4. Return FilterOptions

The use case depends ONLY on domain ports — never on SQLAlchemy,
FastAPI, or any other infrastructure.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.domain.common.errors import EntityNotFoundError
from app.domain.common.uow import UnitOfWork
from app.domain.scanning.models import FilterOptions

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
            scan = uow.scans.get_by_scan_id(query.scan_id)
            if scan is None:
                raise EntityNotFoundError("Scan", query.scan_id)

            if not scan.feature_run_id:
                raise EntityNotFoundError(
                    "FeatureRun", f"scan {query.scan_id} has no bound feature run"
                )

            logger.info(
                "Scan %s: querying filter options from feature_store (run_id=%d)",
                query.scan_id,
                scan.feature_run_id,
            )
            options = uow.feature_store.get_filter_options_for_run(
                scan.feature_run_id,
            )

        return GetFilterOptionsResult(options=options)
