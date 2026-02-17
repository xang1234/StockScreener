"""Unit tests for GetScanResultsUseCase — pure in-memory, no infrastructure."""

import pytest

from app.domain.common.errors import EntityNotFoundError
from app.domain.common.uow import UnitOfWork
from app.domain.scanning.filter_spec import (
    FilterMode,
    FilterSpec,
    PageSpec,
    QuerySpec,
    SortOrder,
    SortSpec,
)
from app.domain.scanning.models import ResultPage, ScanResultItemDomain
from app.domain.scanning.ports import (
    ScanRepository,
    ScanResultRepository,
    UniverseRepository,
)
from app.use_cases.scanning.get_scan_results import (
    GetScanResultsQuery,
    GetScanResultsResult,
    GetScanResultsUseCase,
)


# ── Fakes ────────────────────────────────────────────────────────────────


class _ScanRecord:
    """Minimal in-memory scan record."""

    def __init__(self, **fields):
        for k, v in fields.items():
            setattr(self, k, v)


class FakeScanRepository(ScanRepository):
    def __init__(self):
        self.rows: list[_ScanRecord] = []

    def create(self, *, scan_id: str, **fields) -> _ScanRecord:
        rec = _ScanRecord(scan_id=scan_id, **fields)
        self.rows.append(rec)
        return rec

    def get_by_scan_id(self, scan_id: str) -> _ScanRecord | None:
        return next((r for r in self.rows if r.scan_id == scan_id), None)

    def get_by_idempotency_key(self, key: str) -> _ScanRecord | None:
        return None

    def update_status(self, scan_id: str, status: str, **fields) -> None:
        pass


def _make_domain_item(symbol: str = "AAPL", score: float = 85.0) -> ScanResultItemDomain:
    return ScanResultItemDomain(
        symbol=symbol,
        composite_score=score,
        rating="Buy",
        current_price=150.0,
        screener_outputs={},
        screeners_run=["minervini"],
        composite_method="weighted_average",
        screeners_passed=1,
        screeners_total=1,
        extended_fields={"company_name": f"{symbol} Inc"},
    )


class FakeScanResultRepository(ScanResultRepository):
    """In-memory scan result repo that returns canned data from query()."""

    def __init__(self, items: list[ScanResultItemDomain] | None = None):
        self._items = items or []
        self.last_query_args: dict | None = None

    def bulk_insert(self, rows: list[dict]) -> int:
        return len(rows)

    def persist_orchestrator_results(
        self, scan_id: str, results: list[tuple[str, dict]]
    ) -> int:
        return len(results)

    def count_by_scan_id(self, scan_id: str) -> int:
        return len(self._items)

    def query(self, scan_id, spec, *, include_sparklines=True):
        self.last_query_args = {
            "scan_id": scan_id,
            "spec": spec,
            "include_sparklines": include_sparklines,
        }
        page_items = self._items[spec.page.offset : spec.page.offset + spec.page.limit]
        return ResultPage(
            items=tuple(page_items),
            total=len(self._items),
            page=spec.page.page,
            per_page=spec.page.per_page,
        )


class FakeUniverseRepository(UniverseRepository):
    def resolve_symbols(self, universe_def: object) -> list[str]:
        return []


class FakeUnitOfWork(UnitOfWork):
    def __init__(
        self,
        *,
        scans: FakeScanRepository | None = None,
        scan_results: FakeScanResultRepository | None = None,
    ):
        self.scans = scans or FakeScanRepository()
        self.scan_results = scan_results or FakeScanResultRepository()
        self.universe = FakeUniverseRepository()
        self.committed = 0
        self.rolled_back = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.rollback()

    def commit(self):
        self.committed += 1

    def rollback(self):
        self.rolled_back += 1


# ── Helpers ──────────────────────────────────────────────────────────────


def _make_query(**overrides) -> GetScanResultsQuery:
    defaults = dict(scan_id="scan-123")
    defaults.update(overrides)
    return GetScanResultsQuery(**defaults)


def _setup_scan(uow: FakeUnitOfWork, scan_id: str = "scan-123") -> None:
    """Pre-populate a scan record so the use case doesn't raise NotFound."""
    uow.scans.create(scan_id=scan_id, status="completed")


# ── Tests ────────────────────────────────────────────────────────────────


class TestHappyPath:
    """Core business logic for retrieving scan results."""

    def test_returns_result_page(self):
        items = [_make_domain_item("AAPL"), _make_domain_item("MSFT")]
        uow = FakeUnitOfWork(scan_results=FakeScanResultRepository(items))
        _setup_scan(uow)
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
        _setup_scan(uow, "scan-xyz")
        uc = GetScanResultsUseCase()

        uc.execute(uow, _make_query(scan_id="scan-xyz"))

        assert repo.last_query_args["scan_id"] == "scan-xyz"

    def test_passes_query_spec_to_repository(self):
        repo = FakeScanResultRepository()
        uow = FakeUnitOfWork(scan_results=repo)
        _setup_scan(uow)
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
        _setup_scan(uow)
        uc = GetScanResultsUseCase()

        uc.execute(uow, _make_query(include_sparklines=False))

        assert repo.last_query_args["include_sparklines"] is False

    def test_empty_results_returns_empty_page(self):
        uow = FakeUnitOfWork(scan_results=FakeScanResultRepository([]))
        _setup_scan(uow)
        uc = GetScanResultsUseCase()

        result = uc.execute(uow, _make_query())

        assert result.page.total == 0
        assert len(result.page.items) == 0

    def test_pagination_metadata(self):
        items = [_make_domain_item(f"SYM{i}") for i in range(75)]
        uow = FakeUnitOfWork(scan_results=FakeScanResultRepository(items))
        _setup_scan(uow)
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
        _setup_scan(uow)
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
        _setup_scan(uow)
        uc = GetScanResultsUseCase()

        uc.execute(uow, _make_query())

        assert repo.last_query_args["include_sparklines"] is True
