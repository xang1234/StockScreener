# StockScreener Feature Store Plan (Feature Store + Daily Compute Pipeline)

This document defines a target architecture + implementation plan to make **scans** execute as **fast SQL queries over a daily precomputed feature snapshot**.

It is written so a coding agent can implement without guessing:
- exact `StockFeatureDaily` column set (aligned 1:1 with the current `ScanResultItem` response shape)
- an explicit **criteria → SQLAlchemy** mapping table based on the current `/scans/{scan_id}/results` query parameters and the frontend’s filter param builder

---

## 1) Goal

### Primary goal
Turn “scan” from “compute-per-request” into “query-per-request” by precomputing daily features.

**Offline (daily):** ingest → compute → publish a snapshot  
**Online (request):** resolve universe → query snapshot (filter/sort/paginate) → return results

### What stays the same
- Frontend keeps calling the same scan results endpoint with the same query params.
- Response payload keeps the **same `ScanResultItem` shape**, so the UI doesn’t need a rewrite.

### What changes
- Instead of querying `scan_results` (per-scan table), the API queries `stock_feature_daily` (per-day snapshot table).
- “Create scan” becomes mostly metadata + selecting a snapshot date, not running a long background job.

---

## 2) Current contract that must be preserved

### 2.1 `ScanResultItem` response shape (backend)
The current `ScanResultItem` model in `backend/app/api/v1/scans.py` defines the output fields that the Feature Store must support.

**We will store these 1:1 as columns in `stock_feature_daily`** (same names, same meaning).

> NOTE: Some fields are currently pulled from `ScanResult.details` JSON (e.g., VCP fields). In the feature store, these become first-class columns for speed.

### 2.2 Filtering contract (frontend → backend)
Frontend converts UI filters into API query parameters via `frontend/src/utils/filterUtils.js`. These params must continue to work.

Backend defines these query params in `GET /scans/{scan_id}/results` (same file: `backend/app/api/v1/scans.py`).

**We will implement the same filtering behavior, but on `stock_feature_daily` instead of `scan_results`.**

---

## 3) Target architecture (high level)

### 3.1 Data flow (daily offline pipeline)

1) **Data warmup / ingestion (existing pattern)**
- Update `stock_prices` + SPY
- Update `stock_fundamentals`
- Update `stock_universe` (active tickers)

2) **Feature Store build (new)**
- Create a `FeatureRun(as_of_date, status=running)`
- Compute features + screener scores for each active symbol (parallelizable)
- Upsert rows into `stock_feature_daily` for that `as_of_date`
- Mark the run `completed` (publish signal)

### 3.2 Query-time scan (online)

- Resolve universe → list of symbols
- Pick latest `FeatureRun` with `status='completed'`
- Query `stock_feature_daily` where:
  - `as_of_date = FeatureRun.as_of_date`
  - `symbol IN universe_symbols`
  - Apply filters from query params
  - Apply sorting + pagination
- Return rows in `ScanResultItem` shape

---

## 4) Database schema

### 4.1 `feature_runs` (run metadata / publish marker)

**Table:** `feature_runs`

| Column | Type | Nullable | Notes |
|---|---:|---:|---|
| id | Integer (PK) | no | internal key |
| as_of_date | Date | no | trading day the snapshot represents; **unique** |
| status | String | no | `running|completed|failed` |
| started_at | DateTime | no | default now |
| completed_at | DateTime | yes | set when finished |
| universe_hash | String | yes | hash of active symbol set for reproducibility |
| code_version | String | yes | git sha / version tag |
| stats_json | JSON | yes | counts, timings, errors |
| error | Text | yes | failure info |

**Indexing**
- unique(as_of_date)
- index(status, as_of_date)

---

## 5) Exact `StockFeatureDaily` column list

### 5.1 Naming rules
- Column names match the **current API response fields** where possible.
- Columns used only for filtering/sorting may be included even if not returned yet.
- All numeric values should be normalized to the same units used today:
  - Scores are `0..100`
  - Growth and performance fields are percentages (e.g., `25.0` means `25%`)
  - Distances are percentages (e.g., `-10.5` means `-10.5%` from EMA)

### 5.2 Primary keys & metadata (required)
**Table:** `stock_feature_daily`

