"""Filter presets for saving and loading filter configurations"""
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from ..database import Base


class FilterPreset(Base):
    """
    Saved filter preset containing filter settings, sort column, and sort order.
    """
    __tablename__ = "filter_presets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    filters = Column(Text, nullable=False)  # JSON string of filter settings
    sort_by = Column(String(50), nullable=False, default='composite_score')
    sort_order = Column(String(10), nullable=False, default='desc')
    position = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
