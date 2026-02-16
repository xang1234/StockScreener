# StockScreener Universe Unification Plan

This document describes an implementation plan to make **“universe”** a single, typed concept across **API request/response**, **DB persistence**, and **business logic**, eliminating drift where:

- Startup cleanup treats `nyse/nasdaq/sp500` as invalid and deletes them.  
- Scan create API docs mention `nyse/nasdaq`, but runtime validation allows only `test/all/custom`.  
- Retention cleanup groups by a loosely defined `Scan.universe` string.  

**Relevant repository files (for context):**
- Startup cleanup & allowed universes: `backend/app/main.py`
- Scan create request + validation: `backend/app/api/v1/scans.py`
- Retention cleanup: `backend/app/tasks/scan_tasks.py`
- Universe data model: `backend/app/models/stock_universe.py`
- Frontend API docs drift: `frontend/src/api/scans.js`

---

## Target architecture

### 1) Single source of truth: `UniverseDefinition`
Create a typed model used **everywhere**:

- API: request parsing + OpenAPI docs  
- DB: stored as structured fields  
- Runtime: symbol resolution logic (ALL/EXCHANGE/INDEX/CUSTOM/TEST)  

**Proposed types**
- `UniverseType = { all, test, custom, exchange, index }`
- `UniverseDefinition`:
  - `type: "all" | "test" | "custom" | "exchange" | "index"`
  - `exchange?: "NYSE" | "NASDAQ" | "AMEX" | ...` (required if `type=exchange`)
  - `index?: "SP500" | ...` (required if `type=index`)
  - `symbols?: [...]` (required if `type=custom` or `type=test`)

### 2) Canonical “universe key”
For retention grouping + UI display, compute a canonical `universe_key` string:

- `all`
- `exchange:NYSE`
- `index:SP500`
- `custom:<hash>` (hash of normalized symbol list)
- `test:<hash>`

This prevents custom universes from clobbering each other and removes ambiguity from string usage.

---

## Step-by-step implementation plan

### Step A — Add domain/schema models

**Files to add**
- `backend/app/schemas/universe.py` *(or `backend/app/domain/universe.py` if you prefer domain naming)*

**Implement**
1) `UniverseType` enum: `all`, `test`, `custom`, `exchange`, `index`

2) `Exchange` enum (initial scope aligned with current universe refresh endpoints):
- `NYSE`, `NASDAQ`, `AMEX`

3) `IndexName` enum:
- `SP500` *(aligned with `StockUniverse.is_sp500` and existing refresh endpoint)*

4) `UniverseDefinition(BaseModel)` with strict validation rules:
- `type=all` → `exchange/index/symbols` must be `None`
- `type=exchange` → `exchange` required; `index/symbols` must be `None`
- `type=index` → `index` required; `exchange/symbols` must be `None`
- `type=custom` or `type=test` → `symbols` required, non-empty; normalize:
  - trim
  - uppercase
  - remove empties
  - dedupe (preserve order)
  - enforce max size (recommended) to protect workers

5) Helpers:
- `UniverseDefinition.key() -> str` (canonical key described above)
- `UniverseDefinition.label() -> str` (human-friendly label for UI)
- `UniverseDefinition.from_legacy(universe: str, symbols: list[str] | None)` supporting legacy:
  - `"all"` → `{type:"all"}`
  - `"custom"` → `{type:"custom", symbols:[...]}`
  - `"test"` → `{type:"test", symbols:[...]}`
  - `"nyse"|"nasdaq"|"amex"` → `{type:"exchange", exchange:"NYSE"|"NASDAQ"|"AMEX"}`
  - `"sp500"` → `{type:"index", index:"SP500"}`

This keeps backward compatibility while removing mismatch between docs and runtime.

---

### Step B — Centralize symbol resolution in one service

**File to add**
- `backend/app/services/universe_resolver.py`

**Why**
Symbol resolution currently happens directly inside the scan endpoint with ad-hoc logic. Centralizing avoids duplication across API, Celery tasks, and future features.

**Implement**
- `resolve_symbols(db, universe_def: UniverseDefinition, limit: int | None = None) -> list[str]`

Rules:
- `all` → all active symbols
- `exchange` → active symbols filtered by exchange
- `index=SP500` → active symbols filtered by `is_sp500`
- `custom/test` → return normalized `symbols`

Optional:
- `resolve_count(...) -> int` for fast counts without returning a full list.

---

### Step C — Store universe in DB as structured fields

#### C1) Update the `Scan` SQLAlchemy model

**File to modify**
- `backend/app/models/scan_result.py` *(contains `Scan` model)*

Add columns (keep existing `universe` string for compatibility, but stop using it as truth):

- `universe_key: String(128), index=True`
- `universe_type: String(20), index=True`
- `universe_exchange: String(20), nullable=True, index=True`
- `universe_index: String(20), nullable=True, index=True`
- `universe_symbols: JSON, nullable=True` *(custom/test only)*

**Important rule:** Business logic must never branch on `Scan.universe` after this change. Use structured fields (or reconstructed `UniverseDefinition`).

#### C2) Add a reconstruction helper (recommended)
Add on `Scan` model (or separate mapper):
- `get_universe_definition(self) -> UniverseDefinition`