| Column | Type | Nullable | Notes |
|---|---:|---:|---|
| id | BigInteger (PK) | no | optional, but recommended |
| run_id | Integer (FK → feature_runs.id) | no | link to published run |
| as_of_date | Date | no | snapshot date |
| symbol | String(12) | no | uppercase ticker |
| created_at | DateTime | no | default now |
| updated_at | DateTime | no | default now, update on upsert |

**Constraints**
- unique(symbol, as_of_date)

---

## 6) Response-aligned columns (1:1 with `ScanResultItem`)

Below are the **exact output fields** you must be able to return for each row.

> These should exist as columns with the same names so the API can do `ScanResultItem(**row_dict)`.

### 6.1 Identity & meta
| Column | Type | Nullable | Description |
|---|---:|---:|---|
| company_name | String(255) | yes | from stock_universe.name (denormalize for join-free queries) |
| screeners_run | JSON | yes | array of screener names included in this row’s composite |

### 6.2 Scores & rating
| Column | Type | Nullable | Description |
|---|---:|---:|---|
| composite_score | Float | no | composite score (0–100) |
| rating | String(20) | no | `Strong Buy|Buy|Watch|Pass` |
| minervini_score | Float | yes | individual score |
| canslim_score | Float | yes | individual score |
| ipo_score | Float | yes | individual score |
| custom_score | Float | yes | individual score |
| volume_breakthrough_score | Float | yes | individual score |

### 6.3 Minervini / technical template fields
| Column | Type | Nullable | Description |
|---|---:|---:|---|
| rs_rating | Float | yes | RS rating 0–100 |
| rs_rating_1m | Float | yes | RS 1 month |
| rs_rating_3m | Float | yes | RS 3 month |
| rs_rating_12m | Float | yes | RS 12 month |
| stage | Integer | yes | Weinstein stage 1–4 |
| stage_name | String(50) | yes | optional text label |
| current_price | Float | yes | last close (or last trade if available) |
| volume | BigInteger | yes | **dollar volume** (UI labels `$Vol`) or chosen volume measure |
| market_cap | BigInteger | yes | market cap |
| ma_alignment | Boolean | yes | trend template MA alignment |
| vcp_detected | Boolean | yes | VCP detected |
| vcp_score | Float | yes | VCP score |
| vcp_pivot | Float | yes | VCP pivot price |
| vcp_ready_for_breakout | Boolean | yes | VCP “ready” flag |
| vcp_contraction_ratio | Float | yes | VCP contraction measure |
| vcp_atr_score | Float | yes | VCP ATR score |
| passes_template | Boolean | yes | passes Minervini trend template |

### 6.4 Growth, valuation, EPS rating
| Column | Type | Nullable | Description |
|---|---:|---:|---|
| adr_percent | Float | yes | average daily range % |
| eps_growth_qq | Float | yes | EPS QoQ growth % |
| sales_growth_qq | Float | yes | Sales QoQ growth % |
| eps_growth_yy | Float | yes | EPS YoY growth % |
| sales_growth_yy | Float | yes | Sales YoY growth % |
| peg_ratio | Float | yes | PEG |
| eps_rating | Integer | yes | IBD-style EPS rating 0–99 |

### 6.5 Industry classifications
| Column | Type | Nullable | Description |
|---|---:|---:|---|
| ibd_industry_group | String(100) | yes | industry group |
| ibd_group_rank | Integer | yes | group rank (1 = best) |
| gics_sector | String(100) | yes | sector |
| gics_industry | String(100) | yes | industry |

### 6.6 Sparklines + trend
| Column | Type | Nullable | Description |
|---|---:|---:|---|
| rs_sparkline_data | JSON | yes | array[float], 30-day RS ratio normalized |
| rs_trend | Integer | yes | -1 declining, 0 flat, 1 improving |
| price_sparkline_data | JSON | yes | array[float], 30-day normalized price |
| price_change_1d | Float | yes | 1-day % change (also used as perf-day filter) |
| price_trend | Integer | yes | -1 down, 0 flat, 1 up |

