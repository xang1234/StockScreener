"""Ticker validation log model for tracking invalid/failed tickers"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Index
from sqlalchemy.sql import func
from ..database import Base


class TickerValidationLog(Base):
    """
    Log of ticker validation failures during data fetching operations.

    Used to track invalid tickers for manual review without auto-deactivating.
    Failures are categorized by error type and can be resolved after review.
    """
    __tablename__ = "ticker_validation_log"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)

    # Error categorization
    error_type = Column(String(50), nullable=False)  # 'no_data', 'delisted', 'api_error', 'invalid_response', 'empty_info'
    error_message = Column(Text)
    error_details = Column(Text)  # JSON for extra context

    # Data source that failed
    data_source = Column(String(20))  # 'yfinance', 'finviz', 'both'

    # Trigger context
    triggered_by = Column(String(50), nullable=False)  # 'fundamentals_refresh', 'cache_warmup', 'universe_refresh', 'scan'
    task_id = Column(String(100))  # Celery task ID for correlation

    # Resolution tracking
    is_resolved = Column(Boolean, default=False, index=True)
    resolved_at = Column(DateTime(timezone=True))
    resolution_notes = Column(Text)

    # Timestamps
    detected_at = Column(DateTime(timezone=True), server_default=func.now())

    # For tracking repeated failures
    consecutive_failures = Column(Integer, default=1)

    __table_args__ = (
        Index("idx_validation_unresolved", "is_resolved", "detected_at"),
        Index("idx_validation_symbol_unresolved", "symbol", "is_resolved", "detected_at"),
    )

    def __repr__(self):
        return f"<TickerValidationLog(symbol='{self.symbol}', error_type='{self.error_type}', resolved={self.is_resolved})>"
