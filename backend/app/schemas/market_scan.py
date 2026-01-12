"""Market Scan schemas"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class WatchlistSymbolBase(BaseModel):
    """Base schema for watchlist symbol"""
    symbol: str
    display_name: Optional[str] = None
    notes: Optional[str] = None


class WatchlistSymbolCreate(WatchlistSymbolBase):
    """Schema for creating a new watchlist symbol"""
    position: Optional[int] = None


class WatchlistSymbolUpdate(BaseModel):
    """Schema for updating a watchlist symbol"""
    display_name: Optional[str] = None
    notes: Optional[str] = None
    position: Optional[int] = None


class WatchlistSymbolResponse(WatchlistSymbolBase):
    """Response schema for a watchlist symbol"""
    id: int
    list_name: str
    position: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WatchlistResponse(BaseModel):
    """Response schema for a complete watchlist"""
    list_name: str
    symbols: List[WatchlistSymbolResponse]
    total: int


class ReorderRequest(BaseModel):
    """Request body for reordering symbols"""
    symbol_ids: List[int]
