"""Unit tests for GetPeersUseCase — pure in-memory, no infrastructure."""

from datetime import date

import pytest

from app.domain.common.errors import EntityNotFoundError
from app.domain.feature_store.models import FeatureRow
from app.domain.scanning.models import PeerType
from app.use_cases.scanning.get_peers import (
    GetPeersQuery,
    GetPeersResult,
    GetPeersUseCase,
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


def _make_query(**overrides) -> GetPeersQuery:
    defaults = dict(scan_id="scan-123", symbol="AAPL", peer_type=PeerType.INDUSTRY)
    defaults.update(overrides)
    return GetPeersQuery(**defaults)


def _make_feature_row(
    symbol: str,
    score: float = 85.0,
    ibd_industry_group: str = "Semiconductors",
    gics_sector: str = "Technology",
) -> FeatureRow:
    """Build a FeatureRow with classification fields for peer tests."""
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
            "ibd_industry_group": ibd_industry_group,
            "gics_sector": gics_sector,
        },
    )


def _setup_bound_scan(uow, feature_store, run_id=1):
    """Create a scan bound to a feature run, with rows for peer testing."""
    uow.scans.create(scan_id="scan-bound", status="completed", feature_run_id=run_id)
    feature_store.upsert_snapshot_rows(
        run_id,
        [
            _make_feature_row("AAPL", ibd_industry_group="Consumer Electronics", gics_sector="Technology"),
            _make_feature_row("MSFT", score=70.0, ibd_industry_group="Software", gics_sector="Technology"),
            _make_feature_row("NVDA", ibd_industry_group="Semiconductors", gics_sector="Technology"),
            _make_feature_row("AMD", score=60.0, ibd_industry_group="Semiconductors", gics_sector="Technology"),
        ],
    )


# ── Tests ────────────────────────────────────────────────────────────────


class TestHappyPath:
    """Core business logic for retrieving peers."""

    def test_returns_peers_result(self):
        items = [
            make_domain_item("AAPL", ibd_industry_group="Consumer Electronics"),
            make_domain_item("MSFT", ibd_industry_group="Software"),
        ]
        uow = FakeUnitOfWork(scan_results=FakeScanResultRepository(items=items))
        setup_scan(uow)
        uc = GetPeersUseCase()

        result = uc.execute(uow, _make_query(symbol="AAPL"))

        assert isinstance(result, GetPeersResult)
        assert result.peer_type == PeerType.INDUSTRY

    def test_empty_group_returns_empty_peers(self):
        """Symbol with no group value returns empty result."""
        items = [make_domain_item("AAPL")]  # no ibd_industry_group
        uow = FakeUnitOfWork(scan_results=FakeScanResultRepository(items=items))
        setup_scan(uow)
        uc = GetPeersUseCase()

        result = uc.execute(uow, _make_query(symbol="AAPL"))

        assert result.peers == ()
        assert result.group_name is None

    def test_symbol_not_found_raises_error(self):
        uow = FakeUnitOfWork(scan_results=FakeScanResultRepository(items=[]))
        setup_scan(uow)
        uc = GetPeersUseCase()

        with pytest.raises(EntityNotFoundError, match="ScanResult.*AAPL"):
            uc.execute(uow, _make_query(symbol="AAPL"))


class TestScanNotFound:
    """Use case raises EntityNotFoundError for missing scans."""

    def test_nonexistent_scan_raises_not_found(self):
        uow = FakeUnitOfWork()
        uc = GetPeersUseCase()

        with pytest.raises(EntityNotFoundError, match="Scan.*not-a-scan"):
            uc.execute(uow, _make_query(scan_id="not-a-scan"))

    def test_not_found_error_has_entity_and_identifier(self):
        uow = FakeUnitOfWork()
        uc = GetPeersUseCase()

        with pytest.raises(EntityNotFoundError) as exc_info:
            uc.execute(uow, _make_query(scan_id="missing"))

        assert exc_info.value.entity == "Scan"
        assert exc_info.value.identifier == "missing"


class TestDualSourceRouting:
    """Verify the use case routes to the correct data source."""

    def test_bound_scan_queries_feature_store(self):
        """Scan with feature_run_id routes to feature store for both lookups."""
        feature_store = FakeFeatureStoreRepository()
        legacy_repo = FakeScanResultRepository()
        uow = FakeUnitOfWork(scan_results=legacy_repo, feature_store=feature_store)
        _setup_bound_scan(uow, feature_store)
        uc = GetPeersUseCase()

        # NVDA and AMD are both in "Semiconductors"
        result = uc.execute(uow, _make_query(
            scan_id="scan-bound", symbol="NVDA", peer_type=PeerType.INDUSTRY,
        ))

        assert result.group_name == "Semiconductors"
        symbols = {p.symbol for p in result.peers}
        assert "NVDA" in symbols
        assert "AMD" in symbols
        # Non-semiconductors excluded
        assert "AAPL" not in symbols
        assert "MSFT" not in symbols

    def test_bound_scan_sector_peers(self):
        """Feature store path works for sector peer type too."""
        feature_store = FakeFeatureStoreRepository()
        uow = FakeUnitOfWork(feature_store=feature_store)
        _setup_bound_scan(uow, feature_store)
        uc = GetPeersUseCase()

        result = uc.execute(uow, _make_query(
            scan_id="scan-bound", symbol="AAPL", peer_type=PeerType.SECTOR,
        ))

        # All four stocks are in "Technology" sector
        assert result.group_name == "Technology"
        assert len(result.peers) == 4

    def test_unbound_scan_queries_legacy(self):
        """Scan without feature_run_id routes to legacy scan_results."""
        items = [make_domain_item("AAPL", ibd_industry_group="Consumer Electronics")]
        legacy_repo = FakeScanResultRepository(items=items)
        uow = FakeUnitOfWork(scan_results=legacy_repo)
        setup_scan(uow)
        uc = GetPeersUseCase()

        result = uc.execute(uow, _make_query(symbol="AAPL"))

        # Legacy repo's get_peers_by_industry returns () by default
        assert result.group_name == "Consumer Electronics"
        assert result.peers == ()

    def test_bound_scan_fallback_on_missing_run(self):
        """If feature_run_id points to a deleted run, fall back to legacy."""
        feature_store = FakeFeatureStoreRepository()
        legacy_repo = FakeScanResultRepository(
            items=[make_domain_item("FALLBACK", ibd_industry_group="Test Group")]
        )
        uow = FakeUnitOfWork(scan_results=legacy_repo, feature_store=feature_store)
        uow.scans.create(
            scan_id="scan-orphan", status="completed", feature_run_id=999
        )
        uc = GetPeersUseCase()

        result = uc.execute(uow, _make_query(
            scan_id="scan-orphan", symbol="FALLBACK",
        ))

        # Fell back to legacy — target found, peers from legacy (empty)
        assert result.group_name == "Test Group"
        assert result.peers == ()

    def test_bound_scan_symbol_not_found_raises_error(self):
        """Feature store path raises EntityNotFoundError for missing symbol."""
        feature_store = FakeFeatureStoreRepository()
        uow = FakeUnitOfWork(feature_store=feature_store)
        _setup_bound_scan(uow, feature_store)
        uc = GetPeersUseCase()

        with pytest.raises(EntityNotFoundError, match="ScanResult.*ZZZZ"):
            uc.execute(uow, _make_query(scan_id="scan-bound", symbol="ZZZZ"))
