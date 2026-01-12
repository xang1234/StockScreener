"""
API endpoints for Prompt Presets feature.
Handles CRUD operations for saved chat prompts.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
import logging
import re

from ...database import get_db
from ...models.prompt_preset import PromptPreset
from ...schemas.prompt_preset import (
    PromptPresetCreate, PromptPresetUpdate, PromptPresetResponse,
    PromptPresetListResponse, ReorderPromptPresetsRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter()

TICKER_PLACEHOLDER_PATTERN = re.compile(r'\{ticker\}', re.IGNORECASE)


def has_ticker_placeholder(content: str) -> bool:
    """Check if content contains {ticker} placeholder."""
    return bool(TICKER_PLACEHOLDER_PATTERN.search(content))


def preset_to_response(preset: PromptPreset) -> PromptPresetResponse:
    """Convert a PromptPreset model to response schema."""
    return PromptPresetResponse(
        id=preset.id,
        name=preset.name,
        content=preset.content,
        description=preset.description,
        position=preset.position,
        has_ticker_placeholder=has_ticker_placeholder(preset.content),
        created_at=preset.created_at,
        updated_at=preset.updated_at,
    )


# ================= Preset CRUD =================

@router.get("/", response_model=PromptPresetListResponse)
async def list_presets(db: Session = Depends(get_db)):
    """Get all prompt presets ordered by position."""
    presets = db.query(PromptPreset).order_by(PromptPreset.position).all()

    preset_responses = [preset_to_response(preset) for preset in presets]

    return PromptPresetListResponse(
        presets=preset_responses,
        total=len(preset_responses)
    )


@router.post("/", response_model=PromptPresetResponse)
async def create_preset(data: PromptPresetCreate, db: Session = Depends(get_db)):
    """Create a new prompt preset."""
    existing = db.query(PromptPreset).filter(PromptPreset.name == data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Preset with this name already exists")

    max_pos = db.query(func.max(PromptPreset.position)).scalar() or -1

    preset = PromptPreset(
        name=data.name,
        content=data.content,
        description=data.description,
        position=max_pos + 1
    )
    db.add(preset)
    db.commit()
    db.refresh(preset)

    return preset_to_response(preset)


@router.put("/{preset_id}", response_model=PromptPresetResponse)
async def update_preset(preset_id: int, updates: PromptPresetUpdate, db: Session = Depends(get_db)):
    """Update preset properties."""
    preset = db.query(PromptPreset).filter(PromptPreset.id == preset_id).first()
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")

    # Check for duplicate name if name is being changed
    if updates.name is not None and updates.name != preset.name:
        existing = db.query(PromptPreset).filter(PromptPreset.name == updates.name).first()
        if existing:
            raise HTTPException(status_code=400, detail="Preset with this name already exists")
        preset.name = updates.name

    if updates.content is not None:
        preset.content = updates.content
    if updates.description is not None:
        preset.description = updates.description
    if updates.position is not None:
        preset.position = updates.position

    db.commit()
    db.refresh(preset)

    return preset_to_response(preset)


@router.delete("/{preset_id}")
async def delete_preset(preset_id: int, db: Session = Depends(get_db)):
    """Delete a prompt preset."""
    preset = db.query(PromptPreset).filter(PromptPreset.id == preset_id).first()
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")

    db.delete(preset)
    db.commit()
    return {"status": "deleted", "preset_id": preset_id}


@router.put("/reorder")
async def reorder_presets(
    reorder_data: ReorderPromptPresetsRequest,
    db: Session = Depends(get_db)
):
    """Reorder presets by updating their position values."""
    for idx, preset_id in enumerate(reorder_data.preset_ids):
        preset = db.query(PromptPreset).filter(PromptPreset.id == preset_id).first()
        if preset:
            preset.position = idx
    db.commit()
    return {"status": "reordered"}