### 6.7 IPO + beta metrics
| Column | Type | Nullable | Description |
|---|---:|---:|---|
| ipo_date | Date | yes | stored as Date; API returns `YYYY-MM-DD` string |
| beta | Float | yes | 252d beta |
| beta_adj_rs | Float | yes | beta-adjusted RS |
| beta_adj_rs_1m | Float | yes | beta-adjusted RS 1m |
| beta_adj_rs_3m | Float | yes | beta-adjusted RS 3m |
| beta_adj_rs_12m | Float | yes | beta-adjusted RS 12m |

---

## 7) Additional filter/sort-only columns (recommended)

These are required to fully support the backend filter params currently exposed in `GET /scans/{scan_id}/results`, even though they are not returned in `ScanResultItem` today.

| Column | Type | Nullable | Used by filters |
|---|---:|---:|---|
| perf_week | Float | yes | min/max `perf_week` |
| perf_month | Float | yes | min/max `perf_month` |
| perf_3m | Float | yes | min/max `perf_3m` |
| perf_6m | Float | yes | min/max `perf_6m` |
| gap_percent | Float | yes | min/max `gap_percent` |
| volume_surge | Float | yes | min/max `volume_surge` |
| ema_10_distance | Float | yes | min/max `ema_10_distance` |
| ema_20_distance | Float | yes | min/max `ema_20_distance` |
| ema_50_distance | Float | yes | min/max `ema_50_distance` |
| week_52_high_distance | Float | yes | min/max `52w_high` |
| week_52_low_distance | Float | yes | min/max `52w_low` |

---

## 8) Indexing guidance

At minimum:
- unique(symbol, as_of_date)
- index(as_of_date, composite_score)
- index(as_of_date, minervini_score)
- index(as_of_date, rs_rating)
- index(as_of_date, stage)
- index(as_of_date, market_cap)
- index(as_of_date, volume)
- index(as_of_date, gics_sector)
- index(as_of_date, ibd_industry_group)
- index(as_of_date, ibd_group_rank)
- index(as_of_date, eps_rating)
- index(as_of_date, beta_adj_rs)

If Postgres:
- consider partial indexes on `as_of_date = (latest)` if you also maintain a `stock_feature_latest` table/view.

---

## 9) Criteria → SQL mapping table (query builder)

This table maps **API query parameters** to **SQLAlchemy filters** on `StockFeatureDaily`.

### 9.1 Conventions
- `SFD` = `StockFeatureDaily`
- For `min_*`: apply `SFD.col >= value`
- For `max_*`: apply `SFD.col <= value`
- For list params: parse comma-separated string → list[str] → `IN` or `NOT IN`
- Unless otherwise noted, NULL rows are excluded automatically by comparisons (because `NULL >= x` is unknown).

### 9.2 Filtering mapping

| API param | Type | SFD column | Operator / Expression | Notes |
|---|---|---|---|---|
| symbol_search | str | SFD.symbol (+ optional company_name) | `OR(symbol ILIKE %q%, company_name ILIKE %q%)` | case-insensitive |
| stage | int | SFD.stage | `==` | exact stage |
| ratings | csv str | SFD.rating | `IN (..)` | split on `,` |
| ibd_industries | csv str | SFD.ibd_industry_group | `IN (..)` or `NOT IN` | use `ibd_industries_mode` |
| ibd_industries_mode | str | — | include/exclude | default include |
| gics_sectors | csv str | SFD.gics_sector | `IN (..)` or `NOT IN` | use `gics_sectors_mode` |
| gics_sectors_mode | str | — | include/exclude | default include |
| passes_only | bool | SFD.passes_template | `IS TRUE` | if true: filter; if false: no filter |
| ma_alignment | bool | SFD.ma_alignment | `IS (true/false)` | tri-state in UI; if null: no filter |
| vcp_detected | bool | SFD.vcp_detected | `IS (true/false)` | tri-state |
| vcp_ready | bool | SFD.vcp_ready_for_breakout | `IS (true/false)` | tri-state |

**Score ranges**
| API param | Type | SFD column | Operator | Notes |
|---|---|---|---|---|
| min_composite / max_composite | float | SFD.composite_score | `>=` / `<=` | |
| min_score / max_score | float | SFD.minervini_score | `>=` / `<=` | “score” = minervini |
| min_canslim / max_canslim | float | SFD.canslim_score | `>=` / `<=` | |
| min_ipo / max_ipo | float | SFD.ipo_score | `>=` / `<=` | |
| min_custom / max_custom | float | SFD.custom_score | `>=` / `<=` | |
| min_vol_breakthrough / max_vol_breakthrough | float | SFD.volume_breakthrough_score | `>=` / `<=` | |

