"""Unit tests for ExportScanResultsUseCase — pure in-memory, no infrastructure."""

from datetime import date

import pytest

from app.domain.common.errors import EntityNotFoundError
from app.domain.feature_store.models import FeatureRow
from app.domain.scanning.models import ExportFormat
from app.use_cases.scanning.export_scan_results import (
    ExportScanResultsQuery,
    ExportScanResultsResult,
    ExportScanResultsUseCase,
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


def _make_query(**overrides) -> ExportScanResultsQuery:
    defaults = dict(scan_id="scan-123")
    defaults.update(overrides)
    return ExportScanResultsQuery(**defaults)


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
    """Core business logic for exporting scan results."""

    def test_returns_csv_bytes(self):
        items = [make_domain_item("AAPL"), make_domain_item("MSFT")]
        uow = FakeUnitOfWork(scan_results=FakeScanResultRepository(items=items))
        setup_scan(uow)
        uc = ExportScanResultsUseCase()

        result = uc.execute(uow, _make_query())

        assert isinstance(result, ExportScanResultsResult)
        assert result.media_type == "text/csv"
        assert result.filename.startswith("scan_")
        assert result.filename.endswith(".csv")
        # CSV content starts with UTF-8 BOM
        assert result.content.startswith(b"\xef\xbb\xbf")

    def test_csv_contains_header_and_data_rows(self):
        items = [make_domain_item("AAPL")]
        uow = FakeUnitOfWork(scan_results=FakeScanResultRepository(items=items))
        setup_scan(uow)
        uc = ExportScanResultsUseCase()

        result = uc.execute(uow, _make_query())

        # Decode and check
        csv_text = result.content.decode("utf-8-sig")
        lines = csv_text.strip().split("\n")
        assert len(lines) == 2  # header + 1 data row
        assert "Symbol" in lines[0]
        assert "AAPL" in lines[1]

    def test_empty_scan_exports_header_only(self):
        uow = FakeUnitOfWork(scan_results=FakeScanResultRepository(items=[]))
        setup_scan(uow)
        uc = ExportScanResultsUseCase()

        result = uc.execute(uow, _make_query())

        csv_text = result.content.decode("utf-8-sig")
        lines = csv_text.strip().split("\n")
        assert len(lines) == 1  # header only


class TestScanNotFound:
    """Use case raises EntityNotFoundError for missing scans."""

    def test_nonexistent_scan_raises_not_found(self):
        uow = FakeUnitOfWork()
        uc = ExportScanResultsUseCase()

        with pytest.raises(EntityNotFoundError, match="Scan.*not-a-scan"):
            uc.execute(uow, _make_query(scan_id="not-a-scan"))

    def test_not_found_error_has_entity_and_identifier(self):
        uow = FakeUnitOfWork()
        uc = ExportScanResultsUseCase()

        with pytest.raises(EntityNotFoundError) as exc_info:
            uc.execute(uow, _make_query(scan_id="missing"))

        assert exc_info.value.entity == "Scan"
        assert exc_info.value.identifier == "missing"


class TestDualSourceRouting:
    """Verify the use case routes to the correct data source."""

    def test_bound_scan_queries_feature_store(self):
        """Scan with feature_run_id routes to feature store for export."""
        feature_store = FakeFeatureStoreRepository()
        legacy_repo = FakeScanResultRepository()
        uow = FakeUnitOfWork(scan_results=legacy_repo, feature_store=feature_store)
        _setup_bound_scan(uow, feature_store)
        uc = ExportScanResultsUseCase()

        result = uc.execute(uow, _make_query(scan_id="scan-bound"))

        csv_text = result.content.decode("utf-8-sig")
        lines = csv_text.strip().split("\n")
        # Header + 2 data rows from feature store
        assert len(lines) == 3
        assert "AAPL" in csv_text
        assert "MSFT" in csv_text

    def test_unbound_scan_queries_legacy(self):
        """Scan without feature_run_id routes to legacy scan_results."""
        items = [make_domain_item("GOOGL")]
        legacy_repo = FakeScanResultRepository(items=items)
        uow = FakeUnitOfWork(scan_results=legacy_repo)
        setup_scan(uow)
        uc = ExportScanResultsUseCase()

        result = uc.execute(uow, _make_query())

        csv_text = result.content.decode("utf-8-sig")
        assert "GOOGL" in csv_text

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
        uc = ExportScanResultsUseCase()

        result = uc.execute(uow, _make_query(scan_id="scan-orphan"))

        csv_text = result.content.decode("utf-8-sig")
        assert "FALLBACK" in csv_text
