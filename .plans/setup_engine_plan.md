# Setup Engine Implementation Plan (Part 1: Pre-breakout Discovery)

> **Goal:** Evolve the current scanner from “find stocks that match filters” into a **Setup Engine** that:
> 1) detects multiple *pre-breakout* pattern families,
> 2) computes **breakout readiness** features (stored + filterable), and
> 3) produces an **actionable explanation / checklist** (why it’s a candidate, what levels matter, what would invalidate it).
>
> This plan is **analysis-only** (not financial advice). It focuses on building consistent, explainable computations so a swing/position trader can review charts faster and run a repeatable workflow.

---

## 0) Baseline: where this fits in the current repo (as of main)

The repo already supports a multi-screener architecture and persistence patterns that we can piggyback on:

- **ScanOrchestrator** runs multiple screeners per symbol, shares fetched `StockData`, then returns a single combined result dict.
- **ScreenerRegistry** registers screeners by `screener_name` (decorator-based).
- **ScanResultRepository** persists the orchestrator output into `ScanResult.details` and maps selected fields into indexed columns for filtering.
- A **Feature Store** (`StockFeatureDaily.details_json`) supports storing the *full orchestrator output* and filtering/sorting with `json_extract()` mappings.

**Implication:** We can add a new `setup_engine` screener that emits a structured “setup report” into the orchestrator result dict, and it will naturally be persisted for both:
- ad-hoc **scan results** (`ScanResult.details`)
- daily snapshots via **feature store** (`StockFeatureDaily.details_json`)

### Code pointers (existing)

- `backend/app/scanners/scan_orchestrator.py` (multi-screener orchestration)
- `backend/app/scanners/screener_registry.py` (registration)
- `backend/app/scanners/minervini_scanner_v2.py` (already computes RS ratings, stage, MA alignment, VCP via criteria modules)
- `backend/app/scanners/criteria/vcp_detection.py` (existing VCP logic)
- `backend/app/infra/db/repositories/scan_result_repo.py` (maps orchestrator output → DB)
- `backend/app/infra/query/scan_result_query.py` and `backend/app/infra/query/feature_store_query.py` (filter/sort mapping)

---

## 1) What we are building

### 1.1 New screener: `SetupEngineScanner`

Add a new screener that outputs **Setup Engine fields**:

- A **primary pattern candidate** (e.g., VCP, 3WT, HTF, Cup/Handle, NR7, First Pullback)
- A list of **other detected candidates** (for funnel/ranking)
- **Pivot / buy-point** (pattern-specific pivot definition) + key levels
- **Breakout readiness** computed features (distance to pivot, volatility contraction, volume dry-up, RS leadership)
- A normalized **setup_score** (0–100) and **setup_ready** classification
- An **explain object** with pass/fail checklist + invalidation flags

### 1.2 Pattern detection library (new package)

Create a dedicated pattern library folder with a consistent interface.

```
backend/app/analysis/patterns/
  __init__.py
  models.py          # PatternCandidate dataclass
  utils.py           # resampling, swing detection, rolling stats helpers
  vcp.py             # wrapper around existing VCP code
  three_weeks_tight.py
  high_tight_flag.py
  cup_handle.py
  nr7_inside_day.py
  first_pullback.py
  aggregator.py      # chooses best candidate + yields explanation
```

The detectors are designed to be **heuristics**, not perfect chart recognition.
The goal is: **ranked candidate funnel + consistent language + fast review**.

---

## 2) Setup Engine outputs (stored + filterable)

This section defines the **fields** the Setup Engine will compute and persist.

### 2.1 Top-level fields (recommended naming)

In the orchestrator result dict, write fields under a single namespace key to avoid collisions, e.g.:

