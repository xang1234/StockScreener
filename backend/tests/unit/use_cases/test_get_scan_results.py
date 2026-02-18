"""Unit tests for GetScanResultsUseCase — pure in-memory, no infrastructure."""

from datetime import date

import pytest

from app.domain.common.errors import EntityNotFoundError
from app.domain.feature_store.models import FeatureRow
from app.domain.scanning.filter_spec import (
    PageSpec,
    QuerySpec,
    SortOrder,
    SortSpec,
)
from app.domain.scanning.models import ResultPage
from app.use_cases.scanning.get_scan_results import (
    GetScanResultsQuery,
    GetScanResultsResult,
    GetScanResultsUseCase,
)

from tests.unit.use_cases.conftest import (
    FakeFeatureStoreRepository,
    FakeScanResultRepository,
    FakeUnitOfWork,
    make_domain_item,
    setup_scan,
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _make_query(**overrides) -> GetScanResultsQuery:
    defaults = dict(scan_id="scan-123")
    defaults.update(overrides)
    return GetScanResultsQuery(**defaults)


# ── Tests ────────────────────────────────────────────────────────────────


class TestHappyPath:
    """Core business logic for retrieving scan results."""

    def test_returns_result_page(self):
        items = [make_domain_item("AAPL"), make_domain_item("MSFT")]
        uow = FakeUnitOfWork(scan_results=FakeScanResultRepository(items=items))
        setup_scan(uow)
        uc = GetScanResultsUseCase()

        result = uc.execute(uow, _make_query())

        assert isinstance(result, GetScanResultsResult)
        assert isinstance(result.page, ResultPage)
        assert result.page.total == 2
        assert len(result.page.items) == 2
        assert result.page.items[0].symbol == "AAPL"
        assert result.page.items[1].symbol == "MSFT"

    def test_passes_scan_id_to_repository(self):
        repo = FakeScanResultRepository()
        uow = FakeUnitOfWork(scan_results=repo)
        setup_scan(uow, "scan-xyz")
        uc = GetScanResultsUseCase()

        uc.execute(uow, _make_query(scan_id="scan-xyz"))

        assert repo.last_query_args["scan_id"] == "scan-xyz"

    def test_passes_query_spec_to_repository(self):
        repo = FakeScanResultRepository()
        uow = FakeUnitOfWork(scan_results=repo)
        setup_scan(uow)
        uc = GetScanResultsUseCase()

        spec = QuerySpec(
            sort=SortSpec(field="rs_rating", order=SortOrder.ASC),
            page=PageSpec(page=2, per_page=25),
        )
        uc.execute(uow, _make_query(query_spec=spec))

        assert repo.last_query_args["spec"] is spec

    def test_passes_include_sparklines_flag(self):
        repo = FakeScanResultRepository()
        uow = FakeUnitOfWork(scan_results=repo)
        setup_scan(uow)
        uc = GetScanResultsUseCase()

        uc.execute(uow, _make_query(include_sparklines=False))

        assert repo.last_query_args["include_sparklines"] is False

    def test_empty_results_returns_empty_page(self):
        uow = FakeUnitOfWork(scan_results=FakeScanResultRepository(items=[]))
        setup_scan(uow)
        uc = GetScanResultsUseCase()

        result = uc.execute(uow, _make_query())

        assert result.page.total == 0
        assert len(result.page.items) == 0

    def test_pagination_metadata(self):
        items = [make_domain_item(f"SYM{i}") for i in range(75)]
        uow = FakeUnitOfWork(scan_results=FakeScanResultRepository(items=items))
        setup_scan(uow)
        uc = GetScanResultsUseCase()

        spec = QuerySpec(page=PageSpec(page=2, per_page=25))
        result = uc.execute(uow, _make_query(query_spec=spec))

        assert result.page.total == 75
        assert result.page.page == 2
        assert result.page.per_page == 25
        assert result.page.total_pages == 3
        assert len(result.page.items) == 25


class TestScanNotFound:
    """Use case raises EntityNotFoundError for missing scans."""

    def test_nonexistent_scan_raises_not_found(self):
        uow = FakeUnitOfWork()
        uc = GetScanResultsUseCase()

        with pytest.raises(EntityNotFoundError, match="Scan.*not-a-scan"):
            uc.execute(uow, _make_query(scan_id="not-a-scan"))

    def test_not_found_error_has_entity_and_identifier(self):
        uow = FakeUnitOfWork()
        uc = GetScanResultsUseCase()

        with pytest.raises(EntityNotFoundError) as exc_info:
            uc.execute(uow, _make_query(scan_id="missing"))

        assert exc_info.value.entity == "Scan"
        assert exc_info.value.identifier == "missing"


class TestDefaultQuerySpec:
    """Default query spec uses sensible defaults."""

    def test_default_query_spec_applied(self):
        repo = FakeScanResultRepository()
        uow = FakeUnitOfWork(scan_results=repo)
        setup_scan(uow)
        uc = GetScanResultsUseCase()

        uc.execute(uow, _make_query())

        spec = repo.last_query_args["spec"]
        assert spec.sort.field == "composite_score"
        assert spec.sort.order == SortOrder.DESC
        assert spec.page.page == 1
        assert spec.page.per_page == 50

    def test_default_include_sparklines_is_true(self):
        repo = FakeScanResultRepository()
        uow = FakeUnitOfWork(scan_results=repo)
        setup_scan(uow)
        uc = GetScanResultsUseCase()

        uc.execute(uow, _make_query())

        assert repo.last_query_args["include_sparklines"] is True


# ── Dual-source routing ─────────────────────────────────────────────────


AS_OF = date(2026, 2, 17)


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


class TestDualSourceRouting:
    """Verify the use case routes to the correct data source."""

    def test_bound_scan_queries_feature_store(self):
        """Scan with feature_run_id routes to feature store."""
        feature_store = FakeFeatureStoreRepository()
        legacy_repo = FakeScanResultRepository()
        uow = FakeUnitOfWork(scan_results=legacy_repo, feature_store=feature_store)
        _setup_bound_scan(uow, feature_store)
        uc = GetScanResultsUseCase()

        result = uc.execute(uow, _make_query(scan_id="scan-bound"))

        # Feature store was used (returned items)
        assert result.page.total == 2
        assert result.page.items[0].symbol in ("AAPL", "MSFT")
        # Legacy repo was NOT consulted
        assert legacy_repo.last_query_args is None

    def test_unbound_scan_queries_legacy(self):
        """Scan without feature_run_id routes to legacy scan_results."""
        feature_store = FakeFeatureStoreRepository()
        legacy_repo = FakeScanResultRepository(
            items=[make_domain_item("GOOGL")]
        )
        uow = FakeUnitOfWork(scan_results=legacy_repo, feature_store=feature_store)
        setup_scan(uow)  # creates "scan-123" without feature_run_id
        uc = GetScanResultsUseCase()

        result = uc.execute(uow, _make_query())

        # Legacy repo was used
        assert legacy_repo.last_query_args is not None
        assert legacy_repo.last_query_args["scan_id"] == "scan-123"
        assert result.page.total == 1
        assert result.page.items[0].symbol == "GOOGL"

    def test_bound_scan_returns_result_page(self):
        """Feature store path returns a proper ResultPage."""
        feature_store = FakeFeatureStoreRepository()
        uow = FakeUnitOfWork(feature_store=feature_store)
        _setup_bound_scan(uow, feature_store)
        uc = GetScanResultsUseCase()

        result = uc.execute(uow, _make_query(scan_id="scan-bound"))

        assert isinstance(result.page, ResultPage)
        assert result.page.page == 1
        assert result.page.per_page == 50

    def test_bound_scan_passes_query_spec(self):
        """QuerySpec is forwarded to the feature store bridge method."""
        feature_store = FakeFeatureStoreRepository()
        uow = FakeUnitOfWork(feature_store=feature_store)
        _setup_bound_scan(uow, feature_store)
        uc = GetScanResultsUseCase()

        spec = QuerySpec(page=PageSpec(page=1, per_page=10))
        result = uc.execute(uow, _make_query(
            scan_id="scan-bound", query_spec=spec,
        ))

        assert result.page.per_page == 10

    def test_bound_scan_passes_include_sparklines(self):
        """include_sparklines flag is forwarded to feature store."""
        feature_store = FakeFeatureStoreRepository()
        uow = FakeUnitOfWork(feature_store=feature_store)
        _setup_bound_scan(uow, feature_store)
        uc = GetScanResultsUseCase()

        # Just verify it doesn't crash — actual sparkline suppression is
        # tested in the integration test.
        result = uc.execute(uow, _make_query(
            scan_id="scan-bound", include_sparklines=False,
        ))
        assert result.page.total == 2

    def test_bound_scan_fallback_on_missing_run(self):
        """If feature_run_id points to a deleted run, fall back to legacy."""
        feature_store = FakeFeatureStoreRepository()
        legacy_repo = FakeScanResultRepository(
            items=[make_domain_item("FALLBACK")]
        )
        uow = FakeUnitOfWork(scan_results=legacy_repo, feature_store=feature_store)
        # Bind to run_id=999 which doesn't exist in feature store
        uow.scans.create(
            scan_id="scan-orphan", status="completed", feature_run_id=999
        )
        uc = GetScanResultsUseCase()

        result = uc.execute(uow, _make_query(scan_id="scan-orphan"))

        # Fell back to legacy
        assert legacy_repo.last_query_args is not None
        assert legacy_repo.last_query_args["scan_id"] == "scan-orphan"
        assert result.page.items[0].symbol == "FALLBACK"
