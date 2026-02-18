"""Tests for ExplainStockUseCase with dual-source support."""

from datetime import date

import pytest

from app.domain.common.errors import EntityNotFoundError
from app.domain.feature_store.models import FeatureRow, FeatureRowWrite
from app.domain.scanning.models import ScreenerOutputDomain, ScanResultItemDomain
from app.use_cases.scanning.explain_stock import (
    ExplainStockQuery,
    ExplainStockUseCase,
)
from tests.unit.use_cases.conftest import (
    FakeScan,
    FakeScanResultRepository,
    FakeFeatureStoreRepository,
    FakeUnitOfWork,
)


def _make_legacy_item(symbol: str = "AAPL") -> ScanResultItemDomain:
    """Build a ScanResultItemDomain with screener_outputs for legacy path tests."""
    return ScanResultItemDomain(
        symbol=symbol,
        composite_score=75.0,
        rating="Buy",
        current_price=150.0,
        screener_outputs={
            "minervini": ScreenerOutputDomain(
                screener_name="minervini",
                score=75.0,
                passes=True,
                rating="Buy",
                breakdown={"rs_rating": 18, "stage": 15},
                details={},
            ),
        },
        screeners_run=["minervini"],
        composite_method="weighted_average",
        screeners_passed=1,
        screeners_total=1,
    )


class TestExplainStockLegacyPath:
    """Tests that the existing legacy path still works."""

    def test_legacy_path_returns_explanation(self):
        item = _make_legacy_item()
        scan_results = FakeScanResultRepository(items=[item])
        uow = FakeUnitOfWork(scan_results=scan_results)
        uow.scans.create(scan_id="scan-1", status="completed")

        uc = ExplainStockUseCase()
        result = uc.execute(uow, ExplainStockQuery(scan_id="scan-1", symbol="AAPL"))

        assert result.explanation.symbol == "AAPL"
        assert result.explanation.composite_score == 75.0
        assert len(result.explanation.screener_explanations) == 1
        assert result.explanation.screener_explanations[0].screener_name == "minervini"

    def test_scan_not_found_raises(self):
        uow = FakeUnitOfWork()
        uc = ExplainStockUseCase()
        with pytest.raises(EntityNotFoundError, match="Scan"):
            uc.execute(uow, ExplainStockQuery(scan_id="nope", symbol="AAPL"))

    def test_symbol_not_found_raises(self):
        uow = FakeUnitOfWork()
        uow.scans.create(scan_id="scan-1", status="completed")
        uc = ExplainStockUseCase()
        with pytest.raises(EntityNotFoundError, match="ScanResult"):
            uc.execute(uow, ExplainStockQuery(scan_id="scan-1", symbol="NOPE"))


class TestExplainStockFeatureStorePath:
    """Tests for the new feature-store-backed explain path."""

    def test_feature_store_path_extracts_screeners(self):
        """When scan has feature_run_id, explain reads from feature store."""
        store = FakeFeatureStoreRepository()
        uow = FakeUnitOfWork(feature_store=store)

        # Create scan with feature_run_id
        uow.scans.create(scan_id="scan-fs", status="completed", feature_run_id=42)

        # Populate feature store with screener outputs in details
        store._rows[42] = [
            FeatureRow(
                run_id=42,
                symbol="NVDA",
                as_of_date=date(2026, 2, 18),
                composite_score=82.0,
                overall_rating=4,
                passes_count=2,
                details={
                    "screeners_run": ["minervini", "canslim"],
                    "composite_method": "weighted_average",
                    "screeners_passed": 2,
                    "screeners_total": 2,
                    "current_price": 850.0,
                    "details": {
                        "screeners": {
                            "minervini": {
                                "score": 85.0,
                                "passes": True,
                                "rating": "Strong Buy",
                                "breakdown": {"rs_rating": 20, "stage": 20},
                                "details": {},
                            },
                            "canslim": {
                                "score": 70.0,
                                "passes": True,
                                "rating": "Buy",
                                "breakdown": {"current_earnings": 18},
                                "details": {},
                            },
                        }
                    },
                },
            ),
        ]

        uc = ExplainStockUseCase()
        result = uc.execute(uow, ExplainStockQuery(scan_id="scan-fs", symbol="NVDA"))

        assert result.explanation.symbol == "NVDA"
        assert result.explanation.composite_score == 82.0
        assert len(result.explanation.screener_explanations) == 2

        names = {se.screener_name for se in result.explanation.screener_explanations}
        assert names == {"minervini", "canslim"}

    def test_feature_store_fallback_to_legacy(self):
        """When symbol not in feature store, falls back to legacy scan_results."""
        item = _make_legacy_item("AAPL")
        scan_results = FakeScanResultRepository(items=[item])
        store = FakeFeatureStoreRepository()
        uow = FakeUnitOfWork(scan_results=scan_results, feature_store=store)

        # Scan has feature_run_id, but AAPL not in feature store run 42
        uow.scans.create(scan_id="scan-fb", status="completed", feature_run_id=42)
        store._rows[42] = []  # empty feature store for this run

        uc = ExplainStockUseCase()
        result = uc.execute(uow, ExplainStockQuery(scan_id="scan-fb", symbol="AAPL"))

        # Should fall back to legacy and still return explanation
        assert result.explanation.symbol == "AAPL"
        assert result.explanation.composite_score == 75.0

    def test_feature_store_symbol_not_found_anywhere(self):
        """Symbol not in feature store AND not in legacy → EntityNotFoundError."""
        store = FakeFeatureStoreRepository()
        uow = FakeUnitOfWork(feature_store=store)
        uow.scans.create(scan_id="scan-nf", status="completed", feature_run_id=42)
        store._rows[42] = []

        uc = ExplainStockUseCase()
        with pytest.raises(EntityNotFoundError, match="ScanResult"):
            uc.execute(uow, ExplainStockQuery(scan_id="scan-nf", symbol="GHOST"))

    def test_case_insensitive_symbol_lookup(self):
        """Symbol matching should be case-insensitive."""
        store = FakeFeatureStoreRepository()
        uow = FakeUnitOfWork(feature_store=store)
        uow.scans.create(scan_id="scan-ci", status="completed", feature_run_id=42)

        store._rows[42] = [
            FeatureRow(
                run_id=42, symbol="AAPL", as_of_date=date(2026, 2, 18),
                composite_score=75.0, overall_rating=4, passes_count=1,
                details={
                    "screeners_run": ["minervini"],
                    "composite_method": "weighted_average",
                    "screeners_passed": 1,
                    "screeners_total": 1,
                    "details": {"screeners": {}},
                },
            ),
        ]

        uc = ExplainStockUseCase()
        # Query with lowercase
        result = uc.execute(uow, ExplainStockQuery(scan_id="scan-ci", symbol="aapl"))
        assert result.explanation.symbol == "AAPL"