So endpoints and tasks can reconstruct a typed universe consistently.

---

### Step D — Replace destructive startup cleanup with a migration/backfill

Startup currently deletes scans using legacy universe values when enabled. Once `exchange/index` universes are supported, that deletion is wrong and causes data loss.

#### D1) Implement idempotent “schema + backfill” migration

**File to add**
- `backend/app/db_migrations/universe_migration.py` *(or similar)*

Responsibilities:

1) **Schema patch (no Alembic today)**
- Use SQLite `PRAGMA table_info(scans)` to detect missing columns
- `ALTER TABLE scans ADD COLUMN ...` for each new column

2) **Backfill existing scans**
For each scan row where `universe_key` or `universe_type` is NULL:
- Parse legacy `Scan.universe`:
  - `all` → `type=all`, `key=all`
  - `nyse/nasdaq/amex` → `type=exchange`, `exchange=...`, `key=exchange:...`
  - `sp500` → `type=index`, `index=SP500`, `key=index:SP500`
  - `custom/test` → best-effort populate symbols:
    - Derive from existing `scan_results` rows for that `scan_id` if needed
    - Compute `key=custom:<hash>` / `test:<hash>`
  - unknown → choose a consistent fallback:
    - Recommended: `type=custom` with derived symbols when possible, else `legacy:<value>` key

3) **Logging**
- Log counts migrated
- Log scan IDs that cannot be migrated cleanly

#### D2) Wire migration into startup

**File to modify**
- `backend/app/main.py`

After DB initialization (`init_db()`), run:
- `migrate_scan_universe_schema_and_backfill(engine)`

Then remove/disable the old deletion-based cleanup path.

---

### Step E — Update scan API request/response models (make docs truthful)

#### E1) Update `ScanCreateRequest` to accept structured universes

**File to modify**
- `backend/app/api/v1/scans.py`

Backward-compatible approach:
- Keep legacy fields:
  - `universe: str`
  - `symbols: Optional[List[str]]`
- Add new field:
  - `universe_def: Optional[UniverseDefinition]`

Validation:
- If `universe_def` is set, use it.
- Else parse legacy `universe` + `symbols` via `UniverseDefinition.from_legacy(...)`.

Update field descriptions to remove drift:
- Legacy string shortcuts should be documented as legacy shortcuts (if kept).

#### E2) Update `create_scan()` logic
In scan creation:
1) Build universe:
- `u = request.universe_def or UniverseDefinition.from_legacy(request.universe, request.symbols)`

2) Resolve symbols via `UniverseResolver`

3) Persist structured fields on Scan:
- `scan.universe_key = u.key()`
- `scan.universe_type = u.type`
- `scan.universe_exchange = ...`
- `scan.universe_index = ...`
- `scan.universe_symbols = ...`

4) Keep `scan.universe` only for backward compatibility:
- Set to `u.label()` or `u.key()` consistently.

#### E3) Update scan list endpoint responses
Minimal-disruption plan:
- Keep `universe: str` but populate it from `universe_key` or `label`
- Add:
  - `universe_type`
  - `universe_exchange`
  - `universe_index`
  - `universe_symbols_count`

---

### Step F — Update retention cleanup logic to use `universe_key`

**File to modify**
- `backend/app/tasks/scan_tasks.py`

Change:
- `cleanup_old_scans(db, universe: str, keep_count: int = 3)`

To:
- `cleanup_old_scans(db, universe_key: str, keep_count: int = 3)`
- Query by `Scan.universe_key == universe_key`

Update call sites:
- After scan completion use `cleanup_old_scans(db, scan.universe_key)`.

This makes retention correct for exchange/index/custom universes.

---

### Step G — Fix frontend drift (docs + optional UI)

**File to modify**
- `frontend/src/api/scans.js`

Update documentation to match backend support after these changes:
- If legacy `universe="nyse"` is supported again, document it as supported.
- If `universe_def` is preferred, document its structure.

Optional UI enhancement:
- Add a universe selector in `frontend/src/pages/ScanPage.jsx`:
  - All
  - Exchange (NYSE/NASDAQ/AMEX)
  - Index (SP500)
  - Custom (symbols input)
  - Test

---

## Acceptance criteria checklist

This work is considered complete when:

1) **OpenAPI docs are accurate**: no options are documented that validation rejects.  
2) **No destructive deletion of legacy universes**: legacy scans are migrated/backfilled, not deleted.  
3) **DB has structured universe fields**: new scans persist `universe_type` + params; old scans backfilled.  
4) **Single resolver**: `UniverseResolver` is the only place resolving symbols from universe.  
5) **Retention uses `universe_key`**: cleanup groups correctly by canonical universe, including custom sets.  
6) **Frontend drift removed**: frontend docs reflect actual backend behavior.

---

## Suggested implementation order (keeps the repo runnable at each step)

1) Add `UniverseDefinition` + `UniverseResolver` (no behavior changes yet)  
2) Add DB columns + idempotent migration/backfill (keep old code still working)  
3) Update scan creation to persist structured fields + set `universe_key`  
4) Update retention cleanup to use `universe_key`  
5) Remove/disable startup deletion cleanup  
6) Update frontend API docs (and UI optional)  
