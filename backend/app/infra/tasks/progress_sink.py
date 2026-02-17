"""Celery implementation of the ProgressSink port.

Translates domain ProgressEvents into Celery task state updates
so the frontend can poll ``AsyncResult.info`` for real-time progress.

Error-resilient: swallows ``update_state`` failures because progress
is non-critical — the frontend has a DB-count fallback
(see ``api/v1/scans.py`` lines 374-378).
"""

from __future__ import annotations

import logging

from app.domain.scanning.models import ProgressEvent
from app.domain.scanning.ports import ProgressSink

logger = logging.getLogger(__name__)


class CeleryProgressSink(ProgressSink):
    """Emit scan progress via Celery's ``update_state``."""

    def __init__(self, task_instance) -> None:
        self._task = task_instance

    def emit(self, event: ProgressEvent) -> None:
        try:
            percent = (event.current / event.total * 100) if event.total > 0 else 0.0
            self._task.update_state(
                state="PROGRESS",
                meta={
                    "current": event.current,
                    "total": event.total,
                    "percent": percent,
                    "passed": event.passed,
                    "failed": event.failed,
                    "throughput": event.throughput,
                    "eta_seconds": event.eta_seconds,
                },
            )
        except Exception:
            logger.warning("Failed to emit progress", exc_info=True)
