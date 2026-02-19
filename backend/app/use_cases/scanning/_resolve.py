"""Shared scan resolution helper for read-side use cases.

Extracts the repeated prologue (load scan → check feature_run_id)
into a single reusable function, keeping each use case DRY.
"""

from __future__ import annotations

from app.domain.common.errors import EntityNotFoundError
from app.domain.common.uow import UnitOfWork


def resolve_scan(uow: UnitOfWork, scan_id: str) -> tuple[object, int | None]:
    """Load a scan by ID; return ``(scan, feature_run_id_or_None)``.

    Raises:
        EntityNotFoundError: If no scan with *scan_id* exists.
    """
    scan = uow.scans.get_by_scan_id(scan_id)
    if scan is None:
        raise EntityNotFoundError("Scan", scan_id)
    return scan, scan.feature_run_id
