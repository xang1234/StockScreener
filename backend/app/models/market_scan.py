"""Market Scan watchlist model"""
from sqlalchemy import Column, Integer, String, DateTime, Text, UniqueConstraint
from sqlalchemy.sql import func
from ..database import Base


class ScanWatchlist(Base):
    """
    Watchlist for Market Scan feature.
    Stores symbols with their display order for TradingView charts.
    """
    __tablename__ = "scan_watchlist"

    id = Column(Integer, primary_key=True, index=True)

    # Watchlist identifier (e.g., "key_markets", "sector_leaders")
    list_name = Column(String(50), nullable=False, index=True)

    # Symbol to display (e.g., "SPY", "QQQ", "BTCUSD")
    symbol = Column(String(50), nullable=False)

    # Display name override (optional, for custom labels)
    display_name = Column(String(100), nullable=True)

    # Order position (for drag-drop reordering)
    position = Column(Integer, nullable=False, default=0)

    # Notes about this symbol
    notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Unique constraint: one symbol per list
    __table_args__ = (
        UniqueConstraint('list_name', 'symbol', name='uix_list_symbol'),
    )
