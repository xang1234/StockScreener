"""Tests for SqlUnitOfWork using in-memory SQLite.

Verifies that all repositories share the same session and that
cross-repo transactions are visible within a single UoW.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import sessionmaker

from app.domain.feature_store.models import FeatureRowWrite, RunType
from app.infra.db.uow import SqlUnitOfWork


class TestSqlUnitOfWork:
    def test_repos_share_session(self, engine):
        factory = sessionmaker(bind=engine)
        uow = SqlUnitOfWork(factory)

        with uow:
            sessions = {
                id(uow.scans._session),
                id(uow.scan_results._session),
                id(uow.universe._session),
                id(uow.feature_runs._session),
                id(uow.feature_store._session),
            }
            # All 5 repos must reference the exact same session object
            assert len(sessions) == 1

    def test_cross_repo_transaction(self, engine):
        """Write via feature_runs, upsert via feature_store, read back."""
        factory = sessionmaker(bind=engine)

        # Write data in one UoW
        with SqlUnitOfWork(factory) as uow:
            run = uow.feature_runs.start_run(
                as_of_date=date(2026, 2, 17),
                run_type=RunType.DAILY_SNAPSHOT,
            )
            row = FeatureRowWrite(
                symbol="AAPL",
                as_of_date=date(2026, 2, 17),
                composite_score=85.0,
                overall_rating=4,
                passes_count=3,
                details={"minervini_score": 85.0},
            )
            count = uow.feature_store.upsert_snapshot_rows(run.id, [row])
            assert count == 1
            uow.commit()

        # Verify in a fresh UoW
        with SqlUnitOfWork(factory) as uow:
            stored_count = uow.feature_store.count_by_run_id(run.id)
            assert stored_count == 1