```json
"setup_engine": {
  "setup_score": 84.3,
  "readiness_score": 78.1,
  "quality_score": 88.0,
  "setup_ready": true,
  "setup_stage_ok": true,
  "setup_rs_ok": true,

  "pattern_primary": "three_weeks_tight",
  "pattern_confidence": 0.74,
  "pivot_price": 123.45,
  "pivot_type": "tight_high",
  "pivot_date": "2026-02-18",

  "distance_to_pivot_pct": -2.1,
  "in_early_zone": true,
  "extended_from_pivot": false,

  "base_length_weeks": 14,
  "base_depth_pct": 22.4,
  "tight_closes_count": 9,
  "support_tests_count": 2,

  "atr14_pct": 2.9,
  "atr14_pct_trend": -0.12,
  "bb_width_pct": 6.1,
  "bb_width_pctile_252": 0.18,
  "bb_squeeze": true,

  "volume_vs_50d": 0.64,
  "up_down_volume_ratio_10d": 1.3,
  "quiet_days_10d": 4,

  "rs_line_new_high": true,
  "rs_vs_spy_65d": 1.18,
  "rs_vs_spy_trend_20d": 0.03,

  "candidates": [...],

  "explain": {...}
}
```

> Notes:
> - Keep all computed values JSON-serializable (native floats/ints/strings/bools).
> - Prefer flat numeric fields at the top of `setup_engine` so they are easy to map into `_JSON_FIELD_MAP` for filtering/sorting.

### 2.2 “Breakout readiness” computed features

These are the fields that make it a Setup Engine instead of just a screener.

#### A) Distance to pivot / buy point (%)

**Definition** (for any pattern that defines a pivot):

- `distance_to_pivot_pct = 100 * (current_close - pivot_price) / pivot_price`

Recommended convenience booleans (for filtering):
- `in_early_zone`: `pivot_distance_low <= distance_to_pivot_pct <= pivot_distance_high`
  - Example defaults: `[-5.0, +2.0]` (below pivot = “approaching pivot”; slightly above pivot = “early breakout”)
- `extended_from_pivot`: `distance_to_pivot_pct > +5.0` (configurable; descriptive only)

#### B) Base quality stats

These are pattern-agnostic “base health” metrics; pattern modules may also emit their own variants, but the Setup Engine should output a consistent set.

- `base_length_weeks`  
  - measured from detected base start to end, using weekly bars
- `base_depth_pct`  
  - `100 * (base_high - base_low) / base_high`
- `support_tests_count`  
  - count of touches near key MA/support line (e.g., 10-week / 50d) during base
- `tight_closes_count`  
  - count of closes with small dispersion (e.g., close within X% of rolling median) inside the base
- `contractions_count` (if applicable)  
  - for VCP-like patterns, number of successive contractions (>=2)

#### C) Volatility contraction metrics

Compute on daily bars unless detector requires weekly.

- `atr14_pct = 100 * ATR(14) / close`
- `atr14_pct_trend` = slope of `atr14_pct` over the last N sessions (e.g., 20d linear regression slope)
- Bollinger Band width:
  - `bb_width_pct = 100 * (upper_bb - lower_bb) / middle_bb` (20-period BB by default)
  - `bb_width_pctile_252` = percentile rank of today’s `bb_width_pct` vs last 252 sessions
  - `bb_squeeze` = `bb_width_pctile_252 <= squeeze_threshold` (e.g., 0.20)

#### D) Volume “dry-up” & accumulation proxies

- `volume_vs_50d = current_volume / avg_volume_50d`
- `up_down_volume_ratio_10d`:
  - define up-day volume = sum(volume where close > prior close) over last 10 days
  - define down-day volume = sum(volume where close < prior close) over last 10 days
  - ratio = up / max(down, epsilon)
- `quiet_days_10d`:
  - count of days where:
    - `volume < quiet_volume_threshold * avg_volume_50d` (e.g., 0.8)
    - AND `true_range_pct < quiet_range_threshold` (e.g., 1.0 * ATR14_pct or fixed percent)

#### E) Relative strength “leadership” checks

Setup Engine should compute **ticker-vs-benchmark** RS features using `StockData.benchmark_data` (SPY).

- RS line series: `rs = stock_close / spy_close`
- `rs_line_new_high`:
  - true if `rs[-1] == max(rs[-lookback:])` with lookback e.g. 252 (1y)
- `rs_vs_spy_65d`:
  - ratio of stock return to benchmark return over 65 sessions (or simply the rs line change)
