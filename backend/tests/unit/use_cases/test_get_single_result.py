"""Unit tests for GetSingleResultUseCase — pure in-memory, no infrastructure."""

from datetime import date

import pytest

from app.domain.common.errors import EntityNotFoundError
from app.domain.feature_store.models import FeatureRow
from app.use_cases.scanning.get_single_result import (
    GetSingleResultQuery,
    GetSingleResultResult,
    GetSingleResultUseCase,
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


def _make_query(**overrides) -> GetSingleResultQuery:
    defaults = dict(scan_id="scan-123", symbol="AAPL")
    defaults.update(overrides)
    return GetSingleResultQuery(**defaults)


def _make_feature_row(symbol: str, score: float = 85.0) -> FeatureRow:
    """Build a FeatureRow with minimal details for bridge method tests."""
    return FeatureRow(
        run_id=1,
        symbol=symbol,
        as_of_date=AS_OF,
        composite_score=score,
        overall_rating=4,  # Buy
        passes_count=1,
        details={
            "composite_score": score,
            "rating": "Buy",
            "current_price": 150.0,
            "screeners_run": ["minervini"],
            "composite_method": "weighted_average",
            "screeners_passed": 1,
            "screeners_total": 1,
        },
    )


def _setup_bound_scan(uow, feature_store, run_id=1):
    """Create a scan bound to a feature run, with rows in the feature store."""
    uow.scans.create(scan_id="scan-bound", status="completed", feature_run_id=run_id)
    feature_store.upsert_snapshot_rows(
        run_id,
        [_make_feature_row("AAPL"), _make_feature_row("MSFT", score=70.0)],
    )


# ── Tests ────────────────────────────────────────────────────────────────


class TestHappyPath:
    """Core business logic for retrieving a single scan result."""

    def test_returns_matching_item(self):
        items = [make_domain_item("AAPL"), make_domain_item("MSFT")]
        uow = FakeUnitOfWork(scan_results=FakeScanResultRepository(items=items))
        setup_scan(uow)
        uc = GetSingleResultUseCase()

        result = uc.execute(uow, _make_query(symbol="AAPL"))

        assert isinstance(result, GetSingleResultResult)
        assert result.item.symbol == "AAPL"

    def test_symbol_is_case_insensitive(self):
        items = [make_domain_item("AAPL")]
        uow = FakeUnitOfWork(scan_results=FakeScanResultRepository(items=items))
        setup_scan(uow)
        uc = GetSingleResultUseCase()

        result = uc.execute(uow, _make_query(symbol="aapl"))

        assert result.item.symbol == "AAPL"

    def test_symbol_not_found_raises_error(self):
        uow = FakeUnitOfWork(scan_results=FakeScanResultRepository(items=[]))
        setup_scan(uow)
        uc = GetSingleResultUseCase()

        with pytest.raises(EntityNotFoundError, match="ScanResult.*AAPL"):
            uc.execute(uow, _make_query(symbol="AAPL"))


class TestScanNotFound:
    """Use case raises EntityNotFoundError for missing scans."""

    def test_nonexistent_scan_raises_not_found(self):
        uow = FakeUnitOfWork()
        uc = GetSingleResultUseCase()

        with pytest.raises(EntityNotFoundError, match="Scan.*not-a-scan"):
            uc.execute(uow, _make_query(scan_id="not-a-scan"))

    def test_not_found_error_has_entity_and_identifier(self):
        uow = FakeUnitOfWork()
        uc = GetSingleResultUseCase()

        with pytest.raises(EntityNotFoundError) as exc_info:
            uc.execute(uow, _make_query(scan_id="missing"))

        assert exc_info.value.entity == "Scan"
        assert exc_info.value.identifier == "missing"


class TestDualSourceRouting:
    """Verify the use case routes to the correct data source."""

    def test_bound_scan_queries_feature_store(self):
        """Scan with feature_run_id routes to feature store."""
        feature_store = FakeFeatureStoreRepository()
        legacy_repo = FakeScanResultRepository()
        uow = FakeUnitOfWork(scan_results=legacy_repo, feature_store=feature_store)
        _setup_bound_scan(uow, feature_store)
        uc = GetSingleResultUseCase()

        result = uc.execute(uow, _make_query(scan_id="scan-bound", symbol="AAPL"))

        assert result.item.symbol == "AAPL"
        assert result.item.rating == "Buy"

    def test_unbound_scan_queries_legacy(self):
        """Scan without feature_run_id routes to legacy scan_results."""
        items = [make_domain_item("AAPL")]
        legacy_repo = FakeScanResultRepository(items=items)
        uow = FakeUnitOfWork(scan_results=legacy_repo)
        setup_scan(uow)
        uc = GetSingleResultUseCase()

        result = uc.execute(uow, _make_query(symbol="AAPL"))

        assert result.item.symbol == "AAPL"

    def test_bound_scan_fallback_on_missing_run(self):
        """If feature_run_id points to a deleted run, fall back to legacy."""
        feature_store = FakeFeatureStoreRepository()
        legacy_repo = FakeScanResultRepository(
            items=[make_domain_item("FALLBACK")]
        )
        uow = FakeUnitOfWork(scan_results=legacy_repo, feature_store=feature_store)
        uow.scans.create(
            scan_id="scan-orphan", status="completed", feature_run_id=999
        )
        uc = GetSingleResultUseCase()

        result = uc.execute(uow, _make_query(scan_id="scan-orphan", symbol="FALLBACK"))

        assert result.item.symbol == "FALLBACK"

    def test_bound_scan_symbol_not_found_raises_error(self):
        """Feature store path raises EntityNotFoundError for missing symbol."""
        feature_store = FakeFeatureStoreRepository()
        uow = FakeUnitOfWork(feature_store=feature_store)
        _setup_bound_scan(uow, feature_store)
        uc = GetSingleResultUseCase()

        with pytest.raises(EntityNotFoundError, match="ScanResult.*ZZZZ"):
            uc.execute(uow, _make_query(scan_id="scan-bound", symbol="ZZZZ"))