**RS ranges**
| API param | Type | SFD column | Operator | Notes |
|---|---|---|---|---|
| min_rs / max_rs | float | SFD.rs_rating | `>=` / `<=` | 0–100 |
| min_rs_1m / max_rs_1m | float | SFD.rs_rating_1m | `>=` / `<=` | 0–100 |
| min_rs_3m / max_rs_3m | float | SFD.rs_rating_3m | `>=` / `<=` | 0–100 |
| min_rs_12m / max_rs_12m | float | SFD.rs_rating_12m | `>=` / `<=` | 0–100 |

**Price & growth**
| API param | Type | SFD column | Operator | Notes |
|---|---|---|---|---|
| min_price / max_price | float | SFD.current_price | `>=` / `<=` | |
| min_adr / max_adr | float | SFD.adr_percent | `>=` / `<=` | |
| min_eps_growth / max_eps_growth | float | SFD.eps_growth_qq | `>=` / `<=` | QoQ |
| min_sales_growth / max_sales_growth | float | SFD.sales_growth_qq | `>=` / `<=` | QoQ |
| min_eps_growth_yy | float | SFD.eps_growth_yy | `>=` | backend param only min (as implemented) |
| min_sales_growth_yy | float | SFD.sales_growth_yy | `>=` | backend param only min (as implemented) |
| max_peg | float | SFD.peg_ratio | `<=` | valuation |

**EPS rating**
| API param | Type | SFD column | Operator | Notes |
|---|---|---|---|---|
| min_eps_rating / max_eps_rating | int | SFD.eps_rating | `>=` / `<=` | 0–99 |

**Volume & market cap**
| API param | Type | SFD column | Operator | Notes |
|---|---|---|---|---|
| min_volume | int | SFD.volume | `>=` | volume is `$Vol` per UI |
| min_market_cap | int | SFD.market_cap | `>=` | |

**VCP numeric filters**
| API param | Type | SFD column | Operator | Notes |
|---|---|---|---|---|
| min_vcp_score / max_vcp_score | float | SFD.vcp_score | `>=` / `<=` | |
| min_vcp_pivot / max_vcp_pivot | float | SFD.vcp_pivot | `>=` / `<=` | |

**Performance filters (price change %)**
| API param | Type | SFD column | Operator | Notes |
|---|---|---|---|---|
| min_perf_day / max_perf_day | float | SFD.price_change_1d | `>=` / `<=` | perf_day maps to `price_change_1d` |
| min_perf_week / max_perf_week | float | SFD.perf_week | `>=` / `<=` | |
| min_perf_month / max_perf_month | float | SFD.perf_month | `>=` / `<=` | |
| min_perf_3m / max_perf_3m | float | SFD.perf_3m | `>=` / `<=` | |
| min_perf_6m / max_perf_6m | float | SFD.perf_6m | `>=` / `<=` | |

**EMA distances (% above/below)**
| API param | Type | SFD column | Operator |
|---|---|---|---|
| min_ema_10 / max_ema_10 | float | SFD.ema_10_distance | `>=` / `<=` |
| min_ema_20 / max_ema_20 | float | SFD.ema_20_distance | `>=` / `<=` |
| min_ema_50 / max_ema_50 | float | SFD.ema_50_distance | `>=` / `<=` |

**52-week distances**
| API param | Type | SFD column | Operator |
|---|---|---|---|
| min_52w_high / max_52w_high | float | SFD.week_52_high_distance | `>=` / `<=` |
| min_52w_low / max_52w_low | float | SFD.week_52_low_distance | `>=` / `<=` |

**IPO date**
| API param | Type | SFD column | Operator / Expression | Notes |
|---|---|---|---|---|
| ipo_after | str | SFD.ipo_date | `ipo_date >= cutoff_date` | cutoff_date parsed from presets: `6m,1y,2y,3y,5y,YYYY-MM-DD` |