- `rs_vs_spy_trend_20d`:
  - slope of `rs` over last 20 sessions

> **Industry-group basket RS (optional in v1)**  
> This requires either:
> - mapping each symbol to an IBD group ETF/basket, or
> - building an in-app basket from peers via `ibd_industry_group` in stored data.  
> Keep this as a follow-up iteration once the core Setup Engine is stable.

---

## 3) Pattern detection specifications (precise calculations)

### 3.0 Common requirements and conventions

**Inputs to detectors:**
- Daily OHLCV data (`DataFrame` with `Open/High/Low/Close/Volume` and `DatetimeIndex`)
- Optional: benchmark OHLC for RS-based checks

**Outputs from each detector:**
- `PatternCandidate` (see `models.py`) with:
  - `pattern_name`
  - `timeframe` (`daily` or `weekly`)
  - `start_date`, `end_date`
  - `pivot_price`, `pivot_date`, `pivot_type`
  - `quality_score` (0–100)
  - `readiness_score` (0–100) *(optional; aggregator can compute)*
  - `confidence` (0–1)
  - `metrics` dict (pattern-specific computed metrics)
  - `checks` dict (pass/fail booleans with reasons)
  - `notes` list (human-readable strings for explain UI)

**Time axis convention:**
- In the pattern library, keep everything **chronological** (oldest → newest) for rolling calculations.
- If existing code expects most-recent-first (e.g., VCPDetector), wrap it in `vcp.py` and convert.

**Swing / pivot helpers:**
- Use a swing-high/low detector on daily data (or weekly after resample) to find candidate pivot zones.
- Utility method: `find_swings(series, left=3, right=3)` returns indices where a point is greater/less than neighbors.

---

### 3.1 VCP (wrapper, not reimplementation)

**Module:** `vcp.py`  
**Intent:** Reuse `backend/app/scanners/criteria/vcp_detection.py` and translate its output into `PatternCandidate`.

**Key translation points:**
- Existing `VCPDetector.detect_vcp(prices, volumes)` expects `prices` and `volumes` as **most-recent-first** series in the current repo.
- Wrapper should:
  1) take `df_daily` chronological,
  2) build `prices_mrf = close[::-1].reset_index(drop=True)` and same for volume,
  3) call the detector,
  4) map:
     - `pivot_price` from `pivot_info.pivot`
     - `ready_for_breakout` boolean into checks
     - `atr_score`, `contraction_ratio` into metrics

**Pivot definition (per existing code):**
- Use detector’s `pivot_info.pivot` as pivot price.
- `pivot_type = "vcp_pivot"`

**Candidate score:**
- `quality_score` can map from `vcp_score` (normalize to 0–100 if needed)
- `confidence` can be derived from `vcp_detected` plus number of contractions

---

### 3.2 Three Weeks Tight (3WT) / Multi-Weeks Tight

**Module:** `three_weeks_tight.py`  
**Timeframe:** weekly (resampled from daily)

#### Definition (weekly close tightness)

A “tight area” in MarketSmith is identified when the **closing price for at least three consecutive weeks is within a ±1.5% band**. IBD University also describes 3-weeks-tight as weekly closes within about **1%** of the prior week’s close. (References at bottom.)

We implement both as configurable thresholds:
- strict: `close_band_pct = 1.0`
- relaxed: `close_band_pct = 1.5`

#### Steps

1) Resample daily bars to weekly bars (Fri-close convention):
- `W-FRI` resample:
  - Open = first open
  - High = max high
  - Low = min low
  - Close = last close
  - Volume = sum volume

2) Find the latest run of `k >= 3` consecutive weekly closes such that:

Option A (band-to-median):
- Let `c_i` be weekly closes for weeks i-k+1..i.
- Compute `median_close = median(c)`.
- Condition: `max(|c_j - median_close| / median_close) * 100 <= close_band_pct`

Option B (week-to-week):
- Condition: for each j in the run: `abs(c_j - c_{j-1}) / c_{j-1} * 100 <= close_band_pct`

Use Option A by default (more robust), and record the worst deviation.

