"""
ChatFolder model for organizing chatbot conversations.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from ..database import Base


class ChatFolder(Base):
    """A folder for organizing chatbot conversations."""

    __tablename__ = "chatbot_folders"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    position = Column(Integer, nullable=False, default=0)
    is_collapsed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationship to conversations
    conversations = relationship("Conversation", back_populates="folder")
