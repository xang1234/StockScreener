"""Unit tests for Celery infrastructure adapters.

Tests CeleryProgressSink and DbCancellationToken in isolation
using mock objects — no Redis, no real database.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.domain.scanning.models import ProgressEvent
from app.infra.tasks.progress_sink import CeleryProgressSink
from app.infra.tasks.cancellation import DbCancellationToken


# ---------------------------------------------------------------------------
# CeleryProgressSink
# ---------------------------------------------------------------------------


class TestCeleryProgressSink:
    """Verify that progress events become Celery update_state calls."""

    def test_emit_calls_update_state_with_correct_keys(self):
        task = MagicMock()
        sink = CeleryProgressSink(task)

        event = ProgressEvent(
            current=50, total=100, passed=30, failed=5,
            throughput=2.5, eta_seconds=20,
        )
        sink.emit(event)

        task.update_state.assert_called_once_with(
            state="PROGRESS",
            meta={
                "current": 50,
                "total": 100,
                "percent": 50.0,
                "passed": 30,
                "failed": 5,
                "throughput": 2.5,
                "eta_seconds": 20,
            },
        )

    def test_percent_computed_correctly(self):
        task = MagicMock()
        sink = CeleryProgressSink(task)

        sink.emit(ProgressEvent(current=1, total=3, passed=1, failed=0))

        meta = task.update_state.call_args[1]["meta"]
        assert abs(meta["percent"] - 33.333333) < 0.01

    def test_total_zero_does_not_crash(self):
        """Division by zero guard: total=0 yields 0% instead of ZeroDivisionError."""
        task = MagicMock()
        sink = CeleryProgressSink(task)

        sink.emit(ProgressEvent(current=0, total=0, passed=0, failed=0))

        meta = task.update_state.call_args[1]["meta"]
        assert meta["percent"] == 0.0

    def test_update_state_failure_is_swallowed(self):
        """Redis/Celery failures must not kill the scan."""
        task = MagicMock()
        task.update_state.side_effect = ConnectionError("Redis down")
        sink = CeleryProgressSink(task)

        # Should not raise
        sink.emit(ProgressEvent(current=1, total=10, passed=0, failed=0))

    def test_none_throughput_and_eta_passed_through(self):
        task = MagicMock()
        sink = CeleryProgressSink(task)

        sink.emit(ProgressEvent(current=1, total=10, passed=1, failed=0))

        meta = task.update_state.call_args[1]["meta"]
        assert meta["throughput"] is None
        assert meta["eta_seconds"] is None


# ---------------------------------------------------------------------------
# DbCancellationToken
# ---------------------------------------------------------------------------


class TestDbCancellationToken:
    """Verify DB-polling cancellation logic."""

    def _make_token(self, scan_status="running"):
        """Create a token with a mocked session that returns the given status."""
        mock_session = MagicMock()
        mock_query = MagicMock()

        # Build the chain: session.query().filter().scalar()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = scan_status

        mock_factory = MagicMock(return_value=mock_session)
        token = DbCancellationToken(mock_factory, "test-scan-001")
        return token, mock_session

    def test_returns_true_when_cancelled(self):
        token, _ = self._make_token(scan_status="cancelled")
        assert token.is_cancelled() is True

    def test_returns_false_when_running(self):
        token, _ = self._make_token(scan_status="running")
        assert token.is_cancelled() is False

    def test_returns_false_when_completed(self):
        token, _ = self._make_token(scan_status="completed")
        assert token.is_cancelled() is False

    def test_returns_false_on_db_error(self):
        """Fail-open: DB errors → don't cancel."""
        mock_session = MagicMock()
        mock_session.expire_all.side_effect = Exception("DB connection lost")

        mock_factory = MagicMock(return_value=mock_session)
        token = DbCancellationToken(mock_factory, "test-scan-001")

        assert token.is_cancelled() is False

    def test_returns_false_when_scan_not_found(self):
        """If the scan row doesn't exist, don't cancel."""
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = None

        mock_factory = MagicMock(return_value=mock_session)
        token = DbCancellationToken(mock_factory, "nonexistent")

        assert token.is_cancelled() is False

    def test_expire_all_called_for_fresh_reads(self):
        """Verifies the session identity map is invalidated each check."""
        token, mock_session = self._make_token()
        token.is_cancelled()

        mock_session.expire_all.assert_called_once()

    def test_close_closes_session(self):
        token, mock_session = self._make_token()
        token.close()

        mock_session.close.assert_called_once()

    def test_close_swallows_errors(self):
        """close() should not raise even if the session is broken."""
        mock_session = MagicMock()
        mock_session.close.side_effect = Exception("already closed")

        mock_factory = MagicMock(return_value=mock_session)
        token = DbCancellationToken(mock_factory, "test-scan-001")

        # Should not raise
        token.close()
