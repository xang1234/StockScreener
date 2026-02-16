"""Ports (abstract interfaces) for the scanning domain.

These define WHAT the domain needs from the outside world without
specifying HOW it's provided.  Concrete implementations live in infra/.

Note: No infrastructure types (Session, Engine, Redis) appear here.
Repositories receive their session/connection through the UnitOfWork,
not through method parameters.
"""

from __future__ import annotations

import abc


class ScanRepository(abc.ABC):
    """Persist and retrieve scan metadata."""

    @abc.abstractmethod
    def create(self, *, scan_id: str, **fields) -> object:
        ...

    @abc.abstractmethod
    def get_by_scan_id(self, scan_id: str) -> object | None:
        ...


class ScanResultRepository(abc.ABC):
    """Persist and retrieve individual scan results."""

    @abc.abstractmethod
    def bulk_insert(self, rows: list[dict]) -> int:
        ...


class UniverseRepository(abc.ABC):
    """Resolve which symbols belong to a universe."""

    @abc.abstractmethod
    def resolve_symbols(self, universe_def: object) -> list[str]:
        ...


class StockDataProvider(abc.ABC):
    """Fetch market/fundamental data for scoring."""

    @abc.abstractmethod
    def prepare_data(self, symbol: str, requirements: object) -> object:
        ...

    @abc.abstractmethod
    def prepare_data_bulk(
        self, symbols: list[str], requirements: object
    ) -> dict[str, object]:
        ...