3) Validate trend context (optional, but helpful):
- Prior 8–12 weeks should have “uptrend into tightness”:
  - simple check: weekly close is above 10-week MA, and 10-week MA rising

4) Define pivot:
- `pivot_price = max(highs during tight weeks)`
- `pivot_type = "tight_high"`
- `pivot_date = date of that weekly high`

5) Quality metrics:
- `weeks_tight = k`
- `tight_band_pct = computed worst deviation percent`
- `tight_range_pct = 100 * (max(high) - min(low)) / median_close`
- Optional volume contraction:
  - `vol_vs_10w = last_week_volume / avg(volume last 10 weeks)`

6) Score and checks:
- `check_weeks >= 3`
- `check_tight_band <= threshold`
- `check_volume_quiet` (optional): last week volume below avg 10w
- `quality_score` increases with:
  - more weeks tight (up to cap)
  - tighter band
  - tighter range
  - quiet volume

**Multi-weeks-tight:** treat `k >= 4` as higher confidence, and set `pattern_name = "multi_weeks_tight"` for k >= 4 if desired.

---

### 3.3 High Tight Flag (HTF)

**Module:** `high_tight_flag.py`  
**Timeframe:** daily + weekly (hybrid)

HTF is commonly described as:
- a sharp **pole** of **+100%** (often +100–120%) in about **4–8 weeks**
- followed by a short **flag** consolidation (often **3–5 weeks**) that pulls back less than about **25%** (often 10–20% typical)
(References at bottom.)

#### Steps

1) Identify candidate pole (daily):
- Define a rolling window `pole_weeks ∈ [4, 8]` → `pole_days = pole_weeks * 5`
- For each end day `t` in last N days (e.g., last 60 days), compute:
  - `start = t - pole_days`
  - `pole_return = (close[t] / close[start]) - 1`
- Require:
  - `pole_return >= 1.0` (>= +100%)
  - Optional: `pole_return <= 1.5` for “classic” +150% cap (configurable)

Pick the *best* pole ending near recent highs (e.g., end day within last 20 days).

2) Define flag region after pole:
- From pole end day `t0`, look forward for flag length `flag_days ∈ [5, 25]` (1–5 weeks)
- Candidate flag is the most recent completed segment ending at last bar (or near last bar).
- Compute:
  - `flag_high = max(high in flag)`
  - `flag_low = min(low in flag)`
  - `flag_depth_pct = 100 * (flag_high - flag_low) / flag_high`
- Require:
  - `flag_depth_pct <= 25`
  - optional “upper half” check:
    - `flag_low >= pole_start + 0.5*(pole_end - pole_start)` (ensure flag holds high)

3) Volume dryness in flag:
- `flag_volume_vs_50d = avg(volume in flag) / avg(volume prior 50d)` (or prior 20d if insufficient)
- Check: `flag_volume_vs_50d < 1.0` (configurable)

4) Pivot definition:
- Pivot is the top of flag:
  - `pivot_price = flag_high`
  - `pivot_type = "flag_high"`
  - `pivot_date = date of flag_high`

5) Quality score:
- increases with:
  - bigger pole return (up to cap)
  - shorter flag duration (to a point)
  - smaller flag depth
  - flag volume drying

6) Readiness (optional in detector):
- If close is within X% of pivot (e.g., within 5%), boost readiness_score

---

### 3.4 Cup-with-Handle (heuristic)

**Module:** `cup_handle.py`  
**Timeframe:** weekly primary (resampled), with daily refinement

MarketSmith describes cup patterns lasting **6 to 65 weeks** with depth **8% to 50%**. Cup-with-handle uses similar cup constraints and adds a handle consolidation. (References at bottom.)

Because perfect recognition is hard, implement a **heuristic** with explicit confidence scoring.

#### Definitions

- **Left lip:** a local weekly high that begins the cup.
- **Cup low:** local low after the left lip.
- **Right lip:** a recovery high near the left lip.
- **Handle:** a short consolidation/pullback near the right lip, typically in the upper half of the cup.

#### Steps (weekly)

1) Resample to weekly OHLCV as in 3WT.

2) Find candidate left lips:
- Use swing-highs on weekly highs with `left=2,right=2`.
- Consider recent 6–65 week window.

