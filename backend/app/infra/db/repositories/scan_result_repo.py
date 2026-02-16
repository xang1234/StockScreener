"""SQLAlchemy implementation of ScanResultRepository."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.scanning.ports import ScanResultRepository
from app.models.scan_result import ScanResult


class SqlScanResultRepository(ScanResultRepository):
    """Persist and retrieve ScanResult rows via SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def bulk_insert(self, rows: list[dict]) -> int:
        objects = [ScanResult(**row) for row in rows]
        self._session.bulk_save_objects(objects)
        self._session.flush()
        return len(objects)
