"""
API endpoints for Chat Folder management.

Provides:
- Folder CRUD operations
- Folder organization (collapse/expand, reorder)
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from ...database import get_db
from ...models.chatbot_folder import ChatFolder
from ...models.chatbot import Conversation
from ...schemas.chatbot_folder import (
    FolderCreate,
    FolderUpdate,
    FolderResponse,
    FolderListResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def get_folder_with_count(db: Session, folder: ChatFolder) -> FolderResponse:
    """Convert a folder to response with conversation count."""
    count = db.query(Conversation).filter(
        Conversation.folder_id == folder.id,
        Conversation.is_active == True
    ).count()

    return FolderResponse(
        id=folder.id,
        name=folder.name,
        position=folder.position,
        is_collapsed=folder.is_collapsed,
        conversation_count=count,
        created_at=folder.created_at,
        updated_at=folder.updated_at,
    )


@router.get("", response_model=FolderListResponse)
async def list_folders(
    db: Session = Depends(get_db)
):
    """
    List all folders sorted by position.
    """
    folders = (
        db.query(ChatFolder)
        .order_by(ChatFolder.position, ChatFolder.id)
        .all()
    )

    folder_responses = [get_folder_with_count(db, f) for f in folders]

    return FolderListResponse(
        folders=folder_responses,
        total=len(folders)
    )


@router.post("", response_model=FolderResponse)
async def create_folder(
    request: FolderCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new folder.
    """
    # Get max position if not specified
    position = request.position
    if position is None:
        max_position = db.query(func.max(ChatFolder.position)).scalar()
        position = (max_position or 0) + 1

    folder = ChatFolder(
        name=request.name,
        position=position,
        is_collapsed=False,
    )

    db.add(folder)
    db.commit()
    db.refresh(folder)

    logger.info(f"Created folder: {folder.id} - {folder.name}")
    return get_folder_with_count(db, folder)


@router.get("/{folder_id}", response_model=FolderResponse)
async def get_folder(
    folder_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a single folder by ID.
    """
    folder = db.query(ChatFolder).filter(ChatFolder.id == folder_id).first()

    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    return get_folder_with_count(db, folder)


@router.patch("/{folder_id}", response_model=FolderResponse)
async def update_folder(
    folder_id: int,
    updates: FolderUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a folder's name, position, or collapsed state.
    """
    folder = db.query(ChatFolder).filter(ChatFolder.id == folder_id).first()

    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    if updates.name is not None:
        folder.name = updates.name

    if updates.position is not None:
        folder.position = updates.position

    if updates.is_collapsed is not None:
        folder.is_collapsed = updates.is_collapsed

    db.commit()
    db.refresh(folder)

    logger.info(f"Updated folder: {folder_id}")
    return get_folder_with_count(db, folder)


@router.delete("/{folder_id}")
async def delete_folder(
    folder_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a folder. Conversations in this folder become uncategorized.
    """
    folder = db.query(ChatFolder).filter(ChatFolder.id == folder_id).first()

    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    folder_name = folder.name

    # Conversations will automatically have folder_id set to NULL due to ON DELETE SET NULL
    db.delete(folder)
    db.commit()

    logger.info(f"Deleted folder: {folder_id} - {folder_name}")
    return {"status": "deleted", "folder_id": folder_id}
