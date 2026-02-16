"""Dependency injection bootstrap — the single place that binds ports to adapters.

Every factory function here can be used as a FastAPI ``Depends()`` target.
Routers never import concrete implementations directly; they depend on
the abstractions returned by these factories.

Example usage in a router::

    from app.wiring.bootstrap import get_uow

    @router.post("/scans")
    async def create_scan(uow: SqlUnitOfWork = Depends(get_uow)):
        with uow:
            uow.scans.create(scan_id=..., ...)
            uow.commit()
"""

from __future__ import annotations

from typing import Iterator

from app.database import SessionLocal
from app.domain.scanning.ports import StockDataProvider
from app.infra.db.uow import SqlUnitOfWork
from app.infra.providers.stock_data import DataPrepStockDataProvider


# ── Unit of Work ─────────────────────────────────────────────────────────


def get_uow() -> Iterator[SqlUnitOfWork]:
    """Yield a SqlUnitOfWork bound to SessionLocal.

    Designed for FastAPI Depends()::

        uow: SqlUnitOfWork = Depends(get_uow)
    """
    uow = SqlUnitOfWork(SessionLocal)
    yield uow


# ── Providers ────────────────────────────────────────────────────────────

_stock_data_provider: DataPrepStockDataProvider | None = None


def get_stock_data_provider() -> StockDataProvider:
    """Return a singleton StockDataProvider (wraps DataPreparationLayer)."""
    global _stock_data_provider
    if _stock_data_provider is None:
        _stock_data_provider = DataPrepStockDataProvider()
    return _stock_data_provider