3) For each candidate left lip index `L`:
- Search forward (later weeks) for a cup low `B` such that:
  - `B` occurs at least 2 weeks after L
  - `depth_pct = 100*(high[L] - low[B]) / high[L]` within [8, 50]
- Then search for right lip `R` after B such that:
  - `close[R]` recovers to at least `recovery_pct` of left lip (e.g., >= 0.90 * high[L])
  - Cup duration `weeks = R - L` in [6, 65]

4) Handle detection:
- After right lip R, look for handle segment `H` lasting `handle_weeks ∈ [1, 5]`
- Handle constraints:
  - `handle_depth_pct = 100*(handle_high - handle_low) / handle_high`
  - `handle_depth_pct <= 15` (configurable; typical 8–12)
  - handle should be in upper half of cup:
    - `handle_low >= low[B] + 0.5*(high[L] - low[B])`

5) Pivot definition:
- Pivot is the highest price within handle:
  - `pivot_price = max(high within handle)`
  - `pivot_type = "handle_high"`
  - `pivot_date = date of that high`
- If no handle (cup without handle), pivot is `high[L]` (or right-lip high). Keep it separate pattern_name.

6) Additional heuristics (confidence boosters):
- “U-shape” vs “V-shape”: compute curvature proxy:
  - compare average slope down vs slope up; penalize if too sharp (V)
- Volume contraction into handle:
  - handle volume below cup average volume

7) Quality score:
- boost if:
  - duration in “ideal” range (e.g., 7–40 weeks)
  - depth in “ideal” (e.g., 12–33%)
  - handle exists and is shallow
  - handle volume quiet

---

### 3.5 NR7 + Inside Day (tightening triggers)

**Module:** `nr7_inside_day.py`  
**Timeframe:** daily

#### NR7 definition

NR7 (“Narrow Range 7”) is when today’s range is the narrowest of the last 7 sessions:
- `range[t] = high[t] - low[t]`
- `is_nr7[t] = range[t] == min(range[t-6:t])`
(Reference at bottom.)

#### Inside day definition

An inside day is when:
- `high[t] < high[t-1]` AND `low[t] > low[t-1]`
(Reference at bottom.)

#### Combined trigger logic

This detector should output candidates for:
- `nr7`
- `inside_day`
- `nr7_inside_day` (when both occur on same day)

#### Pivot definition

For tightening triggers, pivot is typically a short-term breakout level:
- `pivot_price = high[t]` (or high[t-1] for inside-day range)
- `pivot_type = "trigger_high"`
- `pivot_date = date[t]`

#### Quality scoring

- Higher score if:
  - occurs within a valid base context (optional):
    - price above 20d MA and within X% of 50d MA
    - volatility contraction trending down
  - volume dries up on trigger day (or day range is extremely small in % terms)

Emit metrics:
- `range_pct = 100 * (high-low)/close`
- `volume_vs_50d`
- `atr14_pct`

---

### 3.6 First Pullback / Trend Resumption (to 10-week / 50-day)

**Module:** `first_pullback.py`  
**Timeframe:** daily + weekly

This aims to detect “first pullback” setups where a leader, after a breakout or strong advance, pulls back into a key moving average zone (often the 10-week / 50-day) and begins to resume trend. This is described in IBD/MarketSmith contexts as a common add-on / alternative buy point type. (References at bottom.)

This will be heuristic and must expose its rules clearly in `checks`.

#### Steps

1) Identify an “uptrend phase” prior to pullback:
- price above 50d MA for at least `trend_days` (e.g., 20–40)
- 50d MA rising (slope positive over last 20 days)
- optional: recent breakout proxy:
  - close made a 60-day high within last 30 days

2) Identify first pullback event:
- Find the most recent swing high `H` (daily swing high in last 30–60 days)
- From H to present, measure pullback depth:
  - `pb_depth_pct = 100 * (high[H] - low_after_H) / high[H]`
- Require pullback stays orderly:
  - `pb_depth_pct <= 20` (configurable; allow more for high-beta stocks)
