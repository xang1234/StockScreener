"""SQLAlchemy query builder for feature store results.

Translates domain FilterSpec / SortSpec / PageSpec into SQLAlchemy
WHERE, ORDER BY, and LIMIT/OFFSET clauses for StockFeatureDaily.
Handles both indexed SQL columns and json_extract() for fields
stored in the details_json blob.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Float as SAFloat, and_, asc, cast, desc, func
from sqlalchemy.orm import Query

from app.domain.common.query import (
    BooleanFilter,
    CategoricalFilter,
    FilterMode,
    FilterSpec,
    PageSpec,
    RangeFilter,
    SortOrder,
    SortSpec,
    TextSearchFilter,
)
from app.infra.db.models.feature_store import StockFeatureDaily

# ── Column resolution ───────────────────────────────────────────────────

# Maps domain filter/sort field names to StockFeatureDaily column attributes.
_COLUMN_MAP: dict[str, Any] = {
    "symbol": StockFeatureDaily.symbol,
    "composite_score": StockFeatureDaily.composite_score,
    "overall_rating": StockFeatureDaily.overall_rating,
    "passes_count": StockFeatureDaily.passes_count,
    "as_of_date": StockFeatureDaily.as_of_date,
}

# JSON details paths for fields stored in details_json.
# These map domain filter/sort field names to json_extract() paths
# within the full orchestrator result dict stored as details_json.
_JSON_FIELD_MAP: dict[str, str] = {
    # Scores
    "minervini_score": "$.minervini_score",
    "canslim_score": "$.canslim_score",
    "ipo_score": "$.ipo_score",
    "custom_score": "$.custom_score",
    "volume_breakthrough_score": "$.volume_breakthrough_score",
    # Price / volume
    "price": "$.current_price",
    "current_price": "$.current_price",
    "volume": "$.avg_dollar_volume",
    "market_cap": "$.market_cap",
    # Technicals
    "stage": "$.stage",
    "rating": "$.rating",
    "rs_rating": "$.rs_rating",
    "rs_rating_1m": "$.rs_rating_1m",
    "rs_rating_3m": "$.rs_rating_3m",
    "rs_rating_12m": "$.rs_rating_12m",
    "adr_percent": "$.adr_percent",
    # Fundamentals
    "eps_growth_qq": "$.eps_growth_qq",
    "sales_growth_qq": "$.sales_growth_qq",
    "eps_growth_yy": "$.eps_growth_yy",
    "sales_growth_yy": "$.sales_growth_yy",
    "peg_ratio": "$.peg_ratio",
    "peg": "$.peg_ratio",
    "eps_rating": "$.eps_rating",
    # Classification
    "ibd_industry_group": "$.ibd_industry_group",
    "ibd_group_rank": "$.ibd_group_rank",
    "gics_sector": "$.gics_sector",
    "gics_industry": "$.gics_industry",
    # Performance
    "perf_week": "$.perf_week",
    "perf_month": "$.perf_month",
    "perf_3m": "$.perf_3m",
    "perf_6m": "$.perf_6m",
    # Sparkline meta
    "rs_trend": "$.rs_trend",
    "price_change_1d": "$.price_change_1d",
    "price_trend": "$.price_trend",
    # Beta
    "beta": "$.beta",
    "beta_adj_rs": "$.beta_adj_rs",
    "beta_adj_rs_1m": "$.beta_adj_rs_1m",
    "beta_adj_rs_3m": "$.beta_adj_rs_3m",
    "beta_adj_rs_12m": "$.beta_adj_rs_12m",
    # Distances
    "ema_10_distance": "$.ema_10_distance",
    "ema_20_distance": "$.ema_20_distance",
    "ema_50_distance": "$.ema_50_distance",
    "week_52_high_distance": "$.from_52w_high_pct",
    "week_52_low_distance": "$.above_52w_low_pct",
    # Episodic pivot
    "gap_percent": "$.gap_percent",
    "volume_surge": "$.volume_surge",
    # IPO / dates
    "ipo_date": "$.ipo_date",
    # VCP / details-only fields
    "vcp_score": "$.vcp_score",
    "vcp_pivot": "$.vcp_pivot",
    "vcp_detected": "$.vcp_detected",
    "vcp_ready_for_breakout": "$.vcp_ready_for_breakout",
    "ma_alignment": "$.ma_alignment",
    "stage_name": "$.stage_name",
    "passes_template": "$.passes_template",
    "vcp_contraction_ratio": "$.vcp_contraction_ratio",
    "vcp_atr_score": "$.vcp_atr_score",
}


# ── Public API ──────────────────────────────────────────────────────────


def apply_filters(query: Query, filters: FilterSpec) -> Query:
    """Apply all FilterSpec constraints as SQLAlchemy WHERE clauses."""
    for rf in filters.range_filters:
        query = _apply_range_filter(query, rf)
    for cf in filters.categorical_filters:
        query = _apply_categorical_filter(query, cf)
    for bf in filters.boolean_filters:
        query = _apply_boolean_filter(query, bf)
    for ts in filters.text_searches:
        query = _apply_text_search(query, ts)
    return query


def apply_sort_and_paginate(
    query: Query,
    sort: SortSpec,
    page: PageSpec,
) -> tuple[list, int]:
    """Apply sort + pagination.  Returns (rows, total_count)."""
    total = query.count()

    col = _COLUMN_MAP.get(sort.field)
    if col is not None:
        order_fn = asc if sort.order == SortOrder.ASC else desc
        query = query.order_by(order_fn(col))
    elif sort.field in _JSON_FIELD_MAP:
        json_path = _JSON_FIELD_MAP[sort.field]
        json_val = func.json_extract(StockFeatureDaily.details_json, json_path)
        order_fn = asc if sort.order == SortOrder.ASC else desc
        query = query.order_by(order_fn(json_val))
    else:
        # Unknown sort field — fall back to composite_score desc
        query = query.order_by(desc(StockFeatureDaily.composite_score))

    query = query.offset(page.offset).limit(page.limit)
    rows = query.all()

    return rows, total


# ── Private helpers ─────────────────────────────────────────────────────


def _apply_range_filter(query: Query, rf: RangeFilter) -> Query:
    """Apply a numeric range filter — SQL column or json_extract."""
    col = _COLUMN_MAP.get(rf.field)
    if col is not None:
        if rf.min_value is not None:
            query = query.filter(col >= rf.min_value)
        if rf.max_value is not None:
            query = query.filter(col <= rf.max_value)
    elif rf.field in _JSON_FIELD_MAP:
        json_path = _JSON_FIELD_MAP[rf.field]
        json_val = func.json_extract(StockFeatureDaily.details_json, json_path)
        if rf.min_value is not None:
            query = query.filter(and_(
                json_val.isnot(None),
                cast(json_val, SAFloat) >= rf.min_value,
            ))
        if rf.max_value is not None:
            query = query.filter(and_(
                json_val.isnot(None),
                cast(json_val, SAFloat) <= rf.max_value,
            ))
    return query


def _apply_categorical_filter(query: Query, cf: CategoricalFilter) -> Query:
    """Apply an include/exclude categorical filter on a SQL column or JSON field."""
    col = _COLUMN_MAP.get(cf.field)
    if col is not None:
        if cf.mode == FilterMode.EXCLUDE:
            query = query.filter(~col.in_(cf.values))
        else:
            query = query.filter(col.in_(cf.values))
    elif cf.field in _JSON_FIELD_MAP:
        json_path = _JSON_FIELD_MAP[cf.field]
        json_val = func.json_extract(StockFeatureDaily.details_json, json_path)
        if cf.mode == FilterMode.EXCLUDE:
            query = query.filter(~json_val.in_(cf.values))
        else:
            query = query.filter(json_val.in_(cf.values))
    return query


def _apply_boolean_filter(query: Query, bf: BooleanFilter) -> Query:
    """Apply a boolean filter — SQL column or json_extract."""
    col = _COLUMN_MAP.get(bf.field)
    if col is not None:
        query = query.filter(col == bf.value)
    elif bf.field in _JSON_FIELD_MAP:
        json_path = _JSON_FIELD_MAP[bf.field]
        json_val = func.json_extract(StockFeatureDaily.details_json, json_path)
        query = query.filter(and_(
            json_val.isnot(None),
            json_val == (1 if bf.value else 0),
        ))
    return query


def _apply_text_search(query: Query, ts: TextSearchFilter) -> Query:
    """Apply a LIKE text search on a SQL column or JSON field."""
    col = _COLUMN_MAP.get(ts.field)
    if col is not None:
        query = query.filter(col.ilike(f"%{ts.pattern}%"))
    elif ts.field in _JSON_FIELD_MAP:
        json_path = _JSON_FIELD_MAP[ts.field]
        json_val = func.json_extract(StockFeatureDaily.details_json, json_path)
        query = query.filter(json_val.ilike(f"%{ts.pattern}%"))
    return query
