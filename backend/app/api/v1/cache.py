"""
Cache management API endpoints.

Provides endpoints for:
- Viewing cache statistics
- Triggering cache warming
- Invalidating caches
- Monitoring cache performance
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Optional, List
from pydantic import BaseModel

from ...services.cache_manager import CacheManager
from ...tasks.cache_tasks import (
    warm_spy_cache,
    warm_top_symbols,
    daily_cache_warmup,
    invalidate_cache as invalidate_cache_task,
    get_cache_stats as get_cache_stats_task,
    force_refresh_stale_intraday
)
from ...services.price_cache_service import PriceCacheService
from ...utils.market_hours import format_market_status, is_market_open
from ...database import SessionLocal
from ...models.stock import StockFundamental

router = APIRouter(prefix="/cache", tags=["cache"])


# Response Models
class CacheStatsResponse(BaseModel):
    """Cache statistics response model."""
    redis_connected: bool
    market_status: str
    spy_cache: dict
    price_cache: dict
    redis_memory: Optional[dict] = None


class CacheWarmRequest(BaseModel):
    """Request model for cache warming."""
    symbols: Optional[List[str]] = None
    count: Optional[int] = None
    force_refresh: bool = False


class CacheInvalidateRequest(BaseModel):
    """Request model for cache invalidation."""
    symbol: Optional[str] = None


class TaskResponse(BaseModel):
    """Generic task response model."""
    task_id: str
    message: str
    status: str


class DashboardStatsResponse(BaseModel):
    """Dashboard cache statistics response model."""
    fundamentals: dict
    prices: dict
    market_status: dict
    timestamp: str


class StalenessStatusResponse(BaseModel):
    """Staleness status response model."""
    stale_intraday_count: int
    stale_symbols: List[str]
    market_is_open: bool
    current_time_et: str
    has_stale_data: bool


class ForceRefreshRequest(BaseModel):
    """Request model for force refresh."""
    symbols: Optional[List[str]] = None  # None means refresh all stale symbols
    refresh_all: bool = False  # True = refresh ALL cached symbols, not just stale ones


# Endpoints
@router.get("/stats", response_model=CacheStatsResponse)
async def get_cache_statistics():
    """
    Get comprehensive cache statistics.

    Returns:
        Cache statistics including Redis status, SPY cache, price cache, and memory usage
    """
    try:
        cache_manager = CacheManager()
        stats = cache_manager.get_cache_stats()
        return stats

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching cache stats: {str(e)}"
        )


@router.get("/market-status")
async def get_market_status():
    """
    Get current market status and hours.

    Returns:
        Market status information
    """
    return {
        "status": format_market_status(),
        "is_open": is_market_open(),
        "timestamp": "now"
    }


@router.post("/warm/spy")
async def warm_spy_benchmark_cache(background_tasks: BackgroundTasks):
    """
    Warm SPY benchmark cache.

    This endpoint triggers background warming of the SPY benchmark data.

    Returns:
        Task information
    """
    try:
        # Run task in background
        task = warm_spy_cache.delay()

        return TaskResponse(
            task_id=task.id,
            message="SPY cache warming task queued",
            status="queued"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error queuing SPY cache warming: {str(e)}"
        )


@router.post("/warm/symbols")
async def warm_symbol_cache(
    request: CacheWarmRequest,
    background_tasks: BackgroundTasks
):
    """
    Warm cache for specific symbols.

    Args:
        request: Cache warming request with symbols or count

    Returns:
        Task information
    """
    try:
        # Run task in background
        task = warm_top_symbols.delay(
            symbols=request.symbols,
            count=request.count
        )

        # Determine message based on parameters
        if request.symbols:
            symbol_count = len(request.symbols)
            message = f"Symbol cache warming task queued for {symbol_count} symbols"
        elif request.count:
            message = f"Symbol cache warming task queued for top {request.count} symbols"
        else:
            message = "Symbol cache warming task queued for ALL active stocks in universe"

        return TaskResponse(
            task_id=task.id,
            message=message,
            status="queued"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error queuing symbol cache warming: {str(e)}"
        )


@router.post("/warm/all")
async def warm_all_caches(background_tasks: BackgroundTasks):
    """
    Warm all caches (SPY + ALL active stocks).

    This triggers the daily cache warmup task which warms:
    - SPY benchmark cache
    - ALL active symbols in the stock universe

    Returns:
        Task information
    """
    try:
        # Run daily warmup task in background
        task = daily_cache_warmup.delay()

        return TaskResponse(
            task_id=task.id,
            message="Full cache warming task queued for ALL active stocks in universe",
            status="queued"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error queuing full cache warming: {str(e)}"
        )


@router.delete("/invalidate")
async def invalidate_caches(request: CacheInvalidateRequest):
    """
    Invalidate cache for a symbol or all caches.

    Args:
        request: Invalidation request with optional symbol

    Returns:
        Invalidation result
    """
    try:
        # Run invalidation task
        task = invalidate_cache_task.delay(symbol=request.symbol)

        message = f"Cache invalidation queued for {request.symbol}" if request.symbol else "All caches invalidation queued"

        return TaskResponse(
            task_id=task.id,
            message=message,
            status="queued"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error invalidating cache: {str(e)}"
        )


@router.get("/hit-rate")
async def get_cache_hit_rate():
    """
    Get cache hit rate statistics.

    Returns:
        Cache hit rate percentage
    """
    try:
        cache_manager = CacheManager()
        hit_rate = cache_manager.get_cache_hit_rate()

        return {
            "hit_rate": hit_rate,
            "hit_rate_str": f"{hit_rate:.1f}%" if hit_rate is not None else "N/A",
            "available": hit_rate is not None
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating hit rate: {str(e)}"
        )


@router.get("/staleness-status", response_model=StalenessStatusResponse)
async def get_staleness_status():
    """
    Get intraday data staleness status.

    Returns information about symbols with stale intraday data:
    - Data fetched during market hours that is now stale (after market close)
    - Count of affected symbols
    - Current market status

    Use this to determine if force-refresh is needed.
    """
    try:
        price_cache = PriceCacheService.get_instance()
        status = price_cache.get_staleness_status()
        return StalenessStatusResponse(**status)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error checking staleness status: {str(e)}"
        )


@router.post("/force-refresh")
async def force_refresh_stale_data(
    request: ForceRefreshRequest,
    background_tasks: BackgroundTasks
):
    """
    Force refresh stale intraday price data.

    This endpoint triggers a background task to refresh symbols that have
    stale intraday data (data fetched during market hours that is now
    outdated after market close).

    Args:
        request:
            - symbols: Optional list of symbols to refresh
            - refresh_all: If True, refresh ALL cached symbols (not just stale ones)

    Returns:
        Task information with task_id for tracking
    """
    try:
        price_cache = PriceCacheService.get_instance()

        # Get symbols to refresh
        if request.symbols:
            symbols = request.symbols
            message = f"Force refresh queued for {len(symbols)} symbols"
        elif request.refresh_all:
            # Get ALL cached symbols from Redis
            symbols = price_cache.get_all_cached_symbols()
            if not symbols:
                return {
                    "task_id": None,
                    "message": "No cached symbols found",
                    "status": "skipped",
                    "symbols_count": 0
                }
            message = f"Force refresh queued for ALL {len(symbols)} cached symbols"
        else:
            # Get only stale symbols
            symbols = price_cache.get_stale_intraday_symbols()

            if not symbols:
                return {
                    "task_id": None,
                    "message": "No stale intraday data detected",
                    "status": "skipped",
                    "symbols_count": 0
                }

            message = f"Force refresh queued for {len(symbols)} stale symbols"

        # Queue the force refresh task
        task = force_refresh_stale_intraday.delay(symbols=symbols)

        return TaskResponse(
            task_id=task.id,
            message=message,
            status="queued"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error queuing force refresh: {str(e)}"
        )


@router.get("/symbol/{symbol}")
async def get_symbol_cache_info(symbol: str):
    """
    Get cache information for a specific symbol.

    Args:
        symbol: Stock symbol

    Returns:
        Cache information for the symbol
    """
    try:
        cache_manager = CacheManager()
        stats = cache_manager.price_cache.get_cache_stats(symbol)

        return stats

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching cache info for {symbol}: {str(e)}"
        )


@router.get("/dashboard-stats", response_model=DashboardStatsResponse)
async def get_dashboard_cache_statistics():
    """
    Get comprehensive cache statistics for UI dashboard.

    This endpoint aggregates cache health metrics from all cache services:
    - Fundamentals cache (Redis + DB)
    - Price/technical data cache (SPY + symbols)
    - Market status

    Returns:
        Comprehensive dashboard statistics including freshness, hit rates,
        and last update times for all cache types
    """
    try:
        from datetime import datetime
        from ...models.stock_universe import StockUniverse

        # Get fundamentals cache stats using efficient SQL aggregate queries
        db = SessionLocal()
        try:
            from sqlalchemy import func
            from datetime import timedelta

            # Get total active stocks count
            total_stocks = db.query(func.count(StockUniverse.id)).filter(
                StockUniverse.is_active == True
            ).scalar()

            # Get fundamentals counts using efficient SQL aggregates
            seven_days_ago = datetime.now() - timedelta(days=7)

            # Total cached (all rows in stock_fundamentals)
            cached_count = db.query(func.count(StockFundamental.id)).scalar()

            # Fresh count (updated within 7 days)
            fresh_count = db.query(func.count(StockFundamental.id)).filter(
                StockFundamental.updated_at >= seven_days_ago
            ).scalar()

            # Stale count
            stale_count = cached_count - fresh_count

            fundamentals_stats = {
                'total_stocks': total_stocks,
                'cached_count': cached_count,
                'fresh_count': fresh_count,
                'stale_count': stale_count,
                'hit_rate': round(cached_count / total_stocks * 100, 1) if total_stocks > 0 else 0
            }

            # Get most recent fundamental update from database
            latest_fundamental = db.query(StockFundamental).order_by(
                StockFundamental.updated_at.desc()
            ).first()
            last_fundamental_update = latest_fundamental.updated_at.isoformat() if latest_fundamental else None

        finally:
            db.close()

        # Get price cache stats
        cache_manager = CacheManager()
        price_stats = cache_manager.get_cache_stats()

        # Extract SPY cache info (corrected key names)
        spy_cache = price_stats.get('spy_cache', {})
        spy_cached = spy_cache.get('2y_cached', False)
        spy_ttl_seconds = spy_cache.get('2y_ttl', 0)
        spy_ttl = (spy_ttl_seconds / 3600) if spy_ttl_seconds else 0  # Convert seconds to hours

        # Get market status
        market_status = {
            "is_open": is_market_open(),
            "status": format_market_status(),
            "next_open": "N/A"  # Could be enhanced with next market open time
        }

        # Build dashboard response
        dashboard_stats = {
            "fundamentals": {
                "total_stocks": fundamentals_stats.get('total_stocks', 0),
                "cached_count": fundamentals_stats.get('cached_count', 0),
                "fresh_count": fundamentals_stats.get('fresh_count', 0),
                "stale_count": fundamentals_stats.get('stale_count', 0),
                "last_update": last_fundamental_update,
                "hit_rate": fundamentals_stats.get('hit_rate', 0)
            },
            "prices": {
                "spy_cached": spy_cached,
                "spy_last_update": "N/A",  # Could be enhanced to extract last update date
                "spy_ttl_hours": round(spy_ttl, 1),
                "total_symbols_cached": price_stats.get('price_cache', {}).get('symbols_cached', 0),
                "last_warmup": "N/A"  # Could track last warmup timestamp
            },
            "market_status": market_status,
            "timestamp": datetime.now().isoformat()
        }

        return DashboardStatsResponse(**dashboard_stats)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching dashboard stats: {str(e)}"
        )
