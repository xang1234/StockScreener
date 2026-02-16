Below is an implementation plan that makes “universe” a single, typed concept across: API request/response, DB persistence, and business logic — eliminating the current drift where:

startup code treats nyse/nasdaq/sp500 as invalid and deletes them

scan creation docs still describe nyse/nasdaq as valid options, but validation rejects anything except test/all/custom

scan retention cleanup is keyed off the string Scan.universe

frontend API comments also still claim nyse/nasdaq

Target architecture
1) Single source of truth: UniverseDefinition

Create a typed model used everywhere:

API: request parsing + OpenAPI docs

DB: stored as structured fields

Runtime: symbol resolution logic (ALL/EXCHANGE/INDEX/CUSTOM/TEST)

Proposed types

UniverseType = { all, test, custom, exchange, index }

UniverseDefinition:

type: "all" | "test" | "custom" | "exchange" | "index"

exchange?: "NYSE" | "NASDAQ" | "AMEX" | ... (required if type=exchange)

index?: "SP500" | ... (required if type=index)

symbols?: [...] (required if type=custom or type=test)

This supports your recommendation and also lines up with the existing stock universe table having exchange and is_sp500.

2) Canonical “universe key”

For retention grouping + UI display, compute a canonical universe_key string, e.g.:

all

exchange:NYSE

index:SP500

custom:<hash> (hash of normalized symbol list)

test:<hash>

This prevents “custom universe” scans from clobbering each other and removes ambiguous string usage.

Step-by-step implementation plan
Step A — Add domain/schema models

Files to add

backend/app/schemas/universe.py (or backend/app/domain/universe.py if you prefer “domain” naming)

Implement

UniverseType enum:

all, test, custom, exchange, index

Exchange enum (start with what the repo uses today):

NYSE, NASDAQ, AMEX
(You can expand later, but keep initial scope aligned with StockUniverseService and /universe/refresh docs.)

IndexName enum:

SP500 (since StockUniverse.is_sp500 exists and there’s already a “refresh-sp500” endpoint)

UniverseDefinition(BaseModel) with strict validation:

Validation rules:

type=all → exchange/index/symbols must be None

type=exchange → exchange required; index/symbols must be None

type=index → index required; exchange/symbols must be None

type=custom or type=test → symbols required non-empty; normalize:

trim

uppercase

remove empties

dedupe (preserve order)

optionally enforce a max length (e.g., 2,000) to protect the worker

Add helpers:

UniverseDefinition.key() -> str (canonical key as described)

UniverseDefinition.label() -> str (for UI / scan history display)

UniverseDefinition.from_legacy(universe: str, symbols: list[str] | None) to map:

"all" → {type:"all"}

"custom" → {type:"custom", symbols:[...]}

"test" → {type:"test", symbols:[...]}

"nyse"|"nasdaq"|"amex" → {type:"exchange", exchange:"NYSE"|"NASDAQ"|"AMEX"}

"sp500" → {type:"index", index:"SP500"}

This gives you backward compatibility while correcting the mismatch between docs and runtime validation.

Step B — Centralize symbol resolution in one service

File to add

backend/app/services/universe_resolver.py

Why
Right now scan creation resolves symbols directly in the endpoint using ad-hoc logic (and only “all/custom/test”).
You want one canonical resolver so that API, tasks, and future features don’t duplicate universe logic.

Implement resolve_symbols(db, universe_def, limit=None)

all → stock_universe_service.get_active_symbols(exchange=None, sp500_only=False, limit=None)

exchange → get_active_symbols(exchange=universe.exchange, sp500_only=False)

index=SP500 → get_active_symbols(sp500_only=True)

custom/test → return symbols (normalized)

Also add resolve_count(...) if you want fast counts without returning lists (optional).

Step C — Store universe in DB as structured fields
C1) Update the Scan SQLAlchemy model

File to modify

backend/app/models/scan_result.py

Add columns (keep the existing universe string for compatibility, but stop using it as the source of truth):

universe_key: String(128), index=True (canonical key)

universe_type: String(20), index=True

universe_exchange: String(20), nullable=True, index=True

universe_index: String(20), nullable=True, index=True

universe_symbols: JSON, nullable=True (only for custom/test)

Important design rule:
After this change, business logic never branches on Scan.universe. It uses universe_type/exchange/index/symbols (or a reconstructed UniverseDefinition).

C2) Add a reconstruction helper (optional but very useful)

In the Scan model (or a separate mapper), add:

def get_universe_definition(self) -> UniverseDefinition

So tasks / endpoints can do:

u = scan.get_universe_definition()

Step D — Replace destructive startup cleanup with a migration/backfill

Today startup can delete scans with nyse/nasdaq/sp500 when invalid_universe_cleanup_enabled is turned on.
Once you support exchange/index, that deletion is both wrong and data loss.

D1) Implement an idempotent “schema + backfill” migration

File to add

backend/app/db_migrations/universe_migration.py (or backend/app/migrations.py)

Migration responsibilities

Schema patch (because you currently do create_all() only, no Alembic):

Check if each new column exists in scans (SQLite: PRAGMA table_info(scans)).

If missing: ALTER TABLE scans ADD COLUMN ... for each new column.

