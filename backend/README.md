# Stock Scanner Backend

FastAPI backend implementing CANSLIM, Minervini, IPO, Volume Breakthrough,
and Custom stock screening with a Feature Store, AI chatbot, and market analysis.

> Full project overview and screenshots: [Root README](../README.md)
> Frontend docs: [Frontend README](../frontend/README.md)

## Setup

### 1. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env — at minimum set DATABASE_URL (absolute path) and at least one LLM API key
```

### 4. Start Redis

```bash
redis-server
# or: brew services start redis (macOS)
```

### 5. Start Celery Workers

```bash
./start_celery.sh
```

> **macOS note**: Celery requires `--pool=solo` to avoid fork() crashes with curl_cffi. The `start_celery.sh` script handles this automatically along with the required `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES` export.

### 6. Start the API Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Reference

Interactive docs available at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Health Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/livez` | GET | Liveness probe (zero dependencies) |
| `/readyz` | GET | Readiness probe (checks DB + Redis) |
| `/health` | GET | Deprecated alias for `/readyz` |

### Endpoint Groups

| Group | Prefix | Description |
|-------|--------|-------------|
| Scans | `/api/v1/scans` | Scan management, results, and history |
| Stocks | `/api/v1/stocks` | Stock data, fundamentals, chart data |
| Features | `/api/v1/features` | Feature store management |
| Breadth | `/api/v1/breadth` | Market breadth indicators |
| Groups | `/api/v1/groups` | IBD group rankings |
| Themes | `/api/v1/themes` | Theme discovery and analysis |
| Technical | `/api/v1/technical` | Technical indicators |
| Fundamentals | `/api/v1/fundamentals` | Fundamental data |
| Chatbot | `/api/v1/chatbot` | AI chat sessions and messages |
| Chat Folders | `/api/v1/chatbot/folders` | Chat folder management |
| Prompt Presets | `/api/v1/prompt-presets` | Saved chatbot prompts |
| Watchlists | `/api/v1/user-watchlists` | Watchlist management |
| User Themes | `/api/v1/user-themes` | User theme management |
| Market Scan | `/api/v1/market-scan` | Dashboard market scan lists |
| Filter Presets | `/api/v1/filter-presets` | Saved scan filter configurations |
| Universe | `/api/v1/universe` | Stock universe management |
| Cache | `/api/v1/cache` | Cache management |
| Tasks | `/api/v1/tasks` | Background task status |
| Config | `/api/v1/config` | Admin configuration |
| Data Fetch | `/api/v1/data-fetch-status` | Data fetch monitoring |
| Ticker Validation | `/api/v1/ticker-validation` | Ticker symbol validation |

## Architecture

### Overview

The backend follows a layered architecture with domain-driven design:

```
domain/       Business rules, value objects, port interfaces
use_cases/    Application services (orchestrate domain + infra)
infra/        SQLAlchemy repositories, Celery tasks, cache adapters
api/          FastAPI routes (thin — delegates to use cases)
```

Dependency injection is wired in `wiring/bootstrap.py`.

### Scanners

| Screener | File | Criteria |
|----------|------|----------|
| Minervini Template | `minervini_scanner.py` | RS > 70-80, Stage 2 uptrend, MA alignment, price 30%+ above 52w low |
| CANSLIM | `canslim_scanner.py` | Quarterly EPS > 25%, annual EPS growth > 25% 3yr, volume patterns, RS > 70 |
| IPO | `ipo_scanner.py` | Recent IPOs with momentum characteristics |
| Volume Breakthrough | `volume_breakthrough_scanner.py` | Unusual volume with confirming price action |
| Custom | `custom_scanner.py` | 80+ configurable filters with saved presets |

All screeners extend `BaseStockScreener` and register via `@register_screener` in `screener_registry.py`. The `ScanOrchestrator` in `scan_orchestrator.py` coordinates execution. `DataPreparationLayer` (`data_preparation.py`) fetches price/fundamental data once and distributes it to all active screeners.

### Feature Store

Pre-computed daily stock snapshots. A scheduled feature run scores every stock in the universe, then atomically publishes via pointer swap. Scan API endpoints read from the latest published run.

Lifecycle: **RUNNING** → **COMPLETED** → quality checks → **PUBLISHED** (or **QUARANTINED**)

| Table | Purpose |
|-------|---------|
| `feature_runs` | Run metadata (status, timing, universe) |
| `feature_run_universe_symbols` | Symbols included in each run |
| `stock_feature_daily` | Per-stock computed features (scores, technicals, fundamentals) |
| `feature_run_pointers` | Atomic publish mechanism (pointer to latest valid run) |

Key files: `domain/feature_store/ports.py`, `domain/feature_store/models.py`, `infra/db/repositories/feature_store_repo.py`

### Background Tasks

Two Celery queues prevent API rate limit violations:

- **`celery`** queue: General compute tasks (4 workers locally, 1 in Docker for SQLite safety)
- **`data_fetch`** queue: External API calls (1 worker, serialized to respect rate limits)

