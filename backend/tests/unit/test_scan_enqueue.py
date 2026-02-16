import types

import pytest
from fastapi import HTTPException

from app.api.v1 import scans as scans_module
from app.api.v1.scans import ScanCreateRequest
from app.schemas.universe import Exchange, IndexName, UniverseDefinition, UniverseType


class FakeSession:
    """Fake DB session that tracks add/commit/refresh calls."""
    def __init__(self):
        self.added = []
        self.commits = 0
        self.refreshes = 0

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.commits += 1

    def refresh(self, _obj):
        self.refreshes += 1

    def query(self, *_args, **_kwargs):
        raise AssertionError("query should not be called for custom universe")


class FakeSessionWithQuery(FakeSession):
    """FakeSession that supports query() for exchange/index universes."""
    def __init__(self, symbols):
        super().__init__()
        self._symbols = symbols

    def query(self, *_args, **_kwargs):
        return self

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def all(self):
        return [(s,) for s in self._symbols]


def _make_fake_delay(called, expected_symbols=None):
    """Create a fake run_bulk_scan.delay function."""
    def fake_delay(scan_id, symbols, criteria):
        assert scan_id
        if expected_symbols is not None:
            assert symbols == expected_symbols
        called["delay"] = True
        return types.SimpleNamespace(id="task-123")
    return fake_delay


# --- Existing tests (backward compat) ---

@pytest.mark.asyncio
async def test_create_scan_commits_before_dispatch(monkeypatch):
    fake_db = FakeSession()
    called = {"delay": False}

    def fake_delay(scan_id, symbols, criteria):
        assert scan_id
        assert symbols == ["AAPL"]
        assert fake_db.commits >= 1
        assert fake_db.added
        assert fake_db.added[-1].task_id is None
        called["delay"] = True
        return types.SimpleNamespace(id="task-123")

    monkeypatch.setattr(scans_module, "run_bulk_scan", types.SimpleNamespace(delay=fake_delay))

    request = ScanCreateRequest(
        universe="custom",
        symbols=["AAPL"],
        criteria=None,
        screeners=["minervini"],
        composite_method="weighted_average",
    )

    response = await scans_module.create_scan(request, db=fake_db)

    assert called["delay"] is True
    assert response.status == "queued"
    assert fake_db.added[-1].task_id == "task-123"
    assert fake_db.commits >= 2


@pytest.mark.asyncio
async def test_create_scan_marks_failed_on_dispatch_error(monkeypatch):
    fake_db = FakeSession()

    def fake_delay(_scan_id, _symbols, _criteria):
        raise RuntimeError("dispatch failed")

    monkeypatch.setattr(scans_module, "run_bulk_scan", types.SimpleNamespace(delay=fake_delay))

    request = ScanCreateRequest(
        universe="custom",
        symbols=["AAPL"],
        criteria=None,
        screeners=["minervini"],
        composite_method="weighted_average",
    )

    with pytest.raises(HTTPException) as exc_info:
        await scans_module.create_scan(request, db=fake_db)

    assert exc_info.value.status_code == 500
    assert fake_db.added[-1].status == "failed"
    assert fake_db.commits >= 2


# --- New universe unification tests ---

@pytest.mark.asyncio
async def test_create_scan_with_exchange_universe(monkeypatch):
    """Exchange universe (e.g. NYSE) resolves via stock_universe_service."""
    called = {"delay": False}
    fake_symbols = ["IBM", "GE", "JPM"]

    # Mock the resolver to return fake symbols
    monkeypatch.setattr(
        scans_module.universe_resolver,
        "resolve_symbols",
        lambda db, u, **kw: fake_symbols,
    )
    monkeypatch.setattr(
        scans_module, "run_bulk_scan",
        types.SimpleNamespace(delay=_make_fake_delay(called, fake_symbols)),
    )

    fake_db = FakeSession()
    request = ScanCreateRequest(
        universe="nyse",
        screeners=["minervini"],
    )

    response = await scans_module.create_scan(request, db=fake_db)

    assert called["delay"] is True
    assert response.status == "queued"
    assert response.total_stocks == 3
    # Verify structured fields on the persisted Scan
    scan = fake_db.added[-1]
    assert scan.universe_type == "exchange"
    assert scan.universe_exchange == "NYSE"
    assert scan.universe_key == "exchange:NYSE"
    assert scan.universe == "NYSE"  # label() for backward compat


