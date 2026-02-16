Below is an implementation-ready plan for the 5 “quick wins” you listed. It’s written so a coding agent can pick it up and execute with minimal ambiguity (file paths, concrete steps, acceptance criteria, and suggested tests).

0) Suggested execution order and PR breakdown

To keep risk low and reviews easy, do this as 5 small PRs:

PR-1: /livez + /readyz, update Docker healthchecks (Dockerfile + docker-compose), and make /health non-invasive (or deprecated).

PR-2: Fix nested Celery-task deadlock risk (extract shared impl functions; optional re-entrant lock hardening).

PR-3: Make DataRequirements defaults minimal.

PR-4: Introduce Redis-backed rate limiter + integrate into yfinance/finviz + remove scattered sleeps.

PR-5: Fix Celery timezone mismatch (ET schedules) + add tzdata dependency.

1) Replace /health with /livez + /readyz, remove yfinance from container healthcheck
Why this is a quick win

Right now /health does a real external fetch via yfinance (Ticker("SPY").info) and Docker uses it as the container healthcheck. That can fail due to network, rate limits, Yahoo flakiness, etc., causing containers to flap even when the app is fine.

Target behavior

GET /livez: always returns 200 if the server process is alive (no DB/Redis/external calls).

GET /readyz: returns 200 only if critical dependencies are reachable (DB + Redis). No yfinance calls.

Docker healthcheck should hit /readyz (or /livez, but readiness is usually more meaningful for orchestration).

Implementation steps
A. Add endpoints in backend/app/main.py

File: backend/app/main.py

Add imports:

from fastapi import status

from fastapi.responses import JSONResponse

from sqlalchemy import text

import redis

from .database import engine (or import SessionLocal and do a tiny query)

Implement:

/livez: returns { "status": "ok" }

/readyz: checks:

DB: SELECT 1 via SQLAlchemy engine.connect()

Redis: redis.Redis(host=settings.redis_host, port=settings.redis_port, db=settings.redis_db).ping()

On any failure: return 503 and include error details.

Decide what to do with /health:

Recommended for safety: keep it as a compat alias for now:

/health returns the same as /readyz and includes {"deprecated": true} (or add response header).

Remove the yfinance call entirely. (No external calls in “health” endpoints.)

B. Update Docker healthchecks

You have two healthchecks to update:

Dockerfile healthcheck
File: backend/Dockerfile currently calls /health.
Change:

curl -f http://localhost:8000/readyz

docker-compose healthcheck
File: docker-compose.yml backend healthcheck also calls /health.
Change:

curl -f http://localhost:8000/readyz

C. Repo-wide reference update

Run a quick search/replace:

grep for "/health" in backend + frontend + docs and update to /readyz or /livez where appropriate.

Acceptance criteria

curl -i localhost:8000/livez returns 200 immediately with no external deps.

If Redis is down: curl -i localhost:8000/readyz returns 503.

Docker backend container becomes healthy without any yfinance/Yahoo dependency.

Suggested tests

Add a small pytest file: backend/tests/test_health_endpoints.py

Use FastAPI TestClient.

Mock DB/Redis failures for /readyz (monkeypatch engine.connect and redis.Redis.ping).

2) Fix cache warming deadlock risk: don’t call Celery tasks synchronously inside Celery tasks
Why it’s happening

Your @serialized_data_fetch decorator blocks waiting for a Redis lock if it can’t acquire it, by sleeping in a loop.
But prewarm_all_active_symbols() calls the decorated prewarm_scan_cache() as a normal function call (result = prewarm_scan_cache(...)), and auto_refresh_after_close() similarly calls force_refresh_stale_intraday() directly. That creates a classic self-deadlock (outer task holds the lock; inner call waits forever).

Goal

Ensure no decorated task calls another decorated task synchronously.

Implementation strategy (recommended)

Extract shared “implementation” functions (plain Python functions) and have tasks call those.

Concrete steps

File: backend/app/tasks/cache_tasks.py

A) Prewarm: refactor shared implementation

Create a pure function near the top of the file:

def _prewarm_scan_cache_impl(task, symbol_list: list[str], priority: str = "normal") -> dict:
    # task can be None; if provided, use task.update_state
    ...


Update prewarm_scan_cache task body to:

validate inputs

return _prewarm_scan_cache_impl(self, symbol_list, priority)

Update prewarm_all_active_symbols task to:

query active symbols

return _prewarm_scan_cache_impl(self, symbols, priority="low")

Remove the direct call to prewarm_scan_cache(...).

B) Intraday refresh: refactor shared implementation

Add:

def _force_refresh_stale_intraday_impl(task, symbols: Optional[list[str]] = None) -> dict:
    ...


Update force_refresh_stale_intraday task to:

