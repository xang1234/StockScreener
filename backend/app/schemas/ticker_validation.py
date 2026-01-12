"""Schemas for Ticker Validation Reports"""
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class ValidationFailure(BaseModel):
    """Single validation failure entry"""
    id: int
    symbol: str
    error_type: str
    error_message: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    data_source: Optional[str] = None
    triggered_by: str
    task_id: Optional[str] = None
    consecutive_failures: int
    detected_at: Optional[str] = None
    is_resolved: bool

    class Config:
        from_attributes = True


class ValidationFailureDetail(ValidationFailure):
    """Validation failure with resolution info"""
    resolved_at: Optional[str] = None
    resolution_notes: Optional[str] = None


class ValidationSummary(BaseModel):
    """Summary statistics for validation failures"""
    total_failures: int
    unique_symbols: int
    by_error_type: Dict[str, int]
    by_data_source: Dict[str, int]
    by_trigger: Dict[str, int]
    top_failing_symbols: List[Dict[str, Any]]
    period_start: str
    period_end: str


class ValidationReportResponse(BaseModel):
    """Paginated validation report response"""
    count: int
    offset: int
    limit: int
    failures: List[ValidationFailure]


class SymbolHistoryResponse(BaseModel):
    """Validation history for a symbol"""
    symbol: str
    history: List[ValidationFailureDetail]


class ResolveRequest(BaseModel):
    """Request to resolve a validation failure"""
    resolution_notes: str


class ResolveResponse(BaseModel):
    """Response from resolving failure(s)"""
    message: str
    count: Optional[int] = None