Backfill existing scans
For each scan row where universe_type (or universe_key) is NULL:

If legacy Scan.universe is:

"all" → type=all, key=all

"nyse"/"nasdaq"/"amex" → type=exchange, exchange=NYSE/..., key=exchange:NYSE

"sp500" → type=index, index=SP500, key=index:SP500

"custom" or "test" → type=custom/test, populate symbols

best-effort: derive symbols from scan_results for that scan
(it’s not perfect if canceled mid-run, but it’s far better than losing data)

compute key=custom:<hash> / test:<hash>

unknown → choose one:

(recommended) set type=custom and derive symbols from results, OR

mark as type=all but set universe_key=legacy:<value> (less clean)

Make it safe and noisy:

log counts migrated

log any scan IDs that could not be migrated cleanly

D2) Wire migration into startup

File to modify

backend/app/main.py

In lifespan startup, after init_db() call, run:

migrate_scan_universe_schema_and_backfill(engine)

Then:

remove or permanently disable the old cleanup_invalid_universe_scans() path (or convert it into a “legacy migration” wrapper).

Step E — Update scan API request/response models (and make docs truthful)

Right now:

Request model says all, nyse, nasdaq, or custom

Implementation rejects nyse/nasdaq entirely

E1) Update ScanCreateRequest to accept structured universes

File to modify

backend/app/api/v1/scans.py

Recommended approach (backward compatible):

Keep accepting legacy:

universe: str

symbols: Optional[List[str]]

Add new optional field:

universe_def: Optional[UniverseDefinition]

Then in a Pydantic model_validator:

If universe_def is set → use it

Else parse legacy universe + symbols using UniverseDefinition.from_legacy(...)

This keeps current frontend working while giving you a clean new contract.

Also update the Field descriptions to remove drift:

If you keep legacy strings, explicitly document them as “legacy shortcuts”.

E2) Update create_scan() logic to use resolver + persist structured fields

In create_scan():

Build universe definition:

u = request.universe_def or UniverseDefinition.from_legacy(request.universe, request.symbols)

Resolve symbols using UniverseResolver

Persist to Scan row:

scan.universe_key = u.key()

scan.universe_type = u.type

scan.universe_exchange/index/symbols = ...

(optional) keep scan.universe = u.label() OR keep scan.universe = u.key() for backward-compatible display

Dispatch Celery unchanged (still pass the symbol list)

This removes universe leakage from the endpoint and makes DB consistent.

E3) Update scan list endpoint responses

Option 1 (minimal disruption):

Keep ScanListItem.universe: str but set it to something meaningful:

universe_key or label

Add new fields:

universe_type, universe_exchange, universe_index, universe_symbols_count

Option 2 (cleaner long-term):

Return universe: UniverseDefinition in responses (breaking change unless UI updated)

Given you already have a React frontend, I’d implement Option 1 first.

Step F — Update retention cleanup logic to use universe_key

Currently, retention is keyed on Scan.universe == universe (string) and docstring claims universe is only test/all/custom.

Files to modify

backend/app/tasks/scan_tasks.py

any call sites (notably run_bulk_scan uses cleanup_old_scans(db, scan.universe))

Change

Rename param: cleanup_old_scans(db, universe_key: str, keep_count: int = 3)

Filter by Scan.universe_key == universe_key (or if you keep Scan.universe as key, standardize on that — but then you must still store structured columns for truth)

Update call

after scan completion: cleanup_old_scans(db, scan.universe_key)

This makes retention correct for:

exchange-specific scans

index scans

multiple different custom sets

Step G — Fix frontend drift (docs + optional UI)

Even if the UI doesn’t expose NYSE/NASDAQ selection, your frontend API docs still claim they exist.

File to modify

frontend/src/api/scans.js

Update JSDoc to reflect what backend supports after your change:

If you support legacy universe: "nyse" etc again, document them as supported.

If you prefer structured universe_def, document the new shape.

Optional UI improvement (if desired):

Add universe dropdown options in ScanPage.jsx (it currently uses only all + test patterns).

all

exchange: NYSE, NASDAQ, AMEX

index: SP500

custom (with a symbol input)

test (still uses your predefined list)

Not required to “fix drift”, but it lets you actually use the richer universe model.

Acceptance criteria checklist

A coding agent should consider this done when:

OpenAPI docs are correct

Request model no longer advertises values that validation rejects.

No destructive deletion of “legacy universes”

Startup migration converts old nyse/nasdaq/sp500 scans into typed universes instead of deleting them.

DB has structured universe fields

New scans always persist universe_type and associated params

Old scans are backfilled

Single resolver path

Only UniverseResolver resolves symbols; no duplicated logic in endpoints/tasks.

Retention uses universe_key

Cleanup groups by canonical universe key, not the loosely-defined universe string.

Frontend comment drift removed

frontend/src/api/scans.js docs match what backend accepts.

Suggested implementation order (keeps the repo runnable at each step)

Add UniverseDefinition + resolver (no behavior changes yet)

Add DB columns + migration/backfill (but keep old code using Scan.universe)

Update create_scan to persist structured fields + set universe_key

Update cleanup_old_scans to use universe_key

Remove/replace startup deletion cleanup

Update frontend API docs (and UI optional)