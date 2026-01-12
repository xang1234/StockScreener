"""Market status models"""
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, UniqueConstraint
from sqlalchemy.sql import func
from ..database import Base


class MarketStatus(Base):
    """Daily market trend and status"""

    __tablename__ = "market_status"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False, unique=True, index=True)

    # SPY (S&P 500 ETF) data
    spy_price = Column(Float)
    spy_ma50 = Column(Float)
    spy_ma200 = Column(Float)

    # Market trend
    trend = Column(String(20))  # bullish, bearish, neutral

    # VIX (volatility index)
    vix = Column(Float)

    # Timestamp
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
