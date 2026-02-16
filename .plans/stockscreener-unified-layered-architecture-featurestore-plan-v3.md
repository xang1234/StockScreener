# Unified Backend Refactor Plan v3 (Layered Architecture + Feature Store)

This document merges:

1) **Layered backend architecture refactor** (domain / use_cases / infra / interfaces)
2) **Feature Store + Daily Snapshot** (schema + pipeline + query mode)
3) **Operational robustness upgrades** (rate-limit policies, idempotency, atomic publish semantics, observability)

It is written to be **implementation-ready for a coding agent**, with concrete modules, ports/adapters, and a PR-by-PR “strangler” migration that keeps the current API working while you refactor.

---

## 0) Why this refactor is worth it (grounded in current code)

Today, several modules mix transport + orchestration + business logic + provider IO in the same place:

- **FastAPI router** does universe parsing/resolution, DB persistence, and Celery dispatch in one function (`create_scan`).
- **Celery tasks** contain DB updates, concurrency, progress reporting, and scanning orchestration (`scan_tasks.py`).
- **Scan orchestration** has core scoring/rating logic, plus depends directly on `DataPreparationLayer` which calls caches + upstream services (IO).
- Several scan “read APIs” (filter-options, peers, single result, export) are directly coupled to `ScanResult` row format and `details` JSON extraction in the router.

You already have the beginnings of the right separation:
- Typed `UniverseDefinition` and a centralized `universe_resolver` service exist.
- `DataPreparationLayer` centralizes data fetch so screeners can share inputs.
- `ScanOrchestrator` centralizes multi-screener coordination + composite score + rating.

The layered refactor makes these separations *explicit and enforceable*.

---

## 0.1 Non-functional requirements and operational constraints (make the refactor measurable)

This refactor must not only “look clean”—it must be measurable in production and safe under retries and upstream failures.

### External data rate limits (must be enforced centrally)

These are policy constraints the system must encode so that any refactor cannot accidentally violate them:

- yfinance: ~1 req/sec (self-imposed)
- Finviz: wrapper-enforced rate limits
- Alpha Vantage: ~25 req/day (free tier)
- SEC EDGAR: ~10 req/sec (≈150ms between requests)

### Performance / UX budgets

- Online “scan results” queries should be fast and avoid N+1 JSON parsing; target **p95 < 300ms** for common filter/sort (excluding cold-cache).
- Daily snapshot build should be resumable and able to complete unattended within your operating window (e.g., overnight).

### Reliability

- Background jobs (scan runs, snapshot builds) must be **idempotent** and safe to retry.
- Publishing a feature run must be **atomic** (no mixed “latest” view).
- Partial upstream failures should degrade gracefully (mark missing data, don’t crash the entire run).

### Observability

- Every scan/run must have a **correlation ID** propagated across API → Celery → DB rows.
- Emit structured logs + metrics for upstream call rates, cache hit rate, job duration, and data-quality outcomes.

---

## 1) Target layered architecture

### 1.1 Layers and allowed dependencies

