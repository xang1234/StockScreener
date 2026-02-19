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


def _setup_bound_scan(uow, feature_store, scan_id="scan-123", run_id=1):
    """Create a scan bound to a feature run, with rows for peer testing."""
    uow.scans.create(scan_id=scan_id, status="completed", feature_run_id=run_id)
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
        feature_store = FakeFeatureStoreRepository()
        uow = FakeUnitOfWork(feature_store=feature_store)
        _setup_bound_scan(uow, feature_store)
        uc = GetPeersUseCase()

        result = uc.execute(uow, _make_query(symbol="NVDA"))

        assert isinstance(result, GetPeersResult)
        assert result.peer_type == PeerType.INDUSTRY
        assert result.group_name == "Semiconductors"
        symbols = {p.symbol for p in result.peers}
        assert "NVDA" in symbols
        assert "AMD" in symbols

    def test_empty_group_returns_empty_peers(self):
        """Symbol with no group value returns empty result."""
        feature_store = FakeFeatureStoreRepository()
        uow = FakeUnitOfWork(feature_store=feature_store)
        uow.scans.create(scan_id="scan-123", status="completed", feature_run_id=1)
        # Row with no ibd_industry_group
        feature_store.upsert_snapshot_rows(1, [
            FeatureRow(
                run_id=1, symbol="AAPL", as_of_date=AS_OF,
                composite_score=85.0, overall_rating=4, passes_count=1,
                details={
                    "composite_score": 85.0, "rating": "Buy",
                    "current_price": 150.0,
                    "screeners_run": ["minervini"],
                    "composite_method": "weighted_average",
                    "screeners_passed": 1, "screeners_total": 1,
                },
            ),
        ])
        uc = GetPeersUseCase()

        result = uc.execute(uow, _make_query(symbol="AAPL"))

        assert result.peers == ()
        assert result.group_name is None

    def test_symbol_not_found_raises_error(self):
        feature_store = FakeFeatureStoreRepository()
        uow = FakeUnitOfWork(feature_store=feature_store)
        _setup_bound_scan(uow, feature_store)
        uc = GetPeersUseCase()

        with pytest.raises(EntityNotFoundError, match="ScanResult.*ZZZZ"):
            uc.execute(uow, _make_query(symbol="ZZZZ"))

    def test_sector_peers(self):
        """Sector peer type returns all stocks in the same sector."""
        feature_store = FakeFeatureStoreRepository()
        uow = FakeUnitOfWork(feature_store=feature_store)
        _setup_bound_scan(uow, feature_store)
        uc = GetPeersUseCase()

        result = uc.execute(uow, _make_query(
            symbol="AAPL", peer_type=PeerType.SECTOR,
        ))

        # All four stocks are in "Technology" sector
        assert result.group_name == "Technology"
        assert len(result.peers) == 4


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


class TestUnboundScanFallback:
    """Scans without a feature run fall back to scan_results."""

    def test_unbound_scan_reads_target_from_scan_results(self):
        """Scan without feature_run_id looks up the target from scan_results."""
        items = [
            make_domain_item("AAPL", ibd_industry_group="Consumer Electronics", gics_sector="Technology"),
            make_domain_item("MSFT", score=70.0, ibd_industry_group="Software", gics_sector="Technology"),
        ]
        scan_results = FakeScanResultRepository(items=items)
        uow = FakeUnitOfWork(scan_results=scan_results)
        uow.scans.create(scan_id="scan-legacy", status="completed")
        uc = GetPeersUseCase()

        result = uc.execute(uow, _make_query(scan_id="scan-legacy", symbol="AAPL"))

        # Target was found; group extracted from extended_fields
        assert result.group_name == "Consumer Electronics"

    def test_unbound_scan_symbol_not_found_raises_error(self):
        """Fallback path raises EntityNotFoundError for missing symbol."""
        scan_results = FakeScanResultRepository(items=[make_domain_item("AAPL")])
        uow = FakeUnitOfWork(scan_results=scan_results)
        uow.scans.create(scan_id="scan-legacy", status="completed")
        uc = GetPeersUseCase()

        with pytest.raises(EntityNotFoundError, match="ScanResult.*ZZZZ"):
            uc.execute(uow, _make_query(scan_id="scan-legacy", symbol="ZZZZ"))


class TestFeatureStoreRouting:
    """Verify the use case queries the feature store correctly."""

    def test_bound_scan_queries_feature_store(self):
        """Scan with feature_run_id routes to feature store for both lookups."""
        feature_store = FakeFeatureStoreRepository()
        uow = FakeUnitOfWork(feature_store=feature_store)
        _setup_bound_scan(uow, feature_store, scan_id="scan-bound")
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

    def test_missing_feature_run_raises_not_found(self):
        """If feature_run_id points to a deleted run, raise EntityNotFoundError."""
        feature_store = FakeFeatureStoreRepository()
        uow = FakeUnitOfWork(feature_store=feature_store)
        uow.scans.create(
            scan_id="scan-orphan", status="completed", feature_run_id=999
        )
        uc = GetPeersUseCase()

        with pytest.raises(EntityNotFoundError, match="FeatureRun"):
            uc.execute(uow, _make_query(scan_id="scan-orphan", symbol="NVDA"))

    def test_bound_scan_symbol_not_found_raises_error(self):
        """Feature store path raises EntityNotFoundError for missing symbol."""
        feature_store = FakeFeatureStoreRepository()
        uow = FakeUnitOfWork(feature_store=feature_store)
        _setup_bound_scan(uow, feature_store, scan_id="scan-bound")
        uc = GetPeersUseCase()

        with pytest.raises(EntityNotFoundError, match="ScanResult.*ZZZZ"):
            uc.execute(uow, _make_query(scan_id="scan-bound", symbol="ZZZZ"))
