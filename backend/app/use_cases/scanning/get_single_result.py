"""GetSingleResultUseCase — retrieve a single scan result by symbol.

Business rules:
  1. Verify the scan exists (raise EntityNotFoundError if not)
  2. Normalise the symbol to uppercase (case-insensitive lookup)
  3. Route to the correct data source:
     - Bound scans (feature_run_id set) -> query feature store
     - Unbound scans (legacy) -> query scan_results table
  4. Raise EntityNotFoundError if the symbol is not in the scan

The use case depends ONLY on domain ports — never on SQLAlchemy,
FastAPI, or any other infrastructure.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.domain.common.errors import EntityNotFoundError
from app.domain.common.uow import UnitOfWork
from app.domain.scanning.models import ScanResultItemDomain

logger = logging.getLogger(__name__)


# ── Query (input) ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class GetSingleResultQuery:
    """Immutable value object describing the single-result lookup."""

    scan_id: str
    symbol: str

    def __post_init__(self) -> None:
        # Business rule: symbols are case-insensitive.
        object.__setattr__(self, "symbol", self.symbol.upper())


# ── Result (output) ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class GetSingleResultResult:
    """What the use case returns to the caller."""

    item: ScanResultItemDomain


# ── Use Case ────────────────────────────────────────────────────────────


class GetSingleResultUseCase:
    """Retrieve a single scan result by scan_id and symbol."""

    def execute(
        self, uow: UnitOfWork, query: GetSingleResultQuery
    ) -> GetSingleResultResult:
        with uow:
            scan = uow.scans.get_by_scan_id(query.scan_id)
            if scan is None:
                raise EntityNotFoundError("Scan", query.scan_id)

            if scan.feature_run_id:
                logger.info(
                    "Scan %s: routing single result to feature_store (run_id=%d)",
                    query.scan_id,
                    scan.feature_run_id,
                )
                try:
                    item = uow.feature_store.get_by_symbol_for_run(
                        scan.feature_run_id,
                        query.symbol,
                    )
                except EntityNotFoundError:
                    logger.warning(
                        "Feature run %d not found for scan %s, falling back to legacy",
                        scan.feature_run_id,
                        query.scan_id,
                    )
                    item = uow.scan_results.get_by_symbol(
                        scan_id=query.scan_id,
                        symbol=query.symbol,
                    )
            else:
                logger.debug(
                    "Scan %s: routing single result to legacy scan_results",
                    query.scan_id,
                )
                item = uow.scan_results.get_by_symbol(
                    scan_id=query.scan_id,
                    symbol=query.symbol,
                )

            if item is None:
                raise EntityNotFoundError("ScanResult", query.symbol)

        return GetSingleResultResult(item=item)
