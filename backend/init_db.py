#!/usr/bin/env python3
"""
Database initialization script.

Creates all required tables in the database.
"""
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from app.database import engine, Base

# Import all models to ensure they're registered with Base
# Only import the main scan-related models for now
from app.models.scan_result import Scan, ScanResult
from app.models.stock import StockPrice, StockFundamental, StockTechnical, StockIndustry
from app.models.market_breadth import MarketBreadth
try:
    from app.models.stock_universe import StockUniverse
except ImportError:
    pass
try:
    import app.models.industry
except ImportError:
    pass
try:
    import app.models.watchlist
except ImportError:
    pass

import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def init_database():
    """Initialize database by creating all tables."""
    try:
        logger.info("Starting database initialization...")

        # Models are already imported at module level
        logger.info("Models loaded:")

        # Create all tables
        logger.info("\nCreating tables...")
        Base.metadata.create_all(bind=engine)

        logger.info("\n✅ Database initialized successfully!")
        logger.info("\nTables created:")
        for table in Base.metadata.sorted_tables:
            logger.info(f"  - {table.name}")

        return True

    except Exception as e:
        logger.error(f"\n❌ Database initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = init_database()
    sys.exit(0 if success else 1)
