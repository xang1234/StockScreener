"""User-defined watchlists for Market Scan Watchlists tab"""
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, UniqueConstraint, Index
from sqlalchemy.sql import func
from ..database import Base


class UserWatchlist(Base):
    """
    User-defined watchlist (top-level container).
    Example: "High RS Leaders", "Earnings Watch", "Breakout Candidates"
    """
    __tablename__ = "user_watchlists"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    color = Column(String(20), nullable=True)
    position = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class WatchlistItem(Base):
    """
    Stock item within a watchlist.
    """
    __tablename__ = "watchlist_items"

    id = Column(Integer, primary_key=True, index=True)
    watchlist_id = Column(Integer, ForeignKey("user_watchlists.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol = Column(String(20), nullable=False)
    display_name = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    position = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('watchlist_id', 'symbol', name='uix_watchlist_symbol'),
        Index("idx_watchlist_item", "watchlist_id", "position"),
    )