**domain/** *(pure logic, no side effects)*
- Entities, value objects, policies (composite scoring, rating rules, “universe rules”), screener interfaces and pure implementations
- **No imports of:** FastAPI, Celery, SQLAlchemy, Redis clients, yfinance, HTTP, filesystem, env

**use_cases/** *(application services)*
- Orchestrate domain logic + repositories + providers
- Examples: `CreateScan`, `RunBulkScan`, `GetScanResults`, `BuildDailyFeatureSnapshot`, `PublishFeatureRun`, `ComputeBreadth`
- Uses domain types + **ports** (Protocols) defined in domain

**infra/** *(adapters / side effects)*
- SQLAlchemy repositories, Redis cache, provider clients, file exports
- Implements domain ports: `ScanRepo`, `FeatureStoreRepo`, `UniverseRepo`, `StockDataProvider`, etc.

**interfaces/** *(transport)*
- FastAPI routers, Celery task entrypoints, CLI commands
- **Thin wrappers**: parse/validate input, call use_case, translate errors to HTTP/task status

> Rule of thumb: if you can unit test it without DB/network, it belongs in **domain**. If it is a “workflow”, it belongs in **use_cases**. If it touches DB/network/cache, it is **infra**.

### 1.2 Enforceable architecture boundaries (CI-gated)

To prevent architectural drift, make layer boundaries enforceable:

- Add an import boundary check (preferred: `import-linter`; acceptable: a small pytest that inspects imports):
  - `domain` may import **only** `domain`
  - `use_cases` may import `domain` + ports (and standard library)
  - `infra` and `interfaces` may import anything, but must not “reach into” domain internals except via ports/types
- Add CI “quality gates”:
  - lint/format (ruff + formatter)
  - unit tests
  - dependency boundary check
  - (optional but recommended) `mypy` on key packages

Also add pre-commit hooks so violations fail fast locally.

### 1.3 Proposed folder layout (backend/app)

```
backend/app/
  domain/
    common/
      errors.py
      types.py
      time.py
      progress.py        # ProgressEvent, ProgressSink (port), CorrelationId
    universe/
      universe_definition.py  # dataclass/Enum version (optional v2)
      universe_rules.py       # e.g. max symbols, validation policies
    scanning/
      models.py          # ScanConfig, ScanResultItemDomain, ScreenerName
      composite.py       # CompositeMethod, CompositeScorer
      rating.py          # RatingCalculator (matches current thresholds)
      filter_spec.py     # FilterSpec dataclasses (pure)
      query_spec.py      # SortSpec, PagingSpec (pure)
      ports.py           # Protocols: repos/providers + job control hooks
    feature_store/
      models.py          # FeatureRunDomain, SnapshotRef, PublishPolicy
      ports.py           # Protocols for feature store repos
      quality.py         # DQ checks (pure)
  use_cases/
    scanning/
      create_scan.py         # CreateScanUseCase
      run_bulk_scan.py       # RunBulkScanUseCase (orchestrates + checkpoints)
      get_scan_results.py    # GetScanResultsUseCase (query mode)
      export_scan_results.py # ExportScanResultsUseCase
      get_filter_options.py  # FilterOptionsUseCase
      get_single_result.py   # GetSingleResultUseCase
      get_peers.py           # GetPeersUseCase
      explain_stock.py       # ExplainStockUseCase (why pass/fail; breakdown)
    feature_store/
      build_daily_snapshot.py  # BuildDailyFeatureSnapshotUseCase
      publish_run.py           # PublishFeatureRunUseCase
      backfill_snapshots.py    # BackfillUseCase
      compare_runs.py          # CompareFeatureRunsUseCase (diff runs)
  infra/
    db/
      models/                 # existing SQLAlchemy models (Scan, ScanResult, StockUniverse, ...)
      models_outbox.py        # optional: transactional outbox (dispatch + progress)
      repositories/
        scan_repo_sqlalchemy.py
        scan_result_repo_sqlalchemy.py
        feature_store_repo_sqlalchemy.py
        universe_repo_sqlalchemy.py
        outbox_repo_sqlalchemy.py
      uow.py                  # UnitOfWork (SessionLocal wrapper)
    cache/
      redis_client.py
      price_cache.py
      fundamentals_cache.py
      benchmark_cache.py
    providers/
      market_data_yfinance.py
      finviz_universe.py
      sec_edgar.py
      llm/
        groq.py
        gemini.py
        openrouter.py
        ...
    query/
      scan_query_sqlalchemy.py         # translates FilterSpec -> SQLAlchemy query
      feature_store_query_sqlalchemy.py
  interfaces/
    api/
      v1/
        scans.py     # routers become thin; call use_cases
        breadth.py
        groups.py
        themes.py
        ...
    tasks/
      scan_tasks.py          # celery tasks become thin; call use_cases
      feature_store_tasks.py
      outbox_poller_tasks.py # optional: publish outbox events
    cli/
      rebuild_snapshot.py
  wiring/
    bootstrap.py             # builds dependency graph (repos/providers/use_cases)
```

**Important migration note:** do not try to move everything at once. Create the new structure, then “strangle” existing code by routing calls through use_cases while leaving old modules in place until the end.

---

## 2) Ports & Adapters (explicit contracts)

### 2.1 Domain ports (Protocols)

Put these in `backend/app/domain/scanning/ports.py` and `domain/feature_store/ports.py`.

#### Scanning ports (examples)

- `ScanRepository`
  - `create(scan: ScanRecordCreate) -> ScanRecord`
  - `get(scan_id) -> ScanRecord`
  - `update_status(scan_id, status, progress, ...)`
  - `set_feature_run(scan_id, feature_run_id)`

- `ScanResultRepository`
  - `bulk_upsert(scan_id, results: list[ScanResultWrite])`
  - `query_results(scan_id, spec: FilterSpec, sort: SortSpec, paging: PagingSpec) -> Page[ScanResultRead]`

- `UniverseRepository`
  - `resolve_symbols(universe: UniverseDefinition) -> list[str]`
  - `count_symbols(universe) -> int`

#### Market data ports (rate-limit aware, failure tolerant)

- `StockDataProvider`
  - `prepare(symbol, requirements, *, as_of_date=None) -> StockData`
  - `prepare_bulk(symbols, requirements, *, as_of_date=None, chunk_size=..., allow_partial=True) -> dict[symbol, StockData]`

Provider policy requirements (must be satisfied by infra adapters):
- enforce upstream rate limits centrally (single throttle point)
- timeouts + retries w/ jittered backoff
- return structured “missing inputs” when allow_partial=True (do not crash the whole run on partial upstream errors)

#### Job control / progress ports

- `ProgressSink`
  - `emit(event: ProgressEvent) -> None`
  - (events are append-only; used for UI timelines and debugging)

- `CancellationToken` (port or domain interface)
  - `is_cancelled() -> bool`

- `CheckpointStore` (optional)
  - `load(scan_id) -> Checkpoint|None`
  - `save(scan_id, checkpoint) -> None`

#### Feature store ports (examples)

- `FeatureRunRepository`
  - `start_run(as_of_date, run_type, code_version, universe_hash, input_hash, correlation_id) -> FeatureRun`
  - `mark_completed(run_id, stats, warnings)`
  - `mark_quarantined(run_id, dq_report)`
  - `publish_atomically(run_id)`  # must update latest pointer in same transaction
  - `get_latest_published() -> FeatureRun|None`

- `FeatureStoreRepository`
  - `upsert_snapshot_rows(run_id, rows)`
  - `save_run_universe_symbols(run_id, symbols: list[str])`
  - `query_latest(spec, sort, paging) -> Page[FeatureRow]`
  - `query_run(run_id, spec, sort, paging) -> Page[FeatureRow]`
  - `get_explain(symbol, run_id) -> FeatureExplainRow` (optional helper)

These ports are what allow swapping providers (yfinance → paid vendor) or DB (SQLite → Postgres) without rewriting domain/use_cases.

### 2.2 Infra adapters you already mostly have

- `DataPreparationLayer` already provides `prepare_data(...)` and `prepare_data_bulk(...)`. It currently imports cache + upstream services directly.
  - In the new structure it becomes an adapter implementing `StockDataProvider`.
  - Add: a single “throttle point” so all upstream calls respect rate limits (align with the existing `data_fetch` queue idea).

- `ScanOrchestrator` currently computes composite score + rating and combines results into a dict, including per-screener fields.
  - In the new structure:
    - composite + rating logic becomes domain (`domain/scanning/composite.py`, `domain/scanning/rating.py`)
    - the orchestrator becomes either:
      - a **domain service** (pure) that is passed a `StockDataProvider` port, or
      - an **application service** in use_cases that calls pure domain functions

---

## 3) How the Feature Store plan fits into the layered architecture

The feature store work is not a separate architecture; it’s an **offline use-case** plus **infra DB tables**.

### 3.1 Feature store components by layer

**domain/**
- `FeatureRunDomain` (status/publish policy)
- DQ policies (rowcount thresholds, null-rate caps, “publishable” criteria)
- `FilterSpec` / `SortSpec` types shared with online querying
- Composite scoring + rating rules (already needed for scan query)

**use_cases**
- `BuildDailyFeatureSnapshotUseCase`
  - resolve `as_of_date` trading day
  - load universe symbols
  - bulk prepare data (fast path)
  - run multi-screener orchestration
  - write to `stock_feature_daily`
  - run DQ checks
  - publish run atomically (or quarantine)
- `QueryFeatureStoreUseCase` (used by scan endpoints)
  - given `ScanRecord.feature_run_id`, choose `latest` or a specific run
- `ExplainStockUseCase` (user-visible trust feature)
- `CompareFeatureRunsUseCase` (movers: score/rating changes)

**infra**
- SQLAlchemy models/tables: `feature_runs`, `stock_feature_daily`, optional `stock_feature_latest`
- `feature_run_universe_symbols` table (run_id, symbol) to store the exact resolved universe for reproducibility
- repo/query builder to translate filter spec to SQLAlchemy query

**interfaces**
- Celery scheduled task calls `BuildDailyFeatureSnapshotUseCase`
- FastAPI scan results endpoints call `GetScanResultsUseCase` which reads from feature store when available

This directly matches the goal: **query-per-request** instead of **compute-per-request**.

---

## 4) Concrete refactor plan (strangler pattern)

### Phase A — Add scaffolding without moving behavior (low risk)

**A1. Create new packages**
- Add folders + `__init__.py` for `domain/`, `use_cases/`, `infra/`, `interfaces/`, `wiring/`
- Add enforceable dependency boundary checks (CI-gated):
  - `import-linter` (or a small pytest) enforcing domain/use_case import rules
  - `ruff` + formatter; optional `mypy`
  - Pre-commit hooks so boundary violations fail fast

**A2. Add wiring/bootstrap**
- `wiring/bootstrap.py` creates:
  - SQLAlchemy UoW factory
  - repository implementations
  - provider implementations (StockDataProvider via DataPreparationLayer adapter)
  - use case instances

**A3. Start with one endpoint**
- Pick **`POST /api/v1/scans`** and refactor it to:
  1) parse request (FastAPI layer)
  2) call `CreateScanUseCase`
  3) return response

Today `create_scan` does universe parsing and symbol resolution and DB persistence and task dispatch in the router.
After A3, router does only transport.

**Additionally (reliability upgrades):**
- Add an `idempotency_key` to Scan creation (client-generated UUID is fine) so repeated POSTs return the existing scan.
- Make async dispatch transaction-safe:
  - Use a transactional outbox (ScanRequested event) **or**
  - A DB `on_commit` hook so Celery tasks are only enqueued after the scan record is committed

**Acceptance**
- No behavior change (same user-visible output)
- Unit tests can call `CreateScanUseCase` with fake repos/providers
- Retry-safe: repeated POST with same idempotency_key yields same scan

---

### Phase B — Extract scanning “core domain” logic (medium risk, high payoff)

**B1. Extract composite score + rating policies**
- Move logic from `ScanOrchestrator._calculate_composite_score` and `_calculate_overall_rating` into:
  - `domain/scanning/composite.py`
  - `domain/scanning/rating.py`

**B2. Define domain types**
- `ScanConfig` (screeners list, composite_method, criteria, universe_def)
- `ScreenerOutput` (score, passes, rating, breakdown, details)
- `ScanResultItemDomain` (matches API output fields; still a domain DTO)

**B3. Refactor orchestrator to depend on ports**
Option 1 (recommended): orchestrator in domain, accepts dependencies:
- `screener_registry` port
- `StockDataProvider` port

No direct instantiation of IO services in orchestrator constructors.

**Acceptance**
- You can unit test composite/rating/orchestration with a fake `StockDataProvider` and fake screeners

---

### Phase C — Make Celery tasks thin wrappers (medium risk)

Today tasks handle DB status updates, concurrency, and call the orchestrator directly.

**C1. Create `RunBulkScanUseCase`**
Responsibilities:
- load Scan record
- resolve universe symbols (via UniverseRepo)
- update scan status/progress (via ScanRepo)
- emit append-only `ProgressEvents` (so UI can show a timeline)
- support cancellation + resumption (chunk checkpointing)
- run batch orchestration
- persist results (via ScanResultRepo)
- finalize status, cleanup retention

**C2. Rewrite Celery task `run_bulk_scan`**
- It becomes:
  - open UoW
  - call `RunBulkScanUseCase.execute(scan_id, correlation_id=..., cancellation_token=...)`
  - update Celery state from use case callbacks

**Acceptance**
- Task files contain no business rules other than “call use_case and report status”
- Task is safe to retry without duplicating results (idempotent writes + checkpointing)

---

### Phase D — Move scan “read APIs” into use_cases (low-medium risk)

These endpoints currently query DB directly from the router and manually map JSON details to response.

Refactor each to a use case:

- `GetScanResultsUseCase`
- `GetFilterOptionsUseCase`
- `GetSingleResultUseCase`
- `GetPeersUseCase`
- `ExportScanResultsUseCase`
- `ExplainStockUseCase` (new)

Router responsibilities become:
- validate request
- call use case
- return response

---

## 5) Combine with Feature Store implementation (merged roadmap)

Now that scanning workflows are in use_cases and core logic is in domain, implement the feature store without adding more spaghetti.

### Phase E — Feature store schema + repositories (infra)

Implementation tasks:
- Add SQLAlchemy models for:
  - `FeatureRun`
  - `StockFeatureDaily`
  - optional `StockFeatureLatest` (table) or a view selecting latest published run
  - `FeatureRunUniverseSymbol` (run_id, symbol) for reproducibility
- Add repositories:
  - `FeatureRunRepository`
  - `FeatureStoreRepository`
- Add migration strategy:
  - Alembic recommended for non-trivial schema evolution
- Add minimal indexes required for query-per-request (see Appendix A)

> SQLite can work early, but query-per-request strongly benefits from Postgres as data grows. Keep the domain/use_cases DB-agnostic so a DB swap is a pure infra change.

### Phase F — Daily snapshot build use case (offline pipeline)

**F1. `BuildDailyFeatureSnapshotUseCase`**
Algorithm:
1) Determine `as_of_date` trading day (domain time policy)
2) `FeatureRunRepository.start_run(...)` (store correlation_id)
3) Resolve universe of active symbols (UniverseRepo; likely “ALL”)
4) Persist resolved universe symbols (`feature_run_universe_symbols`) for reproducibility
5) Merge data requirements for selected screeners (same mechanism current orchestrator uses)
6) Call `StockDataProvider.prepare_bulk(symbols, requirements, as_of_date=..., allow_partial=True)`
7) For each symbol:
  - run orchestrator (pure) with pre-fetched data
8) Persist rows via `FeatureStoreRepository.upsert_snapshot_rows(run_id, rows)`
9) Run DQ checks (domain) and persist DQ stats (rowcount, missingness, null-rates, warnings)
10) If DQ fails: mark run `quarantined` and do NOT publish (keep for inspection/debug)
11) If DQ passes: publish atomically:
  - transaction updates `feature_runs.status='published'` AND updates a single “latest published run” pointer
  - readers never observe mixed latest state (no partial publish)

**F2. Celery beat / scheduler**
- Add `feature_store_tasks.build_daily_snapshot` as thin wrapper calling the use case.

---

### Phase G — Switch scan results endpoints to feature store (online query)

This is where the two plans merge fully.

**G1. Add `Scan.feature_run_id`**
- On scan creation, bind scan to the latest published feature run by default (or allow override).
- This prevents “scan drift” and makes results reproducible over time.

**G2. Update `GetScanResultsUseCase`**
- If scan has `feature_run_id`:
  - query latest view/table if it matches latest run, else query `stock_feature_daily` by run_id
- Else (legacy scans):
  - fall back to `scan_results` until migration completed

**G3. Migrate scan ancillary endpoints**
- `filter-options`, `peers`, `single-result`, `export` should follow the same source selection:
  - use feature store when scan is bound
  - otherwise use legacy scan_results

**G4. New “feature-store-native” endpoints (compelling features)**
- `GET /api/v1/features/runs` list runs + publish status + DQ summary
- `GET /api/v1/scans/{scan_id}/explain/{symbol}` show pass/fail reasons + breakdown
- `GET /api/v1/features/compare?run_a=...&run_b=...` return movers (score/rating changes)

---

## 6) Detailed “coding agent” task list (PR sequence)

### PR0 — Preparatory refactor + enforceable boundaries
- Add `backend/app/domain`, `use_cases`, `infra`, `interfaces`, `wiring`
- Add `wiring/bootstrap.py`
- Add `infra/db/uow.py` (UnitOfWork)
- Add CI “quality gates”: ruff/format, unit tests, and dependency-boundary test
- Add pre-commit hooks mirroring CI gates

**DoD:** repo runs with no behavior change; CI prevents boundary drift

### PR1 — CreateScanUseCase + idempotency + safe dispatch
- Implement `CreateScanUseCase` (uses UniverseDefinition + universe_resolver)
- Add `idempotency_key` support (Scan create is retry-safe)
- Update router `POST /scans` to call use case
- Enqueue scan work only after commit (outbox or on_commit)

**DoD:** same API output, same DB rows; safe to retry POST and safe to retry tasks

### PR2 — Extract domain scoring policies
- Create `domain/scanning/composite.py` and `rating.py`
- Unit tests for composite + rating thresholds (match current orchestrator behavior)

### PR3 — RunBulkScanUseCase + job control
- Implement `RunBulkScanUseCase` with:
  - progress event emission
  - cancellation checks
  - checkpointing for resumption
- Rewrite celery task to call use case, keep progress reporting
- Add progress events persistence (optional outbox table) and/or API read endpoint for progress timeline

### PR4 — Scan read use cases (+ explain)
- Implement `GetScanResultsUseCase` (still reading legacy `scan_results`)
- Implement `GetFilterOptionsUseCase`, `GetSingleResultUseCase`, `GetPeersUseCase`, `ExportScanResultsUseCase`
- Implement `ExplainStockUseCase` (legacy mode reads ScanResult details; feature store mode reads feature row breakdown)
- Routers become wrappers

### PR5 — Feature store schema + repos (+ universe storage)
- Add models: `FeatureRun`, `StockFeatureDaily`, optional `StockFeatureLatest` or view
- Add table: `feature_run_universe_symbols`
- Add repos: `FeatureRunRepository`, `FeatureStoreRepository`
- Implement “latest published run” pointer and atomic publish
- Add migrations and required indexes

### PR6 — BuildDailyFeatureSnapshotUseCase + scheduled task + quarantine semantics
- Implement use case with:
  - allow_partial bulk prep
  - DQ report + quarantined status
  - atomic publish pointer update
- Add celery beat entry
- Validate it can build and publish a snapshot using bulk data path

### PR7 — Bind scans to feature runs + switch query mode
- Add `feature_run_id` to Scan model (and DB)
- Update `CreateScanUseCase` to bind to latest run
- Update `GetScanResultsUseCase` to read feature store when bound
- Migrate ancillary endpoints similarly

### PR8 — Feature-store-native UX upgrades (compare runs)
- Implement `CompareFeatureRunsUseCase`
- Add endpoint `GET /api/v1/features/compare`
- Add endpoint `GET /api/v1/features/runs`

### PR9 — Cleanup / remove legacy compute-per-request path (optional)
- Turn per-scan compute into an opt-in debug mode
- Or remove once feature store is stable

---

## 7) Testing strategy (agent-ready)

### 7.1 Domain unit tests (fast)
- `CompositeScorer`: weighted_average / max / min
- `RatingCalculator`: thresholds + downgrade behavior (pass-rate)
- `UniverseDefinition` parsing rules (if you duplicate as domain dataclass, test parity)

### 7.2 Use case tests (no DB/network)
- Use fake repositories (in-memory dict)
- Use fake StockDataProvider returning deterministic StockData
- Assert:
  - CreateScan stores expected fields and idempotency works
  - RunBulkScan writes results and updates status + progress events
  - Cancellation and checkpointing behave correctly (resume doesn’t duplicate work)

### 7.3 Integration tests (DB)
- SQLite: basic correctness
- Postgres: recommended if you implement partitions/partial indexes

### 7.4 Golden “scan parity” test
- Pick 20 stable tickers and one `as_of_date`
- Run legacy scan pipeline once
- Build feature snapshot for same date
- Compare:
  - composite_score, rating, key fields match (within rounding)
  - filter/sort results order stable for a few filter sets

### 7.5 Provider contract tests (no flakiness)
- Use stub servers or recorded responses to validate:
  - retry/backoff behavior
  - “allow_partial” semantics (missing inputs do not crash the run)
  - rate-limit enforcement at the adapter boundary

### 7.6 Query performance guardrails (lightweight)
- Add a small benchmark that:
  - seeds a minimal feature store table
  - runs a few common filter/sort queries
  - asserts query count and latency stays within a budget (prevent N+1 regressions)

---

## 8) Notes on scope control (what not to refactor yet)

To keep the refactor tractable:

- Do **not** immediately migrate every module (chatbot/themes/breadth) into the new structure.
- Start with **scans**, because:
  - it’s the busiest path
  - it’s the one feature store directly improves
  - it already has partial separation (UniverseDefinition, DataPreparationLayer, ScanOrchestrator)

After scans+feature store are stable, replicate the same pattern to breadth/groups/themes.

---

## 9) Minimal “combined” diagram

```
FastAPI Router (interfaces/api)
  -> UseCase (use_cases/scanning/get_scan_results)
    -> FeatureStoreRepo (infra/db/repositories)
    -> Composite/Ratings Policy (domain/scanning)
  <- returns DTOs
<- response

Celery beat task (interfaces/tasks)
  -> BuildDailyFeatureSnapshotUseCase (use_cases/feature_store)
    -> UniverseRepo (infra)
    -> StockDataProvider (infra: DataPreparationLayer adapter, rate-limited + retries)
    -> Orchestrator + policies (domain)
    -> FeatureStoreRepo (infra)
    -> DQ checks + atomic publish pointer update
```

---

## 10) Implementation shortcuts that keep it “agent-friendly”

- Keep SQLAlchemy models where they are initially; just stop importing them from routers/tasks directly.
- Use small “DTO” dataclasses between layers (domain -> use_cases).
- Prefer explicit constructor injection in use cases (`__init__(repo_a, repo_b, provider_x)`), not global singletons.
- Add a `bootstrap()` function for both FastAPI and Celery so dependency wiring stays consistent.

---

## Appendix A) Minimal Feature Store schema (practical defaults)

This appendix makes the plan self-contained even if other docs are missing.

### A.1 Tables

**feature_runs**
- id (PK)
- as_of_date (DATE, indexed)
- run_type (TEXT)  # daily_snapshot / backfill / etc.
- status (TEXT)    # running/completed/failed/quarantined/published
- created_at, completed_at, published_at
- code_version (TEXT)
- universe_hash (TEXT), input_hash (TEXT)
- correlation_id (TEXT, indexed)
- stats_json (JSON), warnings_json (JSON)

**feature_run_universe_symbols**
- run_id (FK → feature_runs.id, indexed)
- symbol (TEXT, indexed)
- PRIMARY KEY (run_id, symbol)

**stock_feature_daily**
- run_id (FK → feature_runs.id, indexed)
- symbol (TEXT, indexed)
- as_of_date (DATE, indexed)   # denormalized for query convenience
- composite_score (REAL, indexed)
- overall_rating (INTEGER, indexed)
- passes_count (INTEGER)
- details_json (JSON)          # per-screener breakdown; keep small and structured
- PRIMARY KEY (run_id, symbol)

**stock_feature_latest (optional)**
- Either:
  - a materialized table updated on publish, or
  - a SQL VIEW that joins to the latest published run pointer.
- If table: PRIMARY KEY(symbol) plus indexes for common sorts/filters.

### A.2 “Latest published run” pointer (atomic publish)

Implement one authoritative pointer so readers can resolve “latest” cheaply and safely, e.g.:

**feature_run_pointers**
- key (TEXT PK)  # e.g. 'latest_published'
- run_id (FK to feature_runs.id)
- updated_at

Publishing must update:
- feature_runs.status='published' AND
- feature_run_pointers.key='latest_published' -> run_id
in the *same transaction*.

### A.3 Index guidance

Minimum indexes for query-per-request:
- stock_feature_daily(run_id, composite_score DESC)
- stock_feature_daily(run_id, overall_rating DESC)
- stock_feature_daily(run_id, symbol)
- feature_run_universe_symbols(run_id, symbol)

If Postgres:
- Consider partitioning stock_feature_daily by as_of_date (monthly) + BRIN index on as_of_date.

---

**End (v3).**