- Require price interacts with MA zone:
  - daily: low touches within `ma_touch_band_pct` of 50d MA (e.g., within 1–2%)
  - weekly alternative: weekly low touches within band of 10-week MA

3) Count “tests” of MA:
- Count number of distinct touches where low is within band, separated by at least X bars.
- Prefer `tests <= 2`, label first test vs second test.

4) Resumption trigger:
- A resumption day occurs when:
  - close > prior close AND close > short-term MA (e.g., 10d EMA)
  - optional: volume above prior day or above 20d average

5) Pivot definition:
- For pullback resumption, a practical pivot is:
  - `pivot_price = high of the pullback swing` (the high just before pullback began)
  - OR `pivot_price = high of resumption trigger bar` (for tighter triggers)
- Use:
  - `pivot_type = "pullback_high"` or `"resumption_high"`
  - store both in metrics if possible

6) Quality score:
- boost if:
  - shallow pullback
  - first test of MA (not third+)
  - tight ranges in pullback
  - volume dries up during pullback and expands on resumption day

---

## 4) Pattern aggregator (choosing “best candidate” + explanations)

**Module:** `aggregator.py`

### 4.1 Responsibilities

- Run all detectors on the same prepared daily dataframe.
- Collect `PatternCandidate` objects.
- Rank them and select:
  - `primary_candidate`
  - `secondary_candidates` list for UI

### 4.2 Ranking logic (initial heuristic)

Define a common `candidate_score`:

```
candidate_score = (
  0.55 * quality_score +
  0.35 * readiness_score +
  0.10 * confidence * 100
)
```

If detectors do not produce readiness_score, compute it centrally using:
- distance_to_pivot_pct (closer is better, but penalize too extended)
- volatility contraction signals
- volume dryness
- RS leadership

Tie-breakers:
- prefer patterns with explicit base context (VCP / CupHandle / HTF) over pure triggers (NR7/Inside)
- prefer longer-duration bases over ultra-short ones if other factors equal

### 4.3 Aggregator output structure (for explain UI)

Return:
- `primary`: PatternCandidate
- `candidates`: list[PatternCandidate] sorted desc
- `explain` dict with:
  - `passed_checks`: list[str]
  - `failed_checks`: list[str]
  - `key_levels`: dict with pivot, support, resistance
  - `invalidation_flags`: list of `{code, message, severity}`

---

## 5) SetupEngineScanner implementation details

### 5.1 File placement

Add:

- `backend/app/scanners/setup_engine_scanner.py` (new screener)
- `backend/app/analysis/patterns/*` (new pattern package)

### 5.2 DataRequirements

Setup Engine needs:
- 2y daily price data (for BB percentile and MA context)
- benchmark data (SPY) for RS leadership features
- optional: earnings history (if you want “earnings soon” invalidation flag)

```python
return DataRequirements(
    price_period="2y",
    needs_benchmark=True,
    needs_earnings_history=False,  # toggle later if desired
)
```

### 5.3 Scan flow (high level)

1) Validate sufficient data (>= 252 sessions recommended)
2) Build core technical context using existing criteria modules used by MinerviniScannerV2:
   - MovingAverageAnalyzer (MA alignment + trend)
   - WeinsteinstageAnalyzer (stage)
   - RelativeStrengthCalculator (RS rating / RS line)
3) Run PatternAggregator:
   - detect candidates
   - select primary
4) Compute Breakout Readiness features (Section 2.2)
5) Produce `setup_score`, `setup_ready`, and `explain` object
6) Return `ScreenerResult` with:
   - `score = setup_score` (0–100)
   - `passes = setup_ready` (or separate strict pass)
   - `rating` mapping (e.g., Strong/Buy/Watch/Pass)
   - `details` includes the `setup_engine` object described above

### 5.4 Setup scoring model (v1)

Split into **quality** vs **readiness**:

- `quality_score` (0–100)
  - pattern structural goodness:
    - base duration
    - depth constraints
    - tightness / contraction count
    - “upper half” constraints for handle/flag
- `readiness_score` (0–100)
  - distance to pivot (best near 0% but not too extended)
  - volatility contraction (ATR% falling, BB width percentile low)
  - volume dry-up (quiet days, volume_vs_50d low)
  - RS leadership checks

