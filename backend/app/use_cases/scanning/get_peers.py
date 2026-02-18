"""GetPeersUseCase — retrieve peer stocks from the same industry or sector.

Business rules:
  1. Verify the scan exists (raise EntityNotFoundError if not)
  2. Route to the correct data source:
     - Bound scans (feature_run_id set) -> query feature store
     - Unbound scans (legacy) -> query scan_results table
  3. Look up the target symbol (raise EntityNotFoundError if not found)
  4. Read the group value from extended_fields based on peer_type
  5. If no group value, return empty result
  6. Delegate to the appropriate repo method (industry or sector)

Note: this endpoint makes TWO dependent calls (lookup target, then query
peers), so it uses a ``use_feature_store`` flag to ensure both calls
use the same data source.

The use case depends ONLY on domain ports — never on SQLAlchemy,
FastAPI, or any other infrastructure.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.domain.common.errors import EntityNotFoundError
from app.domain.common.uow import UnitOfWork
from app.domain.scanning.models import PeerType, ScanResultItemDomain

logger = logging.getLogger(__name__)


# ── Mapping tables ─────────────────────────────────────────────────────

# PeerType -> key in ScanResultItemDomain.extended_fields
_GROUP_FIELD: dict[PeerType, str] = {
    PeerType.INDUSTRY: "ibd_industry_group",
    PeerType.SECTOR: "gics_sector",
}


# ── Query (input) ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class GetPeersQuery:
    """Immutable value object describing the peers lookup."""

    scan_id: str
    symbol: str
    peer_type: PeerType = PeerType.INDUSTRY

    def __post_init__(self) -> None:
        # Business rule: symbols are case-insensitive.
        object.__setattr__(self, "symbol", self.symbol.upper())


# ── Result (output) ────────────────────────────────────────────────────


@dataclass(frozen=True)
class GetPeersResult:
    """What the use case returns to the caller."""

    peers: tuple[ScanResultItemDomain, ...]
    group_name: str | None
    peer_type: PeerType


# ── Use Case ───────────────────────────────────────────────────────────


class GetPeersUseCase:
    """Retrieve peer stocks from the same industry group or sector."""

    def execute(
        self, uow: UnitOfWork, query: GetPeersQuery
    ) -> GetPeersResult:
        with uow:
            # 1. Verify scan exists
            scan = uow.scans.get_by_scan_id(query.scan_id)
            if scan is None:
                raise EntityNotFoundError("Scan", query.scan_id)

            # Determine data source — flag ensures both calls use
            # the same source (target lookup + peers query).
            use_feature_store = bool(scan.feature_run_id)

            # 2. Look up target symbol
            if use_feature_store:
                logger.info(
                    "Scan %s: routing peers to feature_store (run_id=%d)",
                    query.scan_id,
                    scan.feature_run_id,
                )
                try:
                    target = uow.feature_store.get_by_symbol_for_run(
                        scan.feature_run_id,
                        query.symbol,
                    )
                except EntityNotFoundError:
                    logger.warning(
                        "Feature run %d not found for scan %s, falling back to legacy",
                        scan.feature_run_id,
                        query.scan_id,
                    )
                    use_feature_store = False
                    target = uow.scan_results.get_by_symbol(
                        scan_id=query.scan_id,
                        symbol=query.symbol,
                    )
            else:
                logger.debug(
                    "Scan %s: routing peers to legacy scan_results",
                    query.scan_id,
                )
                target = uow.scan_results.get_by_symbol(
                    scan_id=query.scan_id,
                    symbol=query.symbol,
                )

            if target is None:
                raise EntityNotFoundError("ScanResult", query.symbol)

            # 3. Read group value from extended_fields
            field_key = _GROUP_FIELD[query.peer_type]
            group_value = target.extended_fields.get(field_key)

            # 4. No group -> empty result
            if not group_value or not str(group_value).strip():
                return GetPeersResult(
                    peers=(), group_name=None, peer_type=query.peer_type
                )

            # 5. Delegate to appropriate repo method (same source as target)
            if use_feature_store:
                if query.peer_type == PeerType.INDUSTRY:
                    peers = uow.feature_store.get_peers_by_industry_for_run(
                        scan.feature_run_id, group_value
                    )
                else:
                    peers = uow.feature_store.get_peers_by_sector_for_run(
                        scan.feature_run_id, group_value
                    )
            else:
                if query.peer_type == PeerType.INDUSTRY:
                    peers = uow.scan_results.get_peers_by_industry(
                        query.scan_id, group_value
                    )
                else:
                    peers = uow.scan_results.get_peers_by_sector(
                        query.scan_id, group_value
                    )

        return GetPeersResult(
            peers=peers, group_name=group_value, peer_type=query.peer_type
        )
