"""GetPeersUseCase — retrieve peer stocks from the same industry or sector.

Business rules:
  1. Verify the scan exists (raise EntityNotFoundError if not)
  2. Look up the target symbol (raise EntityNotFoundError if not found)
  3. Read the group value from extended_fields based on peer_type
  4. If no group value, return empty result
  5. Delegate to the appropriate repository method (industry or sector)

If scan is bound to a feature run → use feature store.
Otherwise → fall back to scan_results table.

The use case depends ONLY on domain ports — never on SQLAlchemy,
FastAPI, or any other infrastructure.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.domain.common.errors import EntityNotFoundError
from app.domain.common.uow import UnitOfWork
from app.domain.scanning.models import PeerType, ScanResultItemDomain

from ._resolve import resolve_scan

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
            scan, run_id = resolve_scan(uow, query.scan_id)

            if run_id:
                logger.info(
                    "Scan %s: querying peers from feature_store (run_id=%d)",
                    query.scan_id,
                    run_id,
                )
                target = uow.feature_store.get_by_symbol_for_run(
                    run_id,
                    query.symbol,
                )
            else:
                logger.info(
                    "Scan %s: reading peers from scan_results (no feature run)",
                    query.scan_id,
                )
                target = uow.scan_results.get_by_symbol(
                    query.scan_id,
                    query.symbol,
                )

            if target is None:
                raise EntityNotFoundError("ScanResult", query.symbol)

            # Read group value from extended_fields
            field_key = _GROUP_FIELD[query.peer_type]
            group_value = target.extended_fields.get(field_key)

            # No group -> empty result
            if not group_value or not str(group_value).strip():
                return GetPeersResult(
                    peers=(), group_name=None, peer_type=query.peer_type
                )

            # Delegate to appropriate repository method
            if run_id:
                if query.peer_type == PeerType.INDUSTRY:
                    peers = uow.feature_store.get_peers_by_industry_for_run(
                        run_id, group_value
                    )
                else:
                    peers = uow.feature_store.get_peers_by_sector_for_run(
                        run_id, group_value
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
