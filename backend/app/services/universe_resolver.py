"""
Universe resolver — centralized symbol resolution for scan universes.

Replaces inline symbol resolution in create_scan() with a single service
that maps UniverseDefinition → list of stock symbols. Used by the API,
Celery tasks, and any future scan triggers.
"""
import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from ..schemas.universe import UniverseDefinition, UniverseType
from ..services.stock_universe_service import stock_universe_service

logger = logging.getLogger(__name__)


def resolve_symbols(
    db: Session,
    universe_def: UniverseDefinition,
    limit: Optional[int] = None,
) -> List[str]:
    """
    Resolve a UniverseDefinition to a list of stock symbols.

    Args:
        db: Database session
        universe_def: Typed universe definition
        limit: Optional max number of symbols to return

    Returns:
        List of uppercase stock symbol strings
    """
    t = universe_def.type

    if t == UniverseType.ALL:
        return stock_universe_service.get_active_symbols(
            db, exchange=None, sp500_only=False, limit=limit
        )

    elif t == UniverseType.EXCHANGE:
        return stock_universe_service.get_active_symbols(
            db, exchange=universe_def.exchange.value, sp500_only=False, limit=limit
        )

    elif t == UniverseType.INDEX:
        return stock_universe_service.get_active_symbols(
            db, exchange=None, sp500_only=True, limit=limit
        )

    elif t in (UniverseType.CUSTOM, UniverseType.TEST):
        symbols = universe_def.symbols
        if limit is not None:
            return symbols[:limit]
        return symbols

    else:
        raise ValueError(f"Unknown universe type: {t}")


def resolve_count(
    db: Session,
    universe_def: UniverseDefinition,
) -> int:
    """
    Get the count of symbols in a universe without fetching the full list.

    For CUSTOM/TEST, this is cheap (len of symbols list).
    For ALL/EXCHANGE/INDEX, this queries the DB.

    Args:
        db: Database session
        universe_def: Typed universe definition

    Returns:
        Number of symbols in the universe
    """
    if universe_def.type in (UniverseType.CUSTOM, UniverseType.TEST):
        return len(universe_def.symbols)
    return len(resolve_symbols(db, universe_def))
