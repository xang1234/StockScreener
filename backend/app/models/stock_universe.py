"""Stock universe database model for managing scannable stock lists"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Index
from sqlalchemy.sql import func
from ..database import Base


class StockUniverse(Base):
    """
    Stock universe table storing all scannable stocks.

    Supports fetching from finviz and manual additions.
    Users can activate/deactivate symbols for scanning.
    """

    __tablename__ = "stock_universe"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(10), nullable=False, unique=True, index=True)
    name = Column(String(255))
    exchange = Column(String(20), index=True)  # NYSE, NASDAQ, AMEX
    sector = Column(String(100), index=True)
    industry = Column(String(100))
    market_cap = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True, index=True)  # User can deactivate
    is_sp500 = Column(Boolean, default=False, index=True)  # S&P 500 membership
    source = Column(String(20), default="finviz")  # finviz, manual
    added_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_universe_exchange_active", "exchange", "is_active"),
        Index("idx_universe_sector_active", "sector", "is_active"),
    )

    def __repr__(self):
        return f"<StockUniverse(symbol='{self.symbol}', exchange='{self.exchange}', active={self.is_active})>"
