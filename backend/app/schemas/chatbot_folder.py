"""Pydantic schemas for Chat Folder API"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class FolderCreate(BaseModel):
    """Request to create a new folder."""
    name: str = Field(..., min_length=1, max_length=100, description="Folder name")
    position: Optional[int] = Field(None, description="Position for ordering folders")


class FolderUpdate(BaseModel):
    """Request to update a folder."""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="New folder name")
    position: Optional[int] = Field(None, description="New position for ordering")
    is_collapsed: Optional[bool] = Field(None, description="Whether folder is collapsed in UI")


class FolderResponse(BaseModel):
    """Response for a single folder."""
    id: int
    name: str
    position: int
    is_collapsed: bool
    conversation_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FolderListResponse(BaseModel):
    """Response for listing folders."""
    folders: List[FolderResponse]
    total: int
