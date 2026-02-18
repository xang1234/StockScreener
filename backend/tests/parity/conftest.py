"""Shared fixtures for parity tests.

Seeds an in-memory SQLite database with identical data in both the legacy
``scan_results`` table and the ``stock_feature_daily`` table so the two
read paths can be compared field-by-field.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.domain.feature_store.models import RATING_TO_INT
from app.infra.db.models.feature_store import FeatureRun, StockFeatureDaily
from app.infra.db.repositories.scan_result_repo import _map_orchestrator_result
from app.models.scan_result import Scan, ScanResult  # noqa: F401 — register models
from app.models.stock_universe import StockUniverse

from .golden_fixtures import GOLDEN_TICKERS, build_all_golden_results

# ---------------------------------------------------------------------------
# Fixed constants for reproducibility
# ---------------------------------------------------------------------------
GOLDEN_AS_OF_DATE = date(2026, 1, 15)
LEGACY_SCAN_ID = "parity-legacy-00000000-0000-0000-0000"
FEATURE_RUN_ID = 1


@pytest.fixture
def engine():
    """Function-scoped in-memory SQLite engine with FK enforcement."""
    eng = create_engine("sqlite:///:memory:")

    @event.listens_for(eng, "connect")
    def _set_fk_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine):
    """Function-scoped session bound to the in-memory engine."""
    factory = sessionmaker(bind=engine)
    sess = factory()
    yield sess
    sess.close()


@pytest.fixture
def seeded_session(session: Session):
    """Seed both legacy and feature-store tables from the same golden data.

    Returns the session so tests can create repository objects against it.
    """
    golden = build_all_golden_results()

    # ── 1. Universe table (company names for LEFT JOIN) ──────────────
    for symbol in GOLDEN_TICKERS:
        session.add(
            StockUniverse(symbol=symbol, name=f"{symbol} Inc", exchange="NASDAQ")
        )

    # ── 2. Legacy scan (Scan + ScanResult rows) ─────────────────────
    session.add(
        Scan(
            scan_id=LEGACY_SCAN_ID,
            status="completed",
            screener_types=["minervini", "canslim"],
            composite_method="weighted_average",
        )
    )
    session.flush()  # FK target must exist before ScanResult inserts

    # Use the real _map_orchestrator_result helper to exercise the same
    # field translations as the production write path, then bulk_insert.
    # IBD/GICS fields are already in the golden dicts, so the mapper picks
    # them up from `raw` (lines 117-120 of scan_result_repo.py).
    legacy_rows = [
        _map_orchestrator_result(LEGACY_SCAN_ID, symbol, result_dict)
        for symbol, result_dict in golden.items()
    ]

    session.bulk_save_objects([ScanResult(**r) for r in legacy_rows])

    # ── 3. Feature store (FeatureRun + StockFeatureDaily rows) ───────
    session.add(
        FeatureRun(
            id=FEATURE_RUN_ID,
            as_of_date=GOLDEN_AS_OF_DATE,
            run_type="daily_snapshot",
            status="published",
        )
    )
    session.flush()  # FK target must exist before StockFeatureDaily inserts

    for symbol, result_dict in golden.items():
        session.add(
            StockFeatureDaily(
                run_id=FEATURE_RUN_ID,
                symbol=symbol,
                as_of_date=GOLDEN_AS_OF_DATE,
                composite_score=result_dict["composite_score"],
                overall_rating=RATING_TO_INT.get(result_dict.get("rating", "Pass"), 2),
                passes_count=result_dict.get("screeners_passed", 0),
                details_json=result_dict,
            )
        )

    session.commit()
    return session