Then:
- `setup_score = 0.60*quality_score + 0.40*readiness_score`
- `setup_ready = setup_score >= ready_threshold AND in_early_zone AND stage_ok AND rs_ok`
  - thresholds all configurable

**Why this structure:** it lets you rank a long base with mediocre readiness separately from a tight trigger in a leader — and explain both.

### 5.5 Explain / checklist generation

In the same `setup_engine.explain` object, include:

- **Passed/failed checks** with reasons:
  - Stage: stage == 2?
  - MA alignment: price > 50d > 150d > 200d?
  - RS leadership: rs_line_new_high? rs_rating >= threshold?
  - Pattern checks: each detector’s check results
  - Readiness checks: in_early_zone, squeeze, dry-up
- **Key levels**:
  - pivot price
  - nearest support (e.g., 50d MA, 10-week MA, recent swing low)
  - base high/base low
- **Invalidation flags** (descriptive, not advice):
  - `breaks_50d_support` (if close below 50d)
  - `too_extended` (distance_to_pivot_pct > X)
  - `low_liquidity` (avg dollar volume < threshold)
  - `earnings_soon` (if earnings history available and within N days)

---

## 6) Persistence + filter/sort wiring (so it works like the existing 80+ filters)

### 6.1 Persisting (already works)

Because `ScanResultRepository._map_orchestrator_result()` stores the full orchestrator dict in `ScanResult.details`, anything inside `setup_engine` will be persisted automatically.

Same for the feature store snapshot (`StockFeatureDaily.details_json`) if the daily job writes orchestrator output.

### 6.2 Make fields filterable/sortable

Add JSON path mappings for new fields in:

- `backend/app/infra/query/scan_result_query.py` → `_JSON_FIELD_MAP`
- `backend/app/infra/query/feature_store_query.py` → `_JSON_FIELD_MAP`

Example new mappings (scan results):

```python
_JSON_FIELD_MAP.update({
  "setup_score": "$.setup_engine.setup_score",
  "setup_ready": "$.setup_engine.setup_ready",
  "readiness_score": "$.setup_engine.readiness_score",
  "quality_score": "$.setup_engine.quality_score",
  "pattern_primary": "$.setup_engine.pattern_primary",
  "pivot_price": "$.setup_engine.pivot_price",
  "distance_to_pivot_pct": "$.setup_engine.distance_to_pivot_pct",
  "in_early_zone": "$.setup_engine.in_early_zone",
  "atr14_pct": "$.setup_engine.atr14_pct",
  "bb_width_pctile_252": "$.setup_engine.bb_width_pctile_252",
  "bb_squeeze": "$.setup_engine.bb_squeeze",
  "volume_vs_50d": "$.setup_engine.volume_vs_50d",
  "quiet_days_10d": "$.setup_engine.quiet_days_10d",
  "rs_line_new_high": "$.setup_engine.rs_line_new_high",
})
```

### 6.3 Sorting on JSON fields (important)

Today, `scan_result_query.py` supports:
- range filters on JSON via `json_extract()`
- boolean filters on JSON via `json_extract()`
…but sorting for JSON fields is limited.

**Upgrade plan (recommended):** implement SQL sorting for JSON numeric fields, similar to how `feature_store_query.py` handles json sorting.

Add in `scan_result_query.apply_sort_and_paginate()`:

- If `sort.field in _JSON_FIELD_MAP`:
  - `json_val = func.json_extract(ScanResult.details, json_path)`
  - `order_by(cast(json_val, SAFloat))` (asc/desc)

This avoids needing Python sorting (which is capped and memory risky).

---

## 7) Frontend: “Explain drawer” + columns (minimal plan)

### 7.1 New columns in results table
Expose:
- `setup_score`
- `pattern_primary`
- `distance_to_pivot_pct`
- `bb_squeeze`
- `volume_vs_50d`
- `rs_line_new_high`
- `pivot_price`

### 7.2 Explain drawer UX
When a user clicks a row (or a “why?” icon), show:
- Setup Engine summary (pattern name, score, readiness)
- Checklist (passed/failed) with colored bullets
- Key levels with copy-to-clipboard
- Mini timeline of base dates (start/end), pivot date

