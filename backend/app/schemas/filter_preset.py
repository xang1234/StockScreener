"""Schemas for Filter Presets"""
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


# ================= Preset Schemas =================

class FilterPresetBase(BaseModel):
    """Base schema for a filter preset"""
    name: str
    description: Optional[str] = None
    filters: Dict[str, Any]
    sort_by: str = 'composite_score'
    sort_order: str = 'desc'


class FilterPresetCreate(FilterPresetBase):
    """Schema for creating a new filter preset"""
    pass


class FilterPresetUpdate(BaseModel):
    """Schema for updating a filter preset"""
    name: Optional[str] = None
    description: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    sort_by: Optional[str] = None
    sort_order: Optional[str] = None
    position: Optional[int] = None


class FilterPresetResponse(BaseModel):
    """Response schema for a filter preset"""
    id: int
    name: str
    description: Optional[str] = None
    filters: Dict[str, Any]
    sort_by: str
    sort_order: str
    position: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FilterPresetListResponse(BaseModel):
    """List of filter presets"""
    presets: List[FilterPresetResponse]
    total: int


# ================= Reorder Schema =================

class ReorderPresetsRequest(BaseModel):
    """Request body for reordering presets"""
    preset_ids: List[int]
