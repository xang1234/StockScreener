"""Stock data API endpoints"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional
from datetime import datetime, timedelta
import logging

from ...database import get_db
from ...services.data_fetcher import DataFetcher
from ...services.yfinance_service import yfinance_service
from ...schemas.stock import StockInfo, StockFundamentals, StockTechnicals, StockData
from ...models.scan_result import Scan, ScanResult

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/{symbol}/info", response_model=StockInfo)
async def get_stock_info(symbol: str):
    """
    Get basic stock information.

    Args:
        symbol: Stock ticker symbol (e.g., AAPL, MSFT)

    Returns:
        Basic stock information
    """
    info = yfinance_service.get_stock_info(symbol.upper())

    if not info:
        logger.error(f"Failed to fetch stock info for {symbol} - check yfinance service logs for details")
        raise HTTPException(
            status_code=404,
            detail=f"Unable to fetch data for {symbol}. This could be due to: invalid symbol, network issues, or yfinance API problems. Check backend logs for details."
        )

    return info


@router.get("/{symbol}/fundamentals")
async def get_stock_fundamentals(
    symbol: str,
    force_refresh: bool = False,
    db: Session = Depends(get_db)
):
    """
    Get stock fundamental data.

    Args:
        symbol: Stock ticker symbol
        force_refresh: Force data refresh (ignore cache)

    Returns:
        Fundamental data including earnings, revenue, margins, description
    """
    from ...services.fundamentals_cache_service import FundamentalsCacheService

    cache = FundamentalsCacheService.get_instance()
    data = cache.get_fundamentals(symbol.upper(), force_refresh=force_refresh)

    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"Fundamental data not available for {symbol}"
        )

    # Add symbol to response if not present
    if 'symbol' not in data:
        data['symbol'] = symbol.upper()

    return data


@router.get("/{symbol}/technicals", response_model=StockTechnicals)
async def get_stock_technicals(
    symbol: str,
    force_refresh: bool = False,
    db: Session = Depends(get_db)
):
    """
    Get stock technical indicators.

    Args:
        symbol: Stock ticker symbol
        force_refresh: Force data refresh (ignore cache)

    Returns:
        Technical indicators including MAs, RS rating, 52-week range
    """
    fetcher = DataFetcher(db)
    data = fetcher.get_stock_technicals(symbol.upper(), force_refresh=force_refresh)

    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"Technical data not available for {symbol}"
        )

    return data


@router.get("/{symbol}", response_model=StockData)
async def get_stock_data(
    symbol: str,
    include_fundamentals: bool = True,
    include_technicals: bool = True,
    force_refresh: bool = False,
    db: Session = Depends(get_db)
):
    """
    Get complete stock data (info + fundamentals + technicals).

    Args:
        symbol: Stock ticker symbol
        include_fundamentals: Include fundamental data
        include_technicals: Include technical indicators
        force_refresh: Force data refresh (ignore cache)

    Returns:
        Complete stock data
    """
    symbol = symbol.upper()

    # Get basic info
    info = yfinance_service.get_stock_info(symbol)
    if not info:
        logger.error(f"Failed to fetch stock info for {symbol} - check yfinance service logs for details")
        raise HTTPException(
            status_code=404,
            detail=f"Unable to fetch data for {symbol}. This could be due to: invalid symbol, network issues, or yfinance API problems. Check backend logs for details."
        )

    result = {"info": info}

    # Get fundamentals if requested
    if include_fundamentals:
        fetcher = DataFetcher(db)
        fundamentals = fetcher.get_stock_fundamentals(symbol, force_refresh=force_refresh)
        result["fundamentals"] = fundamentals

    # Get technicals if requested
    if include_technicals:
        fetcher = DataFetcher(db)
        technicals = fetcher.get_stock_technicals(symbol, force_refresh=force_refresh)
        result["technicals"] = technicals

    return result


@router.get("/{symbol}/industry")
async def get_stock_industry(symbol: str, db: Session = Depends(get_db)):
    """
    Get stock industry classification.

    Args:
        symbol: Stock ticker symbol

    Returns:
        Industry classification (sector, industry, ibd_industry_group)
    """
    from ...services.ibd_industry_service import IBDIndustryService

    fetcher = DataFetcher(db)
    classification = fetcher.get_industry_classification(symbol.upper())

    if not classification:
        raise HTTPException(
            status_code=404,
            detail=f"Industry classification not available for {symbol}"
        )

    # Add IBD industry group if available
    try:
        ibd_group = IBDIndustryService.get_industry_group(db, symbol.upper())
        classification['ibd_industry_group'] = ibd_group
    except Exception as e:
        logger.warning(f"Could not fetch IBD industry group for {symbol}: {e}")
        classification['ibd_industry_group'] = None

    return classification


@router.get("/{symbol}/chart-data")
async def get_chart_data(symbol: str, db: Session = Depends(get_db)):
    """
    Get all chart modal data in a single call.
    Prioritizes scan_results lookup (fast), falls back to computation (slow).

    Returns all data needed for the chart modal:
    - Basic info (symbol, name, price)
    - Industry classification (GICS sector/industry, IBD group)
    - RS ratings (overall, 1m, 3m, 12m, trend)
    - Technical data (stage, ADR, EPS rating)
    - Minervini/VCP data
    - Growth metrics
    """
    symbol = symbol.upper()

    # Try to get from recent scan_results (fast path)
    # Look for completed scans from the last 7 days
    cutoff_date = datetime.utcnow() - timedelta(days=7)

    # Get the most recent completed scan
    recent_scan = db.query(Scan).filter(
        Scan.status == "completed",
        Scan.completed_at >= cutoff_date
    ).order_by(desc(Scan.completed_at)).first()

    scan_result = None
    if recent_scan:
        scan_result = db.query(ScanResult).filter(
            ScanResult.scan_id == recent_scan.scan_id,
            ScanResult.symbol == symbol
        ).first()

    if scan_result:
        # Fast path: return data from scan_results
        details = scan_result.details or {}

        return {
            "source": "scan_results",
            "scan_date": recent_scan.completed_at.isoformat() if recent_scan.completed_at else None,
            # Basic info
            "symbol": scan_result.symbol,
            "company_name": details.get("company_name"),
            "current_price": scan_result.price,
            # Industry classification
            "gics_sector": scan_result.gics_sector,
            "gics_industry": scan_result.gics_industry,
            "ibd_industry_group": scan_result.ibd_industry_group,
            "ibd_group_rank": scan_result.ibd_group_rank,
            # RS data
            "rs_rating": scan_result.rs_rating,
            "rs_rating_1m": scan_result.rs_rating_1m,
            "rs_rating_3m": scan_result.rs_rating_3m,
            "rs_rating_12m": scan_result.rs_rating_12m,
            "rs_trend": scan_result.rs_trend,
            # Technical data
            "stage": scan_result.stage,
            "adr_percent": scan_result.adr_percent,
            "eps_rating": scan_result.eps_rating,
            # Scores
            "minervini_score": scan_result.minervini_score,
            "composite_score": scan_result.composite_score,
            # VCP data from details
            "vcp_detected": details.get("vcp_detected", False),
            "vcp_score": details.get("vcp_score"),
            "vcp_pivot": details.get("vcp_pivot"),
            "vcp_ready_for_breakout": details.get("vcp_ready_for_breakout", False),
            # MA data from details
            "ma_alignment": details.get("ma_alignment"),
            "passes_template": details.get("passes_template"),
            # Growth metrics
            "eps_growth_qq": scan_result.eps_growth_qq,
            "sales_growth_qq": scan_result.sales_growth_qq,
            "eps_growth_yy": scan_result.eps_growth_yy,
            "sales_growth_yy": scan_result.sales_growth_yy,
        }

    # Slow path: compute data from individual services
    logger.info(f"Chart data for {symbol} not in recent scans, computing...")

    try:
        # Get basic stock info
        info = yfinance_service.get_stock_info(symbol)
        if not info:
            raise HTTPException(
                status_code=404,
                detail=f"Unable to fetch data for {symbol}"
            )

        # Get fundamentals
        from ...services.fundamentals_cache_service import FundamentalsCacheService
        cache = FundamentalsCacheService.get_instance()
        fundamentals = cache.get_fundamentals(symbol) or {}

        # Get technicals
        fetcher = DataFetcher(db)
        technicals = fetcher.get_stock_technicals(symbol) or {}

        # Get industry classification
        classification = fetcher.get_industry_classification(symbol) or {}

        # Get IBD industry group
        from ...services.ibd_industry_service import IBDIndustryService
        try:
            ibd_group = IBDIndustryService.get_industry_group(db, symbol)
        except Exception:
            ibd_group = None

        # Get RS rating data
        try:
            from ...services.rs_rating_service import RSRatingService
            rs_service = RSRatingService()
            rs_data = rs_service.get_rs_rating(symbol) or {}
        except Exception:
            rs_data = {}

        # Get Minervini scan data for VCP and ADR
        try:
            from ...scanners.minervini_scanner_v2 import MinerviniScannerV2
            scanner = MinerviniScannerV2(db)
            minervini_result = scanner.scan_stock(symbol) or {}
        except Exception as e:
            logger.warning(f"Could not get Minervini scan for {symbol}: {e}")
            minervini_result = {}

        vcp_data = minervini_result.get("vcp", {}) or {}

        return {
            "source": "computed",
            "scan_date": None,
            # Basic info
            "symbol": symbol,
            "company_name": info.get("name"),
            "current_price": technicals.get("current_price") or info.get("current_price"),
            # Industry classification
            "gics_sector": info.get("sector"),
            "gics_industry": info.get("industry"),
            "ibd_industry_group": ibd_group,
            "ibd_group_rank": None,  # Would require additional query
            # RS data
            "rs_rating": rs_data.get("rs_rating") or technicals.get("rs_rating"),
            "rs_rating_1m": rs_data.get("rs_1m"),
            "rs_rating_3m": rs_data.get("rs_3m"),
            "rs_rating_12m": rs_data.get("rs_12m"),
            "rs_trend": rs_data.get("rs_trend"),
            # Technical data
            "stage": technicals.get("stage"),
            "adr_percent": minervini_result.get("adr_percent"),
            "eps_rating": fundamentals.get("eps_rating"),
            # Scores
            "minervini_score": minervini_result.get("score"),
            "composite_score": None,
            # VCP data
            "vcp_detected": vcp_data.get("detected", False),
            "vcp_score": vcp_data.get("score") or technicals.get("vcp_score"),
            "vcp_pivot": vcp_data.get("pivot_price"),
            "vcp_ready_for_breakout": vcp_data.get("ready_for_breakout", False),
            # MA data
            "ma_alignment": minervini_result.get("ma_alignment"),
            "passes_template": minervini_result.get("passes_template"),
            # Growth metrics
            "eps_growth_qq": fundamentals.get("eps_growth_quarterly"),
            "sales_growth_qq": fundamentals.get("sales_growth_qq"),
            "eps_growth_yy": fundamentals.get("eps_growth_annual"),
            "sales_growth_yy": fundamentals.get("sales_growth_yy"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error computing chart data for {symbol}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching chart data for {symbol}: {str(e)}"
        )


@router.get("/{symbol}/history")
async def get_price_history(symbol: str, period: str = "6mo"):
    """
    Get historical price data (OHLCV only) from cache.
    Uses cached data from database/Redis - does not call yfinance directly.
    """
    from ...services.price_cache_service import PriceCacheService
    import pandas as pd

    # Map period to days for filtering
    period_days = {
        "1mo": 30,
        "3mo": 90,
        "6mo": 180,
        "1y": 365,
        "2y": 730,
        "5y": 1825,
    }
    days = period_days.get(period, 180)

    # Get from cache (database) - no yfinance calls
    cache_service = PriceCacheService.get_instance()
    data = cache_service.get_cached_only(symbol.upper(), period="2y")

    if data is None or len(data) == 0:
        logger.warning(f"No cached data for {symbol}")
        raise HTTPException(
            status_code=404,
            detail=f"Historical data not available for {symbol}. Run a scan to populate cache."
        )

    logger.info(f"Retrieved {len(data)} rows from cache for {symbol}")

    # Filter to requested period using pandas Timestamp for timezone safety
    from datetime import datetime, timedelta
    cutoff_date = pd.Timestamp(datetime.now() - timedelta(days=days))

    # Handle timezone-aware index
    if data.index.tz is not None:
        cutoff_date = cutoff_date.tz_localize(data.index.tz)

    data = data[data.index >= cutoff_date]

    if len(data) == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No data available for {symbol} in the last {period}"
        )

    # Convert to list of dicts for JSON response
    # Reset index and ensure column is named 'Date'
    df = data.reset_index()
    # The first column after reset_index is the former index
    date_col = df.columns[0]
    df = df.rename(columns={date_col: 'Date'})

    # Convert dates to string format
    df['Date'] = pd.to_datetime(df['Date']).dt.strftime('%Y-%m-%d')

    result = []
    for _, row in df.iterrows():
        result.append({
            'date': row['Date'],
            'open': round(float(row['Open']), 2),
            'high': round(float(row['High']), 2),
            'low': round(float(row['Low']), 2),
            'close': round(float(row['Close']), 2),
            'volume': int(row['Volume']),
        })

    logger.info(f"Returning {len(result)} price records for {symbol}")
    return result