**Beta & beta-adjusted RS**
| API param | Type | SFD column | Operator | Notes |
|---|---|---|---|---|
| min_beta / max_beta | float | SFD.beta | `>=` / `<=` | |
| min_beta_adj_rs / max_beta_adj_rs | float | SFD.beta_adj_rs | `>=` / `<=` | |
| min_beta_adj_rs_1m | float | SFD.beta_adj_rs_1m | `>=` | backend param is min-only |
| min_beta_adj_rs_3m | float | SFD.beta_adj_rs_3m | `>=` | backend param is min-only |
| min_beta_adj_rs_12m | float | SFD.beta_adj_rs_12m | `>=` | backend param is min-only |

**Episodic pivot filters**
| API param | Type | SFD column | Operator |
|---|---|---|---|
| min_gap_percent / max_gap_percent | float | SFD.gap_percent | `>=` / `<=` |
| min_volume_surge / max_volume_surge | float | SFD.volume_surge | `>=` / `<=` |

### 9.3 Sorting mapping (whitelist)
To avoid arbitrary SQL injection via `sort_by`, implement a whitelist:

Allowed `sort_by` values should match the frontend table’s `column.id` list (plus any additional API-supported fields). Example mapping:

- `symbol` → `SFD.symbol`
- `composite_score` → `SFD.composite_score`
- `minervini_score` → `SFD.minervini_score`
- `canslim_score` → `SFD.canslim_score`
- `ipo_score` → `SFD.ipo_score`
- `custom_score` → `SFD.custom_score`
- `volume_breakthrough_score` → `SFD.volume_breakthrough_score`
- `rs_rating`, `rs_rating_1m`, `rs_rating_3m`, `rs_rating_12m`
- `beta`, `beta_adj_rs`
- `eps_rating`
- `stage`
- `current_price`, `volume`, `market_cap`
- `ipo_date`
- `eps_growth_qq`, `sales_growth_qq`, `adr_percent`
- `rs_trend`, `price_change_1d`, `price_trend`
- `vcp_score`, `vcp_pivot`
- `gics_sector`, `ibd_group_rank`

If `sort_by` is unknown → HTTP 400.

### 9.4 Sparklines payload control
Query param:
- `include_sparklines: bool`

If `false`:
- do not load `rs_sparkline_data` or `price_sparkline_data`
- return those fields as `null`

In SQLAlchemy, you can implement this by either:
- selecting only needed columns (`load_only(...)`), or
- retrieving full row then setting sparkline fields to `None` before serialization (less optimal).

---

## 10) Query builder implementation blueprint (SQLAlchemy)

### 10.1 Recommended approach
Implement a single function:

`apply_feature_filters(query, params) -> query`

- Parse list params once
- Apply range filters using a mapping dict
- Handle special cases: industries mode, sectors mode, symbol search, ipo_after preset
- Apply sorting using a whitelist dict
- Apply pagination

### 10.2 Pseudocode (agent-ready)

