"""SQLAlchemy implementation of UniverseRepository."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.scanning.ports import UniverseRepository
from app.services.universe_resolver import resolve_symbols as _resolve


class SqlUniverseRepository(UniverseRepository):
    """Resolve universe symbols using the existing universe_resolver service."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def resolve_symbols(self, universe_def: object) -> list[str]:
        return _resolve(self._session, universe_def)