| Task File | Description |
|-----------|-------------|
| `scan_tasks.py` | Scan orchestration and result persistence |
| `cache_tasks.py` | Redis cache warming and refresh |
| `breadth_tasks.py` | Market breadth calculation |
| `group_rank_tasks.py` | IBD group rank updates |
| `fundamentals_tasks.py` | Fundamental data fetching |
| `theme_discovery_tasks.py` | Theme clustering and extraction |
| `universe_tasks.py` | Stock universe updates |

### Caching

Three Redis databases:

| DB | Purpose | TTL |
|----|---------|-----|
| 0 | Celery broker | — |
| 1 | Celery results | 24h, auto-cleanup |
| 2 | Application cache | 7d (prices), 7d (fundamentals), 24h (SPY benchmark) |

SPY benchmark refresh uses distributed locking to prevent thundering herd on cache expiry. Connection pool managed in `services/redis_pool.py`.

### LLM Integration

Multi-provider support (Groq, DeepSeek, Together AI, OpenRouter, Gemini) with an agent orchestrator and tool executor pattern. Research mode integrates web search via Tavily, Serper, or DuckDuckGo.

Located in `services/chatbot/` and `services/llm/`.

## Database

SQLite at `data/stockscanner.db` (project root). Uses absolute path in `DATABASE_URL` to prevent working-directory issues.

### Tables by Category

**Core:**
`stock_prices`, `stock_fundamentals`, `stock_universe`, `stock_technicals`, `stock_industry`

**Feature Store:**
`feature_runs`, `feature_run_universe_symbols`, `stock_feature_daily`, `feature_run_pointers`

**Scanning:**
`scans`, `scan_results`

**Market Analysis:**
`market_breadth`, `market_status`, `ibd_industry_groups`, `ibd_group_ranks`, `ibd_group_peer_cache`

**Themes:**
`theme_clusters`, `theme_constituents`, `theme_metrics`, `theme_alerts`, `theme_pipeline_runs`, `content_sources`, `content_items`

**User Data:**
`user_watchlists`, `watchlist_items`, `user_themes`, `user_theme_subgroups`, `user_theme_stocks`, `chatbot_conversations`, `chatbot_messages`, `chatbot_folders`, `filter_presets`, `prompt_presets`

**System:**
`app_settings`, `task_execution_history`, `ticker_validation_log`, `document_cache`

Migrations in `app/db_migrations/` — idempotent, run on startup.

## Code Structure

```
app/
├── main.py                  # FastAPI application entry point
├── celery_app.py            # Celery application configuration
├── database.py              # SQLAlchemy engine and session setup
├── config/                  # Application configuration
├── api/v1/                  # FastAPI route handlers (21 modules)
├── models/                  # SQLAlchemy ORM models
├── schemas/                 # Pydantic request/response schemas
├── scanners/                # Stock screening implementations
│   ├── base_screener.py     #   Abstract base class
│   ├── screener_registry.py #   @register_screener decorator
│   ├── scan_orchestrator.py #   Multi-screener coordinator
│   ├── data_preparation.py  #   Shared data fetching layer
│   └── ...                  #   5 screener implementations
├── services/                # Business logic (70+ service files)
│   ├── chatbot/             #   LLM agent orchestration
│   ├── llm/                 #   Provider adapters
│   └── ...                  #   Data fetching, caching, analysis
├── tasks/                   # Celery background tasks
├── domain/                  # Business rules and port interfaces
│   ├── feature_store/       #   Feature Store domain model
│   ├── scanning/            #   Scan domain model
│   └── common/              #   Shared value objects
├── use_cases/               # Application services
│   ├── feature_store/       #   Feature Store orchestration
│   └── scanning/            #   Scan orchestration
├── infra/                   # Infrastructure implementations
│   ├── db/                  #   SQLAlchemy repositories
│   ├── cache/               #   Redis cache adapters
│   ├── tasks/               #   Celery task infrastructure
│   └── providers/           #   External service adapters
├── wiring/                  # Dependency injection
│   └── bootstrap.py         #   DI container setup
├── db_migrations/           # Idempotent migration scripts
└── utils/                   # Rate limiter, helpers
```

## Testing

```bash
pytest                                         # All tests
pytest tests/unit/                             # Unit only
pytest tests/integration/ -m integration       # Integration (needs running server)
pytest tests/unit/test_minervini_scanner.py -v # Specific file
```

> **Note**: Some unit tests make external API calls (yfinance, etc.). Target specific test files when iterating to avoid slow runs.

## Scripts

Diagnostic utilities in `scripts/`:

| Script | Description |
|--------|-------------|
| `inspect_redis.py` | Inspect Redis cache keys |
| `cache_diagnostic.py` | Trace cache flow (DB → Redis) |
| `check_cache_status.py` | Check price cache status |
| `clear_redis_price_cache.py` | Clear Redis cache after config change |
| `force_full_cache_refresh.py` | Force full cache refresh |
| `cleanup_orphaned_scans.py` | Clean up stale scans, VACUUM DB |

## Rate Limits

| Source | Limit | Notes |
|--------|-------|-------|
| yfinance | 1 req/sec | Self-imposed |
| Finviz | Rate-limited | Via wrapper |
| Alpha Vantage | 25 req/day | Free tier |
| SEC EDGAR | 10 req/sec | 150ms between requests |
