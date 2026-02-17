"""RunBulkScanUseCase — orchestrates the full scan execution lifecycle.

This use case contains the business rules for executing a bulk scan:
  1. Load scan record and determine checkpoint (resume support)
  2. Mark scan as running
  3. Process symbols in chunks via the StockScanner port
  4. Persist results after each chunk (acts as checkpoint)
  5. Report progress via ProgressSink
  6. Check CancellationToken between chunks
  7. Handle completion / failure status transitions

The use case depends ONLY on domain ports — never on SQLAlchemy, Celery,
Redis, or any other infrastructure.

Zero Celery imports.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Iterator, Sequence

from app.domain.common.errors import EntityNotFoundError
from app.domain.common.uow import UnitOfWork
from app.domain.scanning.models import ProgressEvent, ScanStatus
from app.domain.scanning.ports import CancellationToken, ProgressSink, StockScanner

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _chunked(seq: Sequence[str], size: int) -> Iterator[list[str]]:
    """Yield successive chunks of *size* from *seq*."""
    for i in range(0, len(seq), size):
        yield list(seq[i : i + size])


# ── Command (input) ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class RunBulkScanCommand:
    """Immutable value object describing the scan to execute."""

    scan_id: str
    symbols: list[str]
    criteria: dict = field(default_factory=dict)
    chunk_size: int = 50
    correlation_id: str | None = None


# ── Result (output) ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class RunBulkScanResult:
    """What the use case returns to the caller."""

    scan_id: str
    status: str  # completed | cancelled | failed
    total_scanned: int
    passed: int
    failed: int


# ── Use Case ─────────────────────────────────────────────────────────────


class RunBulkScanUseCase:
    """Execute a bulk stock scan: load → run → persist → progress → done.

    The constructor accepts infrastructure collaborators through ports.
    ``execute()`` receives a fresh UoW per invocation (same pattern as
    :class:`CreateScanUseCase`).
    """

    def __init__(self, scanner: StockScanner) -> None:
        self._scanner = scanner

    def execute(
        self,
        uow: UnitOfWork,
        cmd: RunBulkScanCommand,
        progress: ProgressSink,
        cancel: CancellationToken,
    ) -> RunBulkScanResult:
        """Run the full scan lifecycle inside a single UoW."""
        with uow:
            # ── Load scan record ──────────────────────────────────────
            scan = uow.scans.get_by_scan_id(cmd.scan_id)
            if scan is None:
                raise EntityNotFoundError("Scan", cmd.scan_id)

            try:
                return self._run(uow, scan, cmd, progress, cancel)
            except Exception:
                # Best-effort: mark as failed so the UI knows
                try:
                    uow.rollback()
                    uow.scans.update_status(
                        cmd.scan_id, ScanStatus.FAILED.value
                    )
                    uow.commit()
                except Exception:
                    pass
                raise

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(
        self,
        uow: UnitOfWork,
        scan: object,
        cmd: RunBulkScanCommand,
        progress: ProgressSink,
        cancel: CancellationToken,
    ) -> RunBulkScanResult:
        total = len(cmd.symbols)
        screener_names: list[str] = getattr(scan, "screener_types", None) or [
            "minervini"
        ]
        composite_method: str = (
            getattr(scan, "composite_method", None) or "weighted_average"
        )

        # ── Checkpoint: skip already-persisted results ────────────
        already_done = uow.scan_results.count_by_scan_id(cmd.scan_id)
        remaining_symbols = cmd.symbols[already_done:]

        if already_done > 0:
            logger.info(
                "Resuming scan %s from checkpoint %d/%d",
                cmd.scan_id,
                already_done,
                total,
            )

        # ── Mark running ──────────────────────────────────────────
        uow.scans.update_status(
            cmd.scan_id,
            ScanStatus.RUNNING.value,
            total_stocks=total,
        )
        uow.commit()

        # ── Process chunks ────────────────────────────────────────
        processed = already_done
        passed = 0
        failed = 0
        start_time = time.monotonic()

        for chunk in _chunked(remaining_symbols, cmd.chunk_size):
            # 5a — Cancellation gate
            if cancel.is_cancelled():
                uow.scans.update_status(
                    cmd.scan_id,
                    ScanStatus.CANCELLED.value,
                    passed_stocks=passed,
                )
                uow.commit()
                logger.info(
                    "Scan %s cancelled at %d/%d", cmd.scan_id, processed, total
                )
                return RunBulkScanResult(
                    scan_id=cmd.scan_id,
                    status=ScanStatus.CANCELLED.value,
                    total_scanned=processed,
                    passed=passed,
                    failed=failed,
                )

            # 5b — Scan each symbol in the chunk
            chunk_results: list[tuple[str, dict]] = []
            for symbol in chunk:
                try:
                    result = self._scanner.scan_stock_multi(
                        symbol=symbol.upper(),
                        screener_names=screener_names,
                        criteria=cmd.criteria,
                        composite_method=composite_method,
                    )
                    if result and "error" not in result:
                        chunk_results.append((symbol.upper(), result))
                        if result.get("passes_template"):
                            passed += 1
                    else:
                        failed += 1
                except Exception:
                    logger.debug(
                        "Error scanning %s in scan %s",
                        symbol,
                        cmd.scan_id,
                        exc_info=True,
                    )
                    failed += 1
                processed += 1

            # 5c — Persist chunk (doubles as checkpoint)
            if chunk_results:
                uow.scan_results.persist_orchestrator_results(
                    cmd.scan_id, chunk_results
                )
            uow.commit()

            # 5d — Progress reporting
            elapsed = time.monotonic() - start_time
            throughput = (
                (processed - already_done) / elapsed if elapsed > 0 else 0.0
            )
            remaining = total - processed
            eta = remaining / throughput if throughput > 0 else None

            progress.emit(
                ProgressEvent(
                    current=processed,
                    total=total,
                    passed=passed,
                    failed=failed,
                    throughput=round(throughput, 2) if throughput else None,
                    eta_seconds=round(eta) if eta is not None else None,
                )
            )

        # ── Completed ─────────────────────────────────────────────
        uow.scans.update_status(
            cmd.scan_id,
            ScanStatus.COMPLETED.value,
            passed_stocks=passed,
        )
        uow.commit()

        logger.info(
            "Scan %s completed: %d scanned, %d passed, %d failed",
            cmd.scan_id,
            processed,
            passed,
            failed,
        )

        return RunBulkScanResult(
            scan_id=cmd.scan_id,
            status=ScanStatus.COMPLETED.value,
            total_scanned=processed,
            passed=passed,
            failed=failed,
        )
