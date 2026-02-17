"""SQLAlchemy implementation of ScanResultRepository."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.domain.scanning.ports import ScanResultRepository
from app.models.scan_result import ScanResult

logger = logging.getLogger(__name__)


def _map_orchestrator_result(scan_id: str, symbol: str, raw: dict) -> dict:
    """Map a raw orchestrator result dict to ScanResult column values.

    This is a **pure function** — no DB queries, no side-effects.
    IBD/GICS classification lookups are *not* performed here; if needed
    the caller should pre-populate ``ibd_industry_group`` etc. in *raw*.
    """
    r: dict[str, Any] = {}

    r["scan_id"] = scan_id
    r["symbol"] = symbol.upper()

    # Scores
    r["composite_score"] = raw.get("composite_score", raw.get("minervini_score", 0))
    r["minervini_score"] = raw.get("minervini_score")
    r["canslim_score"] = raw.get("canslim_score")
    r["ipo_score"] = raw.get("ipo_score")
    r["custom_score"] = raw.get("custom_score")
    r["volume_breakthrough_score"] = raw.get("volume_breakthrough_score")

    # Rating (backward-compat fallback)
    rating = raw.get("rating")
    if not rating:
        passes = raw.get("passes_template", False)
        cs = r["composite_score"] or 0
        if passes and cs >= 80:
            rating = "Strong Buy"
        elif passes:
            rating = "Buy"
        elif cs >= 60:
            rating = "Watch"
        else:
            rating = "Pass"
    r["rating"] = rating

    # Price / volume / cap
    r["price"] = raw.get("current_price")
    r["volume"] = raw.get("avg_dollar_volume")
    r["market_cap"] = raw.get("market_cap")

    # Indexed technical fields
    r["stage"] = raw.get("stage")
    r["rs_rating"] = raw.get("rs_rating")
    r["rs_rating_1m"] = raw.get("rs_rating_1m")
    r["rs_rating_3m"] = raw.get("rs_rating_3m")
    r["rs_rating_12m"] = raw.get("rs_rating_12m")
    r["eps_growth_qq"] = raw.get("eps_growth_qq")
    r["sales_growth_qq"] = raw.get("sales_growth_qq")
    r["eps_growth_yy"] = raw.get("eps_growth_yy")
    r["sales_growth_yy"] = raw.get("sales_growth_yy")
    r["peg_ratio"] = raw.get("peg_ratio")
    r["adr_percent"] = raw.get("adr_percent")
    r["eps_rating"] = raw.get("eps_rating")
    r["ipo_date"] = raw.get("ipo_date")

    # Beta / Beta-Adjusted RS
    r["beta"] = raw.get("beta")
    r["beta_adj_rs"] = raw.get("beta_adj_rs")
    r["beta_adj_rs_1m"] = raw.get("beta_adj_rs_1m")
    r["beta_adj_rs_3m"] = raw.get("beta_adj_rs_3m")
    r["beta_adj_rs_12m"] = raw.get("beta_adj_rs_12m")

    # Sparklines
    r["rs_sparkline_data"] = raw.get("rs_sparkline_data")
    r["rs_trend"] = raw.get("rs_trend")
    r["price_sparkline_data"] = raw.get("price_sparkline_data")
    r["price_change_1d"] = raw.get("price_change_1d")
    r["price_trend"] = raw.get("price_trend")

    # Performance metrics
    r["perf_week"] = raw.get("perf_week")
    r["perf_month"] = raw.get("perf_month")
    r["perf_3m"] = raw.get("perf_3m")
    r["perf_6m"] = raw.get("perf_6m")

    # Episodic Pivot
    r["gap_percent"] = raw.get("gap_percent")
    r["volume_surge"] = raw.get("volume_surge")

    # EMA distances
    r["ema_10_distance"] = raw.get("ema_10_distance")
    r["ema_20_distance"] = raw.get("ema_20_distance")
    r["ema_50_distance"] = raw.get("ema_50_distance")

    # 52-week distances
    r["week_52_high_distance"] = raw.get("from_52w_high_pct")
    r["week_52_low_distance"] = raw.get("above_52w_low_pct")

    # IBD/GICS (caller may pre-populate in raw)
    r["ibd_industry_group"] = raw.get("ibd_industry_group")
    r["ibd_group_rank"] = raw.get("ibd_group_rank")
    r["gics_sector"] = raw.get("gics_sector")
    r["gics_industry"] = raw.get("gics_industry")

    # Full result dict stored as JSON
    r["details"] = raw

    return r


class SqlScanResultRepository(ScanResultRepository):
    """Persist and retrieve ScanResult rows via SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def bulk_insert(self, rows: list[dict]) -> int:
        objects = [ScanResult(**row) for row in rows]
        self._session.bulk_save_objects(objects)
        self._session.flush()
        return len(objects)

    def persist_orchestrator_results(
        self, scan_id: str, results: list[tuple[str, dict]]
    ) -> int:
        rows = [
            _map_orchestrator_result(scan_id, symbol, result)
            for symbol, result in results
        ]
        return self.bulk_insert(rows)

    def count_by_scan_id(self, scan_id: str) -> int:
        return (
            self._session.query(func.count(ScanResult.id))
            .filter(ScanResult.scan_id == scan_id)
            .scalar()
            or 0
        )