return _force_refresh_stale_intraday_impl(self, symbols)

Update auto_refresh_after_close task to:

return _force_refresh_stale_intraday_impl(self, symbols=None)

Remove result = force_refresh_stale_intraday(symbols=None).

C) Safety net (optional but low-effort): make the lock re-entrant for same task_id

File: backend/app/tasks/data_fetch_lock.py

Modify DataFetchLock.acquire():

If lock is already held and the current holder’s task_id == task_id, return True.

This prevents future accidental nested calls from deadlocking (even though you should still avoid nesting).

Acceptance criteria

No deadlock when running:

prewarm_all_active_symbols.delay()

auto_refresh_after_close.delay()

The tasks complete and release the lock reliably.

Suggested tests

Unit test where you monkeypatch DataFetchLock.acquire to simulate “already locked by same task id”, ensure wrapper doesn’t loop forever.

Static guard: a simple grep check in CI for patterns like = prewarm_scan_cache( inside cache_tasks.py (not perfect, but catches regressions).

3) Make DataRequirements defaults minimal (avoid accidental fundamentals/SPY fetch)
Why this matters

DataRequirements defaults currently enable:

needs_fundamentals=True

needs_benchmark=True

So any DataRequirements() created without explicit flags can trigger extra expensive fetches (fundamentals + SPY benchmark).
Also, merge_requirements([]) returns DataRequirements() which inherits these defaults.

Target behavior

Defaults should fetch only what’s truly universal:

price data only (keep price_period default if desired)

no fundamentals

no benchmark

Implementation steps

File: backend/app/scanners/base_screener.py

Change dataclass defaults to:

needs_fundamentals: bool = False

needs_benchmark: bool = False

keep other booleans False as-is

Validate screeners are explicit:

Your screeners already specify requirements explicitly (e.g., CANSLIM needs benchmark + fundamentals; Minervini needs benchmark only; etc.)
So this should be a safe change.

Optional: Update merge_requirements to return an explicit minimal object if list is empty (even though new defaults already do that).

Acceptance criteria

Running a scan with only “price-only” screeners does not fetch fundamentals or SPY unless required.

DataPreparationLayer.merge_requirements([]) yields needs_fundamentals=False and needs_benchmark=False.

Suggested tests

tests/test_data_requirements_defaults.py:

assert defaults are minimal

assert merge([]) is minimal

4) Unify rate limiting into one Redis-backed limiter (remove duplicated sleeps / 2-second global min delay)
Current issues to fix

DataPreparation enforces a hard-coded 2-second min delay for yfinance calls using a local in-process lock.

FinvizService has its own local lock + sleep limiter.

Cache warming + bulk fetchers + fundamentals tasks add additional sleeps in multiple places (duplicated throttling).

This makes behavior inconsistent, slow, and not scalable across multiple workers/hosts.

Target behavior

A single Redis-coordinated limiter that works across processes/containers.

No scattered time.sleep() “rate limit” sleeps in business logic.

Still allow backoff sleeps on errors (that’s not rate limiting, it’s recovery).

Implementation plan
A) Add RedisRateLimiter service

New file: backend/app/services/rate_limiter.py

Implement:

RedisRateLimiter.wait(key: str, min_interval_s: float, timeout_s: float = 60, jitter_ms: int = 50)

Uses Redis to store “next allowed timestamp” per key.

Use atomic Lua script (EVAL) to compute required wait and update the key.

If Redis is unavailable, fallback to a simple in-process limiter (thread lock + timestamp) rather than crashing (optional but recommended).

Keys to use (suggested):

"yfinance" for per-request yfinance

"finviz" for finvizfinance calls

"yfinance_batch_prices" for batch warmup loops (if you keep batch throttling)

"yfinance_fundamentals" for batch fundamentals loops

B) Remove DataPreparation’s local limiter and call unified limiter instead

File: backend/app/scanners/data_preparation.py currently has _YFINANCE_MIN_DELAY = 2.0 and _rate_limited_api_call.

Steps:

Delete:

_yfinance_lock

_last_yfinance_call_time

_YFINANCE_MIN_DELAY

_rate_limited_api_call

Before yfinance calls, do:

rate_limiter.wait("yfinance", min_interval_s=1.0 / settings.yfinance_rate_limit)

With current config yfinance_rate_limit=1, this becomes 1 second instead of 2 seconds.

(Or, if you prefer an explicit config, add yfinance_min_interval_seconds to Settings.)

C) Update FinvizService to use Redis limiter (remove its local lock/sleep)

File: backend/app/services/finviz_service.py

Replace _rate_limited_call implementation with:

rate_limiter.wait("finviz", min_interval_s=self.rate_limit_delay)

then call func(...) directly

