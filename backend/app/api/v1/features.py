"""Feature store API endpoints.

Provides monitoring and comparison capabilities for the feature store:
- GET /features/runs — list feature runs with row counts
- GET /features/compare — compare two feature runs side-by-side
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ...domain.common.errors import (
    EntityNotFoundError,
    ValidationError as DomainValidationError,
)
from ...infra.db.uow import SqlUnitOfWork
from ...use_cases.feature_store.compare_runs import (
    CompareFeatureRunsUseCase,
    CompareRunsQuery,
)
from ...use_cases.feature_store.list_runs import (
    ListFeatureRunsUseCase,
    ListRunsQuery,
)
from ...wiring.bootstrap import (
    get_compare_feature_runs_use_case,
    get_list_feature_runs_use_case,
    get_uow,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class RunStatsResponse(BaseModel):
    total_symbols: int
    processed_symbols: int
    failed_symbols: int
    duration_seconds: float


class FeatureRunResponse(BaseModel):
    id: int
    as_of_date: date
    run_type: str
    status: str
    created_at: str
    completed_at: Optional[str] = None
    published_at: Optional[str] = None
    row_count: int
    is_latest_published: bool
    stats: Optional[RunStatsResponse] = None
    warnings: list[str]


class ListRunsResponse(BaseModel):
    runs: list[FeatureRunResponse]


class SymbolEntryResponse(BaseModel):
    symbol: str
    score: Optional[float] = None
    rating: Optional[str] = None


class SymbolDeltaResponse(BaseModel):
    symbol: str
    score_a: Optional[float] = None
    score_b: Optional[float] = None
    score_delta: float
    rating_a: Optional[str] = None
    rating_b: Optional[str] = None


class CompareSummaryResponse(BaseModel):
    total_common: int
    upgraded_count: int
    downgraded_count: int
    avg_score_change: float


class CompareRunsResponse(BaseModel):
    run_a_id: int
    run_b_id: int
    run_a_date: date
    run_b_date: date
    summary: CompareSummaryResponse
    added: list[SymbolEntryResponse]
    removed: list[SymbolEntryResponse]
    movers: list[SymbolDeltaResponse]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/runs", response_model=ListRunsResponse)
async def list_runs(
    status: Optional[str] = Query(None, description="Filter by run status"),
    date_from: Optional[date] = Query(None, description="Start date (inclusive)"),
    date_to: Optional[date] = Query(None, description="End date (inclusive)"),
    limit: int = Query(50, ge=1, le=200, description="Max runs to return"),
    uow: SqlUnitOfWork = Depends(get_uow),
    use_case: ListFeatureRunsUseCase = Depends(get_list_feature_runs_use_case),
):
    """List feature runs with row counts and publish status."""
    try:
        query = ListRunsQuery(
            status=status,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )
        result = use_case.execute(uow, query)
    except DomainValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    runs = []
    for r in result.runs:
        stats = None
        if r.stats is not None:
            stats = RunStatsResponse(
                total_symbols=r.stats.total_symbols,
                processed_symbols=r.stats.processed_symbols,
                failed_symbols=r.stats.failed_symbols,
                duration_seconds=r.stats.duration_seconds,
            )
        runs.append(FeatureRunResponse(
            id=r.id,
            as_of_date=r.as_of_date,
            run_type=r.run_type,
            status=r.status,
            created_at=r.created_at.isoformat(),
            completed_at=r.completed_at.isoformat() if r.completed_at else None,
            published_at=r.published_at.isoformat() if r.published_at else None,
            row_count=r.row_count,
            is_latest_published=r.is_latest_published,
            stats=stats,
            warnings=list(r.warnings),
        ))

    return ListRunsResponse(runs=runs)


@router.get("/compare", response_model=CompareRunsResponse)
async def compare_runs(
    run_a: int = Query(..., description="First run ID (baseline)"),
    run_b: int = Query(..., description="Second run ID (comparison)"),
    limit: int = Query(50, ge=1, le=500, description="Max movers to return"),
    uow: SqlUnitOfWork = Depends(get_uow),
    use_case: CompareFeatureRunsUseCase = Depends(get_compare_feature_runs_use_case),
):
    """Compare two feature runs: added/removed symbols and score movers."""
    try:
        query = CompareRunsQuery(run_a=run_a, run_b=run_b, limit=limit)
        result = use_case.execute(uow, query)
    except DomainValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return CompareRunsResponse(
        run_a_id=result.run_a_id,
        run_b_id=result.run_b_id,
        run_a_date=result.run_a_date,
        run_b_date=result.run_b_date,
        summary=CompareSummaryResponse(
            total_common=result.summary.total_common,
            upgraded_count=result.summary.upgraded_count,
            downgraded_count=result.summary.downgraded_count,
            avg_score_change=result.summary.avg_score_change,
        ),
        added=[
            SymbolEntryResponse(symbol=e.symbol, score=e.score, rating=e.rating)
            for e in result.added
        ],
        removed=[
            SymbolEntryResponse(symbol=e.symbol, score=e.score, rating=e.rating)
            for e in result.removed
        ],
        movers=[
            SymbolDeltaResponse(
                symbol=d.symbol,
                score_a=d.score_a,
                score_b=d.score_b,
                score_delta=d.score_delta,
                rating_a=d.rating_a,
                rating_b=d.rating_b,
            )
            for d in result.movers
        ],
    )
