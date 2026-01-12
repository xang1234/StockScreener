"""Model for tracking institutional ownership history (SCD2 pattern)."""
from sqlalchemy import Column, Integer, String, Float, Date, Boolean, DateTime
from sqlalchemy.sql import func
from ..database import Base


class InstitutionalOwnershipHistory(Base):
    """
    SCD2-style historical tracking for institutional ownership.

    Tracks changes in institutional and insider ownership over time.
    Only creates new records when ownership changes meaningfully (>1% threshold).
    """

    __tablename__ = "institutional_ownership_history"

    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False, index=True)

    # Ownership values
    institutional_pct = Column(Float)
    insider_pct = Column(Float)
    institutional_transactions = Column(Float)  # % change in inst holdings

    # SCD2 columns
    valid_from = Column(Date, nullable=False)
    valid_to = Column(Date)  # NULL = current record
    is_current = Column(Boolean, default=True)

    # Metadata
    data_source = Column(String(20))
    created_at = Column(DateTime, default=func.now())

    def __repr__(self):
        return (
            f"<InstitutionalOwnershipHistory("
            f"symbol={self.symbol}, "
            f"inst={self.institutional_pct}%, "
            f"insider={self.insider_pct}%, "
            f"current={self.is_current}, "
            f"valid_from={self.valid_from})>"
        )
