"""Market breadth indicator models"""
from sqlalchemy import Column, Integer, Float, Date, DateTime, Index
from sqlalchemy.sql import func
from ..database import Base


class MarketBreadth(Base):
    """
    Daily market breadth indicators based on StockBee methodology.

    Tracks breadth metrics across all active stocks in the universe:
    - Daily movers (4%+ threshold)
    - Multi-day ratios (5-day, 10-day)
    - Monthly and quarterly movers (various thresholds)
    """

    __tablename__ = "market_breadth"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False, unique=True, index=True)

    # Daily movers (4%+ threshold)
    stocks_up_4pct = Column(Integer, default=0, nullable=False)
    stocks_down_4pct = Column(Integer, default=0, nullable=False)

    # Multi-day ratios (up/down over period)
    ratio_5day = Column(Float, nullable=True)  # Nullable for edge cases (denominator = 0)
    ratio_10day = Column(Float, nullable=True)

    # Quarterly movers (63 trading days, ~25% threshold)
    stocks_up_25pct_quarter = Column(Integer, default=0, nullable=False)
    stocks_down_25pct_quarter = Column(Integer, default=0, nullable=False)

    # Monthly movers (21 trading days, 25% threshold)
    stocks_up_25pct_month = Column(Integer, default=0, nullable=False)
    stocks_down_25pct_month = Column(Integer, default=0, nullable=False)

    # Monthly extreme movers (21 trading days, 50% threshold)
    stocks_up_50pct_month = Column(Integer, default=0, nullable=False)
    stocks_down_50pct_month = Column(Integer, default=0, nullable=False)

    # 34-day movers (13% threshold - IBD-style)
    stocks_up_13pct_34days = Column(Integer, default=0, nullable=False)
    stocks_down_13pct_34days = Column(Integer, default=0, nullable=False)

    # Metadata
    total_stocks_scanned = Column(Integer, default=0, nullable=False)
    calculation_duration_seconds = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_breadth_date", "date"),
    )

    def __repr__(self):
        return f"<MarketBreadth(date={self.date}, up_4pct={self.stocks_up_4pct}, down_4pct={self.stocks_down_4pct})>"
