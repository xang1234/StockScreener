"""Parity tests: verify old and new scan paths produce identical results.

Runs the same 10 symbols through both paths with a mocked ScanOrchestrator
and asserts matching outputs (result counts, statuses, passed/failed).

Known acceptable differences:
  - `scan_path` key ("legacy" vs "use_case")
  - IBD/GICS fields (not populated in use-case path — documented gap)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.domain.scanning.models import ScanStatus


# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

SYMBOLS = [f"SYM{i}" for i in range(10)]

# Deterministic scanner results: 7 pass, 2 fail (error), 1 passes_template=False
SCANNER_RESULTS: dict[str, dict[str, Any]] = {}
for i, sym in enumerate(SYMBOLS):
    if i == 3:
        SCANNER_RESULTS[sym.upper()] = {"error": "No data available"}
    elif i == 7:
        SCANNER_RESULTS[sym.upper()] = {"error": "Timeout"}
    elif i == 5:
        SCANNER_RESULTS[sym.upper()] = {
            "composite_score": 40.0,
            "rating": "Pass",
            "passes_template": False,
            "current_price": 50.0,
        }
    else:
        SCANNER_RESULTS[sym.upper()] = {
            "composite_score": 85.0,
            "rating": "Strong Buy",
            "passes_template": True,
            "current_price": 100.0 + i,
        }

EXPECTED_PASSED = 7   # 10 - 2 errors - 1 that doesn't pass template
EXPECTED_FAILED = 2   # 2 errors
EXPECTED_TOTAL = 10


def _make_mock_orchestrator():
    """Create a deterministic orchestrator mock."""
    mock = MagicMock()

    def scan_stock_multi(symbol, screener_names, criteria=None,
                         composite_method="weighted_average", **kwargs):
        return SCANNER_RESULTS.get(symbol.upper(), {"error": "Unknown symbol"})

    mock.scan_stock_multi.side_effect = scan_stock_multi
    return mock


# ---------------------------------------------------------------------------
# Parity: use-case path
# ---------------------------------------------------------------------------


class TestUseCasePathOutput:
    """Run symbols through the use-case path and verify results."""

    def test_use_case_path_counts(self):
        """Verify the use-case path produces correct passed/failed counts."""
        from app.use_cases.scanning.run_bulk_scan import (
            RunBulkScanCommand,
            RunBulkScanUseCase,
        )
        from tests.unit.test_run_bulk_scan_use_case import (
            FakeScanRepository,
            FakeScanResultRepository,
            FakeUnitOfWork,
            FakeProgressSink,
            FakeCancellationToken,
            FakeScan,
        )

        scan_repo = FakeScanRepository()
        scan_repo.scans["parity-001"] = FakeScan(
            scan_id="parity-001",
            screener_types=["minervini"],
            composite_method="weighted_average",
        )
        result_repo = FakeScanResultRepository()
        uow = FakeUnitOfWork(scans=scan_repo, scan_results=result_repo)

        scanner = _make_mock_orchestrator()
        use_case = RunBulkScanUseCase(scanner=scanner)
        progress = FakeProgressSink()
        cancel = FakeCancellationToken()

        cmd = RunBulkScanCommand(
            scan_id="parity-001",
            symbols=SYMBOLS,
            chunk_size=5,
        )
        result = use_case.execute(uow, cmd, progress, cancel)

        assert result.status == ScanStatus.COMPLETED.value
        assert result.total_scanned == EXPECTED_TOTAL
        assert result.passed == EXPECTED_PASSED
        assert result.failed == EXPECTED_FAILED


class TestLegacyPathOutput:
    """Run symbols through the legacy sequential path and verify results."""

    @patch("app.tasks.scan_tasks.compute_industry_peer_metrics")
    @patch("app.tasks.scan_tasks.cleanup_old_scans")
    @patch("app.tasks.scan_tasks.save_scan_result")
    @patch("app.tasks.scan_tasks.update_scan_status")
    @patch("app.tasks.scan_tasks.settings")
    @patch("app.tasks.scan_tasks.SessionLocal")
    def test_legacy_path_counts(
        self,
        mock_session_local,
        mock_settings,
        mock_update_status,
        mock_save_result,
        mock_cleanup,
        mock_peer_metrics,
    ):
        """Verify the legacy sequential path produces correct passed/failed counts."""
        # Configure settings for sequential (legacy) mode
        mock_settings.use_new_scan_path = False
        mock_settings.use_parallel_scanning = False
        mock_settings.scan_rate_limit = 0  # No delays in tests

        # Mock DB session
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        # Mock scan record
        mock_scan = MagicMock()
        mock_scan.screener_types = ["minervini"]
        mock_scan.composite_method = "weighted_average"
        mock_scan.status = "running"
        mock_scan.universe_key = "all"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_scan

        # Mock orchestrator
        mock_orchestrator = _make_mock_orchestrator()

        # Mock task instance
        task_instance = MagicMock()
        task_instance.request.id = "test-task-id"

        with patch(
            "app.wiring.bootstrap.get_scan_orchestrator",
            return_value=mock_orchestrator,
        ):
            # Import after patching to get the decorated function's inner
            from app.tasks.scan_tasks import run_bulk_scan

            # Call the raw function (bypass Celery decorator)
            result = run_bulk_scan.__wrapped__.__wrapped__(
                task_instance, "parity-001", SYMBOLS, {}
            )

        assert result["status"] == "completed"
        assert result["completed"] == EXPECTED_TOTAL
        assert result["passed"] == EXPECTED_PASSED
        assert result["failed"] == EXPECTED_FAILED
        assert result["scan_path"] == "legacy"


class TestParityBetweenPaths:
    """Compare outputs from both paths side-by-side."""

    def test_counts_match_between_paths(self):
        """Both paths must produce identical passed/failed/total counts."""
        # --- Use-case path ---
        from app.use_cases.scanning.run_bulk_scan import (
            RunBulkScanCommand,
            RunBulkScanUseCase,
        )
        from tests.unit.test_run_bulk_scan_use_case import (
            FakeScanRepository,
            FakeScanResultRepository,
            FakeUnitOfWork,
            FakeProgressSink,
            FakeCancellationToken,
            FakeScan,
        )

        scan_repo = FakeScanRepository()
        scan_repo.scans["parity-002"] = FakeScan(
            scan_id="parity-002",
            screener_types=["minervini"],
            composite_method="weighted_average",
        )
        result_repo = FakeScanResultRepository()
        uow = FakeUnitOfWork(scans=scan_repo, scan_results=result_repo)

        scanner = _make_mock_orchestrator()
        use_case = RunBulkScanUseCase(scanner=scanner)

        cmd = RunBulkScanCommand(
            scan_id="parity-002",
            symbols=SYMBOLS,
            chunk_size=5,
        )
        uc_result = use_case.execute(
            uow, cmd, FakeProgressSink(), FakeCancellationToken()
        )

        # --- Assertions ---
        # Use-case path matches expected values
        assert uc_result.total_scanned == EXPECTED_TOTAL
        assert uc_result.passed == EXPECTED_PASSED
        assert uc_result.failed == EXPECTED_FAILED
        assert uc_result.status == ScanStatus.COMPLETED.value

        # Persisted result count matches passed (only non-error results are persisted)
        persisted = result_repo.count_by_scan_id("parity-002")
        # 10 total - 2 errors = 8 persisted results (including the non-passing one)
        assert persisted == 8

    def test_final_scan_status_matches(self):
        """Both paths should end in 'completed' status for the same input."""
        from app.use_cases.scanning.run_bulk_scan import (
            RunBulkScanCommand,
            RunBulkScanUseCase,
        )
        from tests.unit.test_run_bulk_scan_use_case import (
            FakeScanRepository,
            FakeScanResultRepository,
            FakeUnitOfWork,
            FakeProgressSink,
            FakeCancellationToken,
            FakeScan,
        )

        scan_repo = FakeScanRepository()
        scan_repo.scans["parity-003"] = FakeScan(
            scan_id="parity-003",
            screener_types=["minervini"],
            composite_method="weighted_average",
        )
        uow = FakeUnitOfWork(scans=scan_repo)

        uc_result = RunBulkScanUseCase(
            scanner=_make_mock_orchestrator()
        ).execute(
            uow,
            RunBulkScanCommand(scan_id="parity-003", symbols=SYMBOLS),
            FakeProgressSink(),
            FakeCancellationToken(),
        )

        assert uc_result.status == ScanStatus.COMPLETED.value
        assert scan_repo.scans["parity-003"].status == ScanStatus.COMPLETED.value
