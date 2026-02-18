"""Tests for ListFeatureRunsUseCase."""

from datetime import date, datetime, timedelta

import pytest

from app.domain.common.errors import ValidationError
from app.domain.feature_store.models import RunStats, RunStatus, RunType
from app.use_cases.feature_store.list_runs import (
    ListFeatureRunsUseCase,
    ListRunsQuery,
)
from tests.unit.use_cases.conftest import (
    FakeFeatureRunRepository,
    FakeFeatureStoreRepository,
    FakeUnitOfWork,
)


def _make_uow() -> tuple[FakeUnitOfWork, FakeFeatureRunRepository, FakeFeatureStoreRepository]:
    store = FakeFeatureStoreRepository()
    runs = FakeFeatureRunRepository(row_counter=store.count_by_run_id)
    uow = FakeUnitOfWork(feature_runs=runs, feature_store=store)
    return uow, runs, store


class TestListFeatureRunsUseCase:
    """Test suite for ListFeatureRunsUseCase."""

    def test_empty_repo(self):
        uow, _, _ = _make_uow()
        uc = ListFeatureRunsUseCase()
        result = uc.execute(uow, ListRunsQuery())
        assert result.runs == ()

    def test_multiple_runs_ordered_by_created_at_desc(self):
        uow, runs_repo, store = _make_uow()
        uc = ListFeatureRunsUseCase()

        # Create runs with different created_at times
        r1 = runs_repo.start_run(date(2026, 2, 15), RunType.DAILY_SNAPSHOT)
        runs_repo.mark_completed(r1.id, RunStats(100, 95, 5, 60.0))
        runs_repo.publish_atomically(r1.id)

        r2 = runs_repo.start_run(date(2026, 2, 16), RunType.DAILY_SNAPSHOT)
        runs_repo.mark_completed(r2.id, RunStats(110, 105, 5, 65.0))
        runs_repo.publish_atomically(r2.id)

        result = uc.execute(uow, ListRunsQuery())
        # Most recent first
        assert len(result.runs) == 2
        assert result.runs[0].id == r2.id
        assert result.runs[1].id == r1.id

    def test_row_counts_computed(self):
        from app.domain.feature_store.models import FeatureRowWrite

        uow, runs_repo, store = _make_uow()
        uc = ListFeatureRunsUseCase()

        r1 = runs_repo.start_run(date(2026, 2, 15), RunType.DAILY_SNAPSHOT)
        # Add 3 rows
        store.upsert_snapshot_rows(r1.id, [
            FeatureRowWrite("AAPL", date(2026, 2, 15), 80.0, 4, 3, {}),
            FeatureRowWrite("MSFT", date(2026, 2, 15), 70.0, 3, 2, {}),
            FeatureRowWrite("GOOG", date(2026, 2, 15), 60.0, 3, 1, {}),
        ])

        result = uc.execute(uow, ListRunsQuery())
        assert result.runs[0].row_count == 3

    def test_status_filter(self):
        uow, runs_repo, _ = _make_uow()
        uc = ListFeatureRunsUseCase()

        r1 = runs_repo.start_run(date(2026, 2, 15), RunType.DAILY_SNAPSHOT)
        runs_repo.mark_completed(r1.id, RunStats(100, 95, 5, 60.0))
        runs_repo.publish_atomically(r1.id)

        r2 = runs_repo.start_run(date(2026, 2, 16), RunType.DAILY_SNAPSHOT)
        runs_repo.mark_completed(r2.id, RunStats(100, 95, 5, 60.0))

        # Filter published only
        result = uc.execute(uow, ListRunsQuery(status="published"))
        assert len(result.runs) == 1
        assert result.runs[0].status == "published"

    def test_date_range_filter(self):
        uow, runs_repo, _ = _make_uow()
        uc = ListFeatureRunsUseCase()

        runs_repo.start_run(date(2026, 2, 10), RunType.DAILY_SNAPSHOT)
        runs_repo.start_run(date(2026, 2, 15), RunType.DAILY_SNAPSHOT)
        runs_repo.start_run(date(2026, 2, 20), RunType.DAILY_SNAPSHOT)

        result = uc.execute(uow, ListRunsQuery(
            date_from=date(2026, 2, 12),
            date_to=date(2026, 2, 18),
        ))
        assert len(result.runs) == 1
        assert result.runs[0].as_of_date == date(2026, 2, 15)

    def test_is_latest_published_flag(self):
        uow, runs_repo, _ = _make_uow()
        uc = ListFeatureRunsUseCase()

        r1 = runs_repo.start_run(date(2026, 2, 15), RunType.DAILY_SNAPSHOT)
        runs_repo.mark_completed(r1.id, RunStats(100, 95, 5, 60.0))
        runs_repo.publish_atomically(r1.id)

        r2 = runs_repo.start_run(date(2026, 2, 16), RunType.DAILY_SNAPSHOT)
        runs_repo.mark_completed(r2.id, RunStats(100, 95, 5, 60.0))
        runs_repo.publish_atomically(r2.id)

        result = uc.execute(uow, ListRunsQuery())
        # r2 is the latest published
        r2_summary = next(r for r in result.runs if r.id == r2.id)
        r1_summary = next(r for r in result.runs if r.id == r1.id)
        assert r2_summary.is_latest_published is True
        assert r1_summary.is_latest_published is False

    def test_limit_validation_too_low(self):
        with pytest.raises(ValidationError, match="limit"):
            ListRunsQuery(limit=0)

    def test_limit_validation_too_high(self):
        with pytest.raises(ValidationError, match="limit"):
            ListRunsQuery(limit=201)

    def test_date_range_validation(self):
        with pytest.raises(ValidationError, match="date_from"):
            ListRunsQuery(date_from=date(2026, 3, 1), date_to=date(2026, 2, 1))

    def test_stats_propagated(self):
        uow, runs_repo, _ = _make_uow()
        uc = ListFeatureRunsUseCase()

        r1 = runs_repo.start_run(date(2026, 2, 15), RunType.DAILY_SNAPSHOT)
        runs_repo.mark_completed(r1.id, RunStats(3000, 2847, 153, 423.5))

        result = uc.execute(uow, ListRunsQuery())
        assert result.runs[0].stats is not None
        assert result.runs[0].stats.total_symbols == 3000
        assert result.runs[0].stats.duration_seconds == 423.5