Remove class-level _last_call_time, _lock, etc. (or keep only for fallback if Redis fails).

D) Ensure all direct yfinance usage is routed through the limiter

You currently bypass YFinanceService in at least:

DataSourceService._get_eps_rating_data uses import yfinance as yf directly.

BulkDataFetcher imports yfinance directly and sleeps manually.

Fix those:

DataSourceService
File: backend/app/services/data_source_service.py
Before yf.Ticker(...) or ticker.info, call:

rate_limiter.wait("yfinance", min_interval_s=1.0 / settings.yfinance_rate_limit)

BulkDataFetcher
File: backend/app/services/bulk_data_fetcher.py
Replace time.sleep(delay_per_ticker) and time.sleep(delay_between_batches) with:

rate_limiter.wait("yfinance_fundamentals", min_interval_s=delay_per_ticker)

rate_limiter.wait("yfinance_fundamentals_batch", min_interval_s=delay_between_batches)

Remove the time.sleep(...) calls (and possibly import time if no longer needed).

E) Remove redundant sleeps in tasks (but keep exponential backoff sleeps)

Fundamentals task loop sleep
File: backend/app/tasks/fundamentals_tasks.py includes time.sleep(0.5) in the loop.
Remove it—finviz/yfinance calls should now be rate limited at the service layer.

Cache warming batch sleep
File: backend/app/services/cache_manager.py sleeps between batches.
Option A (minimal risk): replace time.sleep(rate_limit) with:

rate_limiter.wait("yfinance_batch_prices", min_interval_s=rate_limit)
Option B (cleaner layering): remove it and rely on the lower layers if they enforce appropriate rate limiting.

Given your “quick win” intent, Option A is safest (preserves behavior, centralizes mechanism).

Keep backoff sleeps like _fetch_with_backoff in cache_tasks.py—those aren’t “duplicate throttles”, they’re retry logic.

Acceptance criteria

No occurrences of ad-hoc “rate limit” sleeps remain in:

data_preparation.py

finviz_service.py

fundamentals_tasks.py

bulk_data_fetcher.py

(optionally) cache_manager.py (replaced with limiter)

Rate limiting is coordinated across multiple Celery worker containers (Redis-backed).

Scans are faster than before due to removing the 2-second universal delay.

Suggested tests

Unit test the limiter with a mocked Redis client:

first call returns immediately

second call returns a wait time and sleeps (mock time.sleep)

“Integration smoke”: run 2 threads calling wait("yfinance", 0.2) and assert call timestamps are spaced.

5) Fix Celery timezone vs “ET schedule” mismatch
Current issue

Celery is configured with timezone='UTC', but your schedule settings/comments are clearly ET-based (e.g., cache warmup “5 PM ET”, “6 PM ET”).
Result: tasks run at the wrong wall-clock time (and DST makes UTC conversions brittle).

Target behavior

Celery Beat schedules execute in America/New_York timezone.

Schedule config values (cache_warm_hour, etc.) remain written in ET.

Implementation steps
A) Add timezone setting

File: backend/app/config/settings.py
Add:

celery_timezone: str = "America/New_York"

B) Update Celery config

File: backend/app/celery_app.py
Change:

timezone='UTC' → timezone=settings.celery_timezone

Keep:

enable_utc=True (fine; Celery will still interpret crontab in the configured timezone)

Fix misleading comments (especially the “UTC-5 but Celery runs local time” line).

C) Ensure tzdata exists in Docker builds

Your backend image is python:3.11-slim, which often lacks system tzdata.
Add one of these:

Easiest: add pip tzdata to backend/requirements.txt:

add tzdata>=2024.1 (or latest)

Alternatively: install OS package tzdata via apt in Dockerfile.

Given speed and portability, prefer the pip tzdata approach.

File: backend/requirements.txt

Acceptance criteria

Celery Beat scheduled tasks run at the intended ET times (verify by checking next-run logs).

No timezone exceptions on startup (ZoneInfoNotFoundError etc.).

Suggested validation

Run: celery -A app.celery_app report and confirm timezone.

Temporarily log celery_app.conf.timezone on startup.

Compare “next run” timestamps for one scheduled crontab task against ET.

Deliverable checklist for the coding agent

 PR-1: /livez + /readyz added; /health made non-external; Dockerfile + compose updated.

 PR-2: No synchronous calls from decorated task → decorated task (refactor to impl funcs; optional re-entrant lock).

 PR-3: DataRequirements defaults minimal; tests updated.

 PR-4: RedisRateLimiter created; integrated into finviz/yfinance and direct yfinance call sites; scattered throttling sleeps removed; keep retry backoff.

 PR-5: Celery timezone uses America/New_York; tzdata included; schedule comments cleaned.