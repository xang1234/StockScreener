"""
Institutional Ownership Service

SCD2-style tracking for institutional ownership changes.
Records new ownership values only when meaningful changes are detected.
"""
from datetime import date
from typing import Optional
import logging

from sqlalchemy.orm import Session

from ..models.institutional_ownership import InstitutionalOwnershipHistory

logger = logging.getLogger(__name__)


class InstitutionalOwnershipService:
    """
    SCD2-style tracking for institutional ownership changes.

    Implements slowly-changing dimension type 2 pattern:
    - Tracks historical ownership values over time
    - Only records changes when they exceed threshold (default 1%)
    - Maintains `is_current` flag for fast current-value queries
    - Idempotent: safe to call multiple times with same data
    """

    # Threshold: only record if change exceeds this percentage
    CHANGE_THRESHOLD = 1.0  # 1% change required to create new record

    def __init__(self, db: Session):
        """
        Initialize ownership service.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def update_ownership(
        self,
        symbol: str,
        institutional_pct: Optional[float],
        insider_pct: Optional[float],
        institutional_transactions: Optional[float] = None,
        data_source: str = "hybrid"
    ) -> bool:
        """
        Compare new ownership with current record.
        Insert new record only if meaningful change detected.

        This method is idempotent:
        - Same-day multiple calls: Only creates one record per day
        - No change detected: Skips insert if ownership within threshold
        - Re-runs safe: Can safely retry failed refreshes

        Args:
            symbol: Stock ticker symbol
            institutional_pct: Institutional ownership percentage
            insider_pct: Insider ownership percentage
            institutional_transactions: % change in institutional holdings
            data_source: Data source identifier ('hybrid', 'yfinance', 'finviz')

        Returns:
            True if new record was inserted, False otherwise
        """
        if institutional_pct is None and insider_pct is None:
            return False  # No data to track

        # Get current record
        current = self.db.query(InstitutionalOwnershipHistory).filter(
            InstitutionalOwnershipHistory.symbol == symbol,
            InstitutionalOwnershipHistory.is_current == True
        ).first()

        today = date.today()

        if current is None:
            # First record for this symbol
            self._insert_new_record(
                symbol, institutional_pct, insider_pct,
                institutional_transactions, data_source, today
            )
            logger.debug(f"{symbol}: Initial ownership record created")
            return True

        # Check if meaningful change
        if not self._has_meaningful_change(current, institutional_pct, insider_pct):
            logger.debug(
                f"{symbol}: Ownership unchanged (inst: {current.institutional_pct}%, "
                f"insider: {current.insider_pct}%)"
            )
            return False

        # Close current record
        current.valid_to = today
        current.is_current = False

        # Insert new current record
        self._insert_new_record(
            symbol, institutional_pct, insider_pct,
            institutional_transactions, data_source, today
        )

        # Log the change
        old_inst = current.institutional_pct
        new_inst = institutional_pct
        if old_inst is not None and new_inst is not None:
            change = new_inst - old_inst
            direction = "↑" if change > 0 else "↓"
            logger.info(
                f"{symbol}: Institutional ownership {direction} "
                f"{old_inst:.1f}% → {new_inst:.1f}% ({change:+.1f}%)"
            )
        else:
            logger.info(f"{symbol}: Ownership record updated")

        return True

    def _has_meaningful_change(
        self,
        current: InstitutionalOwnershipHistory,
        new_inst_pct: Optional[float],
        new_insider_pct: Optional[float]
    ) -> bool:
        """
        Check if change exceeds threshold.

        Args:
            current: Current ownership record
            new_inst_pct: New institutional ownership percentage
            new_insider_pct: New insider ownership percentage

        Returns:
            True if change exceeds threshold
        """
        # Check institutional ownership change
        if new_inst_pct is not None and current.institutional_pct is not None:
            if abs(new_inst_pct - current.institutional_pct) >= self.CHANGE_THRESHOLD:
                return True

        # Check insider ownership change
        if new_insider_pct is not None and current.insider_pct is not None:
            if abs(new_insider_pct - current.insider_pct) >= self.CHANGE_THRESHOLD:
                return True

        # Handle case where we have new data but didn't have it before
        if new_inst_pct is not None and current.institutional_pct is None:
            return True
        if new_insider_pct is not None and current.insider_pct is None:
            return True

        return False

    def _insert_new_record(
        self,
        symbol: str,
        institutional_pct: Optional[float],
        insider_pct: Optional[float],
        institutional_transactions: Optional[float],
        data_source: str,
        valid_from: date
    ):
        """
        Insert new current record.

        Args:
            symbol: Stock ticker symbol
            institutional_pct: Institutional ownership percentage
            insider_pct: Insider ownership percentage
            institutional_transactions: % change in institutional holdings
            data_source: Data source identifier
            valid_from: Date this record becomes effective
        """
        record = InstitutionalOwnershipHistory(
            symbol=symbol,
            institutional_pct=institutional_pct,
            insider_pct=insider_pct,
            institutional_transactions=institutional_transactions,
            valid_from=valid_from,
            valid_to=None,
            is_current=True,
            data_source=data_source
        )
        self.db.add(record)

    def get_history(self, symbol: str) -> list[InstitutionalOwnershipHistory]:
        """
        Get full ownership history for a symbol.

        Args:
            symbol: Stock ticker symbol

        Returns:
            List of ownership records, newest first
        """
        return self.db.query(InstitutionalOwnershipHistory).filter(
            InstitutionalOwnershipHistory.symbol == symbol
        ).order_by(InstitutionalOwnershipHistory.valid_from.desc()).all()

    def get_current(self, symbol: str) -> Optional[InstitutionalOwnershipHistory]:
        """
        Get current ownership record.

        Args:
            symbol: Stock ticker symbol

        Returns:
            Current ownership record or None
        """
        return self.db.query(InstitutionalOwnershipHistory).filter(
            InstitutionalOwnershipHistory.symbol == symbol,
            InstitutionalOwnershipHistory.is_current == True
        ).first()

    def bulk_update(
        self,
        fundamentals_list: list[dict],
        data_source: str = "hybrid"
    ) -> int:
        """
        Batch update ownership from fundamentals refresh.
        Called after hybrid fundamentals fetch completes.

        Args:
            fundamentals_list: List of fundamental data dicts
            data_source: Data source identifier

        Returns:
            Number of symbols with changes recorded
        """
        updated_count = 0

        for data in fundamentals_list:
            symbol = data.get("symbol")
            if not symbol:
                continue

            was_updated = self.update_ownership(
                symbol=symbol,
                institutional_pct=data.get("institutional_ownership"),
                insider_pct=data.get("insider_ownership"),
                institutional_transactions=data.get("institutional_transactions"),
                data_source=data_source
            )
            if was_updated:
                updated_count += 1

        # Commit all changes at once
        self.db.commit()

        logger.info(
            f"Institutional ownership bulk update: "
            f"{updated_count}/{len(fundamentals_list)} symbols with changes recorded"
        )
        return updated_count

    def get_recent_changes(
        self,
        days: int = 30,
        min_change_pct: float = 5.0
    ) -> list[dict]:
        """
        Get symbols with significant recent ownership changes.

        Args:
            days: Look back period in days
            min_change_pct: Minimum change percentage to include

        Returns:
            List of dicts with symbol, old_pct, new_pct, change, change_date
        """
        from datetime import timedelta

        cutoff_date = date.today() - timedelta(days=days)

        # Get current records with a previous record
        results = []

        # Query current records
        current_records = self.db.query(InstitutionalOwnershipHistory).filter(
            InstitutionalOwnershipHistory.is_current == True,
            InstitutionalOwnershipHistory.valid_from >= cutoff_date
        ).all()

        for current in current_records:
            # Find the previous record for this symbol
            previous = self.db.query(InstitutionalOwnershipHistory).filter(
                InstitutionalOwnershipHistory.symbol == current.symbol,
                InstitutionalOwnershipHistory.valid_to == current.valid_from
            ).first()

            if previous and previous.institutional_pct and current.institutional_pct:
                change = current.institutional_pct - previous.institutional_pct
                if abs(change) >= min_change_pct:
                    results.append({
                        'symbol': current.symbol,
                        'previous_pct': previous.institutional_pct,
                        'current_pct': current.institutional_pct,
                        'change': change,
                        'change_date': current.valid_from
                    })

        # Sort by absolute change descending
        results.sort(key=lambda x: abs(x['change']), reverse=True)
        return results
