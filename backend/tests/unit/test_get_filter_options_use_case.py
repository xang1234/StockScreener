"""Unit tests for GetFilterOptionsUseCase — pure in-memory, no infrastructure."""

import pytest

from app.domain.common.errors import EntityNotFoundError
from app.domain.common.uow import UnitOfWork
from app.domain.scanning.models import FilterOptions
from app.domain.scanning.ports import (
    ScanRepository,
    ScanResultRepository,
    UniverseRepository,
)
from app.use_cases.scanning.get_filter_options import (
    GetFilterOptionsQuery,
    GetFilterOptionsResult,
    GetFilterOptionsUseCase,
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


class FakeScanResultRepository(ScanResultRepository):
    """In-memory scan result repo that returns canned FilterOptions."""

    def __init__(self, options: FilterOptions | None = None):
        self._options = options or FilterOptions(
            ibd_industries=(), gics_sectors=(), ratings=()
        )
        self.last_filter_scan_id: str | None = None

    def bulk_insert(self, rows: list[dict]) -> int:
        return len(rows)

    def persist_orchestrator_results(
        self, scan_id: str, results: list[tuple[str, dict]]
    ) -> int:
        return len(results)

    def count_by_scan_id(self, scan_id: str) -> int:
        return 0

    def query(self, scan_id, spec, *, include_sparklines=True):
        raise NotImplementedError("Not needed for filter options tests")

    def get_filter_options(self, scan_id: str) -> FilterOptions:
        self.last_filter_scan_id = scan_id
        return self._options


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


def _make_query(**overrides) -> GetFilterOptionsQuery:
    defaults = dict(scan_id="scan-123")
    defaults.update(overrides)
    return GetFilterOptionsQuery(**defaults)


def _setup_scan(uow: FakeUnitOfWork, scan_id: str = "scan-123") -> None:
    """Pre-populate a scan record so the use case doesn't raise NotFound."""
    uow.scans.create(scan_id=scan_id, status="completed")


# ── Tests ────────────────────────────────────────────────────────────────


class TestHappyPath:
    """Core business logic for retrieving filter options."""

    def test_returns_filter_options(self):
        options = FilterOptions(
            ibd_industries=("Electronics", "Software"),
            gics_sectors=("Information Technology", "Healthcare"),
            ratings=("Buy", "Strong Buy"),
        )
        uow = FakeUnitOfWork(scan_results=FakeScanResultRepository(options))
        _setup_scan(uow)
        uc = GetFilterOptionsUseCase()

        result = uc.execute(uow, _make_query())

        assert isinstance(result, GetFilterOptionsResult)
        assert result.options is options
        assert result.options.ibd_industries == ("Electronics", "Software")
        assert result.options.gics_sectors == ("Information Technology", "Healthcare")
        assert result.options.ratings == ("Buy", "Strong Buy")

    def test_passes_scan_id_to_repository(self):
        repo = FakeScanResultRepository()
        uow = FakeUnitOfWork(scan_results=repo)
        _setup_scan(uow, "scan-xyz")
        uc = GetFilterOptionsUseCase()

        uc.execute(uow, _make_query(scan_id="scan-xyz"))

        assert repo.last_filter_scan_id == "scan-xyz"

    def test_empty_options(self):
        options = FilterOptions(
            ibd_industries=(), gics_sectors=(), ratings=()
        )
        uow = FakeUnitOfWork(scan_results=FakeScanResultRepository(options))
        _setup_scan(uow)
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
