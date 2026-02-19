"""GetScanResultsUseCase — paginated, filtered, sorted query of scan results.

This use case owns the business rules for retrieving scan results:
  1. Verify the scan exists (raise EntityNotFoundError if not)
  2. Verify the scan is bound to a feature run
  3. Query the feature store for pre-computed results
  4. Return a ResultPage (source-agnostic)

The use case depends ONLY on domain ports — never on SQLAlchemy,
FastAPI, or any other infrastructure.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.domain.common.errors import EntityNotFoundError
from app.domain.common.uow import UnitOfWork
from app.domain.scanning.filter_spec import FilterSpec, QuerySpec
from app.domain.scanning.models import ResultPage

logger = logging.getLogger(__name__)


# ── Query (input) ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class GetScanResultsQuery:
    """Immutable value object describing what the caller wants to read."""

    scan_id: str
    query_spec: QuerySpec = field(default_factory=QuerySpec)
    include_sparklines: bool = True
    passes_only: bool = False


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

            if not scan.feature_run_id:
                raise EntityNotFoundError(
                    "FeatureRun", f"scan {query.scan_id} has no bound feature run"
                )

            # Apply passes_only business rule: augment filters to
            # include only "Strong Buy" and "Buy" ratings.
            query_spec = query.query_spec
            if query.passes_only:
                # Build a fresh FilterSpec to avoid mutating the caller's object.
                augmented = FilterSpec(
                    range_filters=list(query_spec.filters.range_filters),
                    categorical_filters=list(query_spec.filters.categorical_filters),
                    boolean_filters=list(query_spec.filters.boolean_filters),
                    text_searches=list(query_spec.filters.text_searches),
                )
                augmented.add_categorical("rating", ("Strong Buy", "Buy"))
                query_spec = QuerySpec(
                    filters=augmented,
                    sort=query_spec.sort,
                    page=query_spec.page,
                )

            logger.info(
                "Scan %s: querying feature_store (run_id=%d)",
                query.scan_id,
                scan.feature_run_id,
            )
            result_page = uow.feature_store.query_run_as_scan_results(
                scan.feature_run_id,
                query_spec,
                include_sparklines=query.include_sparklines,
            )

        return GetScanResultsResult(page=result_page)
