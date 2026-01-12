"""Schemas for Prompt Presets"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# ================= Preset Schemas =================

class PromptPresetBase(BaseModel):
    """Base schema for a prompt preset"""
    name: str
    content: str
    description: Optional[str] = None


class PromptPresetCreate(PromptPresetBase):
    """Schema for creating a new prompt preset"""
    pass


class PromptPresetUpdate(BaseModel):
    """Schema for updating a prompt preset"""
    name: Optional[str] = None
    content: Optional[str] = None
    description: Optional[str] = None
    position: Optional[int] = None


class PromptPresetResponse(BaseModel):
    """Response schema for a prompt preset"""
    id: int
    name: str
    content: str
    description: Optional[str] = None
    position: int
    has_ticker_placeholder: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PromptPresetListResponse(BaseModel):
    """List of prompt presets"""
    presets: List[PromptPresetResponse]
    total: int


# ================= Reorder Schema =================

class ReorderPromptPresetsRequest(BaseModel):
    """Request body for reordering presets"""
    preset_ids: List[int]