```python
RANGE_FILTERS = {
  "min_composite": (SFD.composite_score, ">="),
  "max_composite": (SFD.composite_score, "<="),
  "min_score": (SFD.minervini_score, ">="),
  "max_score": (SFD.minervini_score, "<="),
  "min_rs": (SFD.rs_rating, ">="),
  "max_rs": (SFD.rs_rating, "<="),
  "min_price": (SFD.current_price, ">="),
  "max_price": (SFD.current_price, "<="),
  "min_perf_day": (SFD.price_change_1d, ">="),
  "max_perf_day": (SFD.price_change_1d, "<="),
  # ... (fill from mapping table above)
}

BOOL_FILTERS = {
  "ma_alignment": SFD.ma_alignment,
  "vcp_detected": SFD.vcp_detected,
  "vcp_ready": SFD.vcp_ready_for_breakout,
}

SORT_WHITELIST = {
  "symbol": SFD.symbol,
  "composite_score": SFD.composite_score,
  "minervini_score": SFD.minervini_score,
  # ... (fill)
}

def apply_feature_filters(query, params):
    # Text search
    if params.symbol_search:
        q = f"%{params.symbol_search.strip().upper()}%"
        query = query.filter(or_(SFD.symbol.ilike(q), SFD.company_name.ilike(q)))

    # Stage
    if params.stage is not None:
        query = query.filter(SFD.stage == params.stage)

    # Ratings
    if params.ratings:
        rating_list = [r.strip() for r in params.ratings.split(",") if r.strip()]
        query = query.filter(SFD.rating.in_(rating_list))

    # IBD industries include/exclude
    if params.ibd_industries:
        vals = [v.strip() for v in params.ibd_industries.split(",") if v.strip()]
        if (params.ibd_industries_mode or "include") == "exclude":
            query = query.filter(~SFD.ibd_industry_group.in_(vals))
        else:
            query = query.filter(SFD.ibd_industry_group.in_(vals))

    # GICS sectors include/exclude
    if params.gics_sectors:
        vals = [v.strip() for v in params.gics_sectors.split(",") if v.strip()]
        if (params.gics_sectors_mode or "include") == "exclude":
            query = query.filter(~SFD.gics_sector.in_(vals))
        else:
            query = query.filter(SFD.gics_sector.in_(vals))

    # passes_only
    if params.passes_only:
        query = query.filter(SFD.passes_template.is_(True))

    # Range filters
    for key, (col, op) in RANGE_FILTERS.items():
        val = getattr(params, key, None)
        if val is None:
            continue
        if op == ">=":
            query = query.filter(col >= val)
        elif op == "<=":
            query = query.filter(col <= val)

    # Boolean tri-state filters
    for key, col in BOOL_FILTERS.items():
        val = getattr(params, key, None)
        if val is None:
            continue
        query = query.filter(col.is_(val))

    # IPO preset
    if params.ipo_after:
        cutoff = parse_ipo_after_preset(params.ipo_after)  # returns date
        if cutoff:
            query = query.filter(SFD.ipo_date >= cutoff)

    return query

def apply_sort(query, sort_by: str, sort_order: str):
    col = SORT_WHITELIST.get(sort_by)
    if col is None:
        raise HTTPException(400, f"Invalid sort_by: {sort_by}")
    return query.order_by(desc(col) if sort_order == "desc" else asc(col))
```

---

## 11) Implementation plan (phased, agent-friendly)

### Phase 1 — Feature store schema + daily build MVP
1) Add models:
- `backend/app/models/feature_store.py`:
  - `FeatureRun`
  - `StockFeatureDaily`
2) Add service:
- `backend/app/services/feature_store_service.py`
3) Add tasks:
- `backend/app/tasks/feature_store_tasks.py`
  - `build_daily_feature_store(as_of_date=None, force=False)`
4) Add Celery beat schedule entry:
- schedule after existing cache warmup

**Acceptance**
- `feature_runs` has `status=completed` for today’s `as_of_date`
- `stock_feature_daily` has rows for most active symbols

### Phase 2 — Query-mode scan results (no per-scan compute)
5) Add query engine:
- `backend/app/services/scan_query_service.py`
6) Add filter mapping & whitelist sorting:
- implement `apply_feature_filters`, `apply_sort`
7) Modify `GET /scans/{scan_id}/results`:
- Instead of querying `ScanResult`, use:
  - `latest_completed_feature_run.as_of_date`
  - `symbol IN scan.universe_symbols` (or resolve universe key)
  - query `StockFeatureDaily`

**Acceptance**
- `/scans/{scan_id}/results` returns same payload shape, fast.

### Phase 3 — Parallel nightly build + performance
8) Batch tasks:
- `compute_feature_batch(run_id, as_of_date, symbols[])`
- `finalize_feature_run(run_id)`
9) Bulk load inputs (DB → pandas) to avoid per-symbol DB queries
10) Upsert in bulk

### Phase 4 — Quality gates + backfills
11) Data quality checks before publishing
12) Add backfill task to rebuild feature snapshots for a date range
13) Move to Postgres for production scale (optional but recommended)

---

## 12) Notes for the coding agent

### 12.1 Backward compatibility
Keep existing scan creation + async tasks initially, but switch **results retrieval** to feature store once available.

### 12.2 Testing strategy
- Pick 20 stable symbols and one date.
- Run the old scan pipeline once (baseline)
- Run feature store build for same date
- Compare:
  - returned rows fields match for key metrics (scores, RS, stage, vcp flags, etc.)
  - filters and sorting produce the same count/order for sample filter sets

---

## 13) Deliverable PR order
1) PR1: feature store models + migrations
2) PR2: daily build task (single-process MVP)
3) PR3: query-mode `get_scan_results` reading from feature store
4) PR4: parallel batch build + bulk IO
5) PR5: backfill + quality checks + docs