No new backend endpoint needed if the table already fetches `details` / `extended_fields`.

---

## 8) Testing plan (must-have)

### 8.1 Unit tests for each detector
- Each detector gets:
  - synthetic dataset tests (constructed to trigger pattern)
  - negative tests (similar data but fails one critical check)
- Validate:
  - pivot is within the detected time window
  - computed depth/duration match expected
  - `checks` reflect the fail reason accurately

### 8.2 Golden tests with known tickers (optional)
- Keep a small local dataset snapshot (CSV) for a handful of known historical examples.
- Verify regression stability for pivot, score ordering, and checks list.

### 8.3 No look-ahead guarantee
- Ensure any rolling or percentile calculations only use data up to `t`.
- When resampling to weekly, confirm the “current week” bar is only included if it’s complete (or explicitly label incomplete).

---

## 9) Implementation checklist (step-by-step)

### Step 1 — Add pattern package skeleton
- [ ] Create folder `backend/app/analysis/patterns/`
- [ ] Implement `PatternCandidate` dataclass in `models.py`
- [ ] Implement utilities in `utils.py`:
  - [ ] resample daily→weekly
  - [ ] ATR(14), BB(20,2), slope/regression helper
  - [ ] swing detection helper
  - [ ] percentile rank helper
  - [ ] “true range %” helper

### Step 2 — Implement detectors
- [ ] `vcp.py` wrapper around existing `VCPDetector`
- [ ] `three_weeks_tight.py`
- [ ] `high_tight_flag.py`
- [ ] `cup_handle.py`
- [ ] `nr7_inside_day.py`
- [ ] `first_pullback.py`

Each detector must return `PatternCandidate | None` (or list), and must not throw on missing data—return `None` gracefully.

### Step 3 — Add aggregator
- [ ] Run all detectors
- [ ] Score/rank
- [ ] Emit combined candidate list + explain block

### Step 4 — Implement `SetupEngineScanner`
- [ ] Create `setup_engine_scanner.py`
- [ ] Register via `@register_screener`
- [ ] Compute readiness features
- [ ] Emit details under `setup_engine` namespace
- [ ] Decide `passes` logic and rating mapping

### Step 5 — Persistence mappings
- [ ] Update `_JSON_FIELD_MAP` in `scan_result_query.py`
- [ ] Update `_JSON_FIELD_MAP` in `feature_store_query.py`
- [ ] Add JSON sorting support in `scan_result_query.py` (recommended)

### Step 6 — Frontend wiring
- [ ] Add “Setup Engine” to screener selection
- [ ] Add columns + filters
- [ ] Add Explain drawer rendering from `setup_engine.explain`

---

## 10) References for pattern rules (parameter guidance)

These are used to choose initial default thresholds; all thresholds should be **configurable** in code.

- MarketSmith: Tight Areas (≥3 consecutive weekly closes within ±1.5%)  
  https://www.marketsmith.hk/tight-areas/?lang=en

- IBD University: 3-Weeks-Tight (“each weekly close within about 1% of the prior week’s close”)  
  https://myibd.investors.com/Education/lesson.aspx?id=736316&sourceid=735787

- MarketSmith: Cup / Cup-with-handle duration + depth guidance (6–65 weeks; 8–50% depth)  
  https://www.marketsmith.hk/cup-with-handle/?lang=en  
  https://www.marketsmith.hk/cup/?lang=en

- Deepvue: High Tight Flag basics (≥100% in <8 weeks; short flag consolidation)  
  https://deepvue.com/screener/high-tight-flag/

- StockCharts ChartSchool: NR7 (narrowest range in last 7 days)  
  https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/narrow-range-day-nr7

- Investopedia: Inside Day definition (high/low within prior day’s range)  
  https://www.investopedia.com/terms/i/inside-days.asp

- Nasdaq (IBD syndication): 10-week line context / definition  
  https://www.nasdaq.com/articles/how-trade-stocks-why-10-week-line-offers-follow-buy-points-2017-11-27
