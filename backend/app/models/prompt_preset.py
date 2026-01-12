"""Prompt presets for saving and loading chat prompts"""
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from ..database import Base


class PromptPreset(Base):
    """
    Saved prompt preset containing prompt templates for the chatbot.
    """
    __tablename__ = "prompt_presets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    content = Column(Text, nullable=False)  # The prompt text
    description = Column(Text, nullable=True)
    position = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