@pytest.mark.asyncio
async def test_create_scan_with_index_universe(monkeypatch):
    """Index universe (sp500) resolves via stock_universe_service."""
    called = {"delay": False}
    fake_symbols = ["AAPL", "MSFT"]

    monkeypatch.setattr(
        scans_module.universe_resolver,
        "resolve_symbols",
        lambda db, u, **kw: fake_symbols,
    )
    monkeypatch.setattr(
        scans_module, "run_bulk_scan",
        types.SimpleNamespace(delay=_make_fake_delay(called, fake_symbols)),
    )

    fake_db = FakeSession()
    request = ScanCreateRequest(universe="sp500")

    response = await scans_module.create_scan(request, db=fake_db)

    assert called["delay"] is True
    scan = fake_db.added[-1]
    assert scan.universe_type == "index"
    assert scan.universe_index == "SP500"
    assert scan.universe_key == "index:SP500"
    assert scan.universe == "S&P 500"


@pytest.mark.asyncio
async def test_create_scan_with_structured_universe_def(monkeypatch):
    """Structured universe_def takes precedence over legacy universe field."""
    called = {"delay": False}

    monkeypatch.setattr(
        scans_module.universe_resolver,
        "resolve_symbols",
        lambda db, u, **kw: ["AAPL"],
    )
    monkeypatch.setattr(
        scans_module, "run_bulk_scan",
        types.SimpleNamespace(delay=_make_fake_delay(called)),
    )

    fake_db = FakeSession()
    request = ScanCreateRequest(
        universe="all",  # This should be ignored
        universe_def=UniverseDefinition(
            type=UniverseType.EXCHANGE, exchange=Exchange.NASDAQ
        ),
    )

    response = await scans_module.create_scan(request, db=fake_db)

    assert called["delay"] is True
    scan = fake_db.added[-1]
    # universe_def should win over legacy "all"
    assert scan.universe_type == "exchange"
    assert scan.universe_exchange == "NASDAQ"


@pytest.mark.asyncio
async def test_legacy_universe_parsing_via_from_legacy(monkeypatch):
    """Legacy 'all' universe parses correctly through from_legacy()."""
    called = {"delay": False}
    fake_symbols = ["AAPL"]

    monkeypatch.setattr(
        scans_module.universe_resolver,
        "resolve_symbols",
        lambda db, u, **kw: fake_symbols,
    )
    monkeypatch.setattr(
        scans_module, "run_bulk_scan",
        types.SimpleNamespace(delay=_make_fake_delay(called)),
    )

    fake_db = FakeSession()
    request = ScanCreateRequest(universe="all")

    response = await scans_module.create_scan(request, db=fake_db)

    scan = fake_db.added[-1]
    assert scan.universe_type == "all"
    assert scan.universe_key == "all"
    assert scan.universe == "All Stocks"


@pytest.mark.asyncio
async def test_create_scan_persists_universe_symbols_for_custom(monkeypatch):
    """Custom universe persists the symbol list in universe_symbols."""
    called = {"delay": False}

    monkeypatch.setattr(
        scans_module, "run_bulk_scan",
        types.SimpleNamespace(delay=_make_fake_delay(called)),
    )

    fake_db = FakeSession()
    request = ScanCreateRequest(
        universe="custom",
        symbols=["AAPL", "MSFT", "TSLA"],
    )

    await scans_module.create_scan(request, db=fake_db)

    scan = fake_db.added[-1]
    assert scan.universe_type == "custom"
    assert scan.universe_symbols == ["AAPL", "MSFT", "TSLA"]
    assert scan.universe_key.startswith("custom:")
