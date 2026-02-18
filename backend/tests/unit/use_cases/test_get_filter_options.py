"""Unit tests for GetFilterOptionsUseCase — pure in-memory, no infrastructure."""

from datetime import date

import pytest

from app.domain.common.errors import EntityNotFoundError
from app.domain.feature_store.models import FeatureRow
from app.domain.scanning.models import FilterOptions
from app.use_cases.scanning.get_filter_options import (
    GetFilterOptionsQuery,
    GetFilterOptionsResult,
    GetFilterOptionsUseCase,
)

from tests.unit.use_cases.conftest import (
    FakeFeatureStoreRepository,
    FakeScanResultRepository,
    FakeUnitOfWork,
    make_domain_item,
    setup_scan,
)


# ── Helpers ──────────────────────────────────────────────────────────────


AS_OF = date(2026, 2, 17)


def _make_query(**overrides) -> GetFilterOptionsQuery:
    defaults = dict(scan_id="scan-123")
    defaults.update(overrides)
    return GetFilterOptionsQuery(**defaults)


def _make_feature_row(symbol: str, score: float = 85.0, **details_overrides) -> FeatureRow:
    """Build a FeatureRow with classification fields for filter tests."""
    details = {
        "composite_score": score,
        "rating": "Buy",
        "current_price": 150.0,
        "screeners_run": ["minervini"],
        "composite_method": "weighted_average",
        "screeners_passed": 1,
        "screeners_total": 1,
        "ibd_industry_group": "Semiconductors",
        "gics_sector": "Technology",
    }
    details.update(details_overrides)
    return FeatureRow(
        run_id=1,
        symbol=symbol,
        as_of_date=AS_OF,
        composite_score=score,
        overall_rating=4,  # Buy
        passes_count=1,
        details=details,
    )


def _setup_bound_scan(uow, feature_store, run_id=1, rows=None):
    """Create a scan bound to a feature run, with rows in the feature store."""
    uow.scans.create(scan_id="scan-bound", status="completed", feature_run_id=run_id)
    if rows is None:
        rows = [
            _make_feature_row("AAPL"),
            _make_feature_row("NVDA", ibd_industry_group="Semiconductors", gics_sector="Technology"),
            _make_feature_row("MSFT", score=70.0, ibd_industry_group="Software", gics_sector="Technology"),
        ]
    feature_store.upsert_snapshot_rows(run_id, rows)


# ── Tests ────────────────────────────────────────────────────────────────


class TestHappyPath:
    """Core business logic for retrieving filter options."""

    def test_returns_filter_options(self):
        uow = FakeUnitOfWork()
        setup_scan(uow)
        uc = GetFilterOptionsUseCase()

        result = uc.execute(uow, _make_query())

        assert isinstance(result, GetFilterOptionsResult)
        assert isinstance(result.options, FilterOptions)

    def test_empty_options_for_empty_scan(self):
        uow = FakeUnitOfWork()
        setup_scan(uow)
        uc = GetFilterOptionsUseCase()

        result = uc.execute(uow, _make_query())

        assert result.options.ibd_industries == ()
        assert result.options.gics_sectors == ()
        assert result.options.ratings == ()


class TestScanNotFound:
    """Use case raises EntityNotFoundError for missing scans."""

    def test_nonexistent_scan_raises_not_found(self):
        uow = FakeUnitOfWork()
        uc = GetFilterOptionsUseCase()

        with pytest.raises(EntityNotFoundError, match="Scan.*not-a-scan"):
            uc.execute(uow, _make_query(scan_id="not-a-scan"))

    def test_not_found_error_has_entity_and_identifier(self):
        uow = FakeUnitOfWork()
        uc = GetFilterOptionsUseCase()

        with pytest.raises(EntityNotFoundError) as exc_info:
            uc.execute(uow, _make_query(scan_id="missing"))

        assert exc_info.value.entity == "Scan"
        assert exc_info.value.identifier == "missing"


class TestDualSourceRouting:
    """Verify the use case routes to the correct data source."""

    def test_bound_scan_queries_feature_store(self):
        """Scan with feature_run_id routes to feature store."""
        feature_store = FakeFeatureStoreRepository()
        uow = FakeUnitOfWork(feature_store=feature_store)
        _setup_bound_scan(uow, feature_store)
        uc = GetFilterOptionsUseCase()

        result = uc.execute(uow, _make_query(scan_id="scan-bound"))

        # Feature store returned distinct classification values
        assert "Semiconductors" in result.options.ibd_industries
        assert "Software" in result.options.ibd_industries
        assert "Technology" in result.options.gics_sectors
        assert "Buy" in result.options.ratings

    def test_unbound_scan_queries_legacy(self):
        """Scan without feature_run_id routes to legacy scan_results."""
        feature_store = FakeFeatureStoreRepository()
        uow = FakeUnitOfWork(feature_store=feature_store)
        setup_scan(uow)  # creates "scan-123" without feature_run_id
        uc = GetFilterOptionsUseCase()

        result = uc.execute(uow, _make_query())

        # Legacy fake returns empty FilterOptions
        assert result.options.ibd_industries == ()
        assert result.options.gics_sectors == ()

    def test_bound_scan_fallback_on_missing_run(self):
        """If feature_run_id points to a deleted run, fall back to legacy."""
        feature_store = FakeFeatureStoreRepository()
        uow = FakeUnitOfWork(feature_store=feature_store)
        # Bind to run_id=999 which doesn't exist in feature store
        uow.scans.create(
            scan_id="scan-orphan", status="completed", feature_run_id=999
        )
        uc = GetFilterOptionsUseCase()

        result = uc.execute(uow, _make_query(scan_id="scan-orphan"))

        # Fell back to legacy (empty options)
        assert isinstance(result.options, FilterOptions)
