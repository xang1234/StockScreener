"""Main API router"""
from fastapi import APIRouter
from . import stocks, technical, scans, universe, cache, breadth, fundamentals, groups, themes, tasks, chatbot, chatbot_folders, market_scan, user_themes, user_watchlists, data_fetch_status, ticker_validation, filter_presets, prompt_presets, config

# Create main router
router = APIRouter()

# Include sub-routers
router.include_router(stocks.router, prefix="/stocks", tags=["stocks"])
router.include_router(technical.router, prefix="/technical", tags=["technical"])
router.include_router(scans.router, prefix="/scans", tags=["scans"])
router.include_router(universe.router, prefix="/universe", tags=["universe"])
router.include_router(cache.router, tags=["cache"])
router.include_router(breadth.router, prefix="/breadth", tags=["breadth"])
router.include_router(fundamentals.router, tags=["fundamentals"])
router.include_router(groups.router, prefix="/groups", tags=["groups"])
router.include_router(themes.router, prefix="/themes", tags=["themes"])
router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
router.include_router(chatbot.router, prefix="/chatbot", tags=["chatbot"])
router.include_router(chatbot_folders.router, prefix="/chatbot/folders", tags=["chatbot-folders"])
router.include_router(market_scan.router, prefix="/market-scan", tags=["market-scan"])
router.include_router(user_themes.router, prefix="/user-themes", tags=["user-themes"])
router.include_router(user_watchlists.router, prefix="/user-watchlists", tags=["user-watchlists"])
router.include_router(data_fetch_status.router, tags=["data-fetch"])
router.include_router(ticker_validation.router, prefix="/ticker-validation", tags=["ticker-validation"])
router.include_router(filter_presets.router, prefix="/filter-presets", tags=["filter-presets"])
router.include_router(prompt_presets.router, prefix="/prompt-presets", tags=["prompt-presets"])
router.include_router(config.router, tags=["config"])
