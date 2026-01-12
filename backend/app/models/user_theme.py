"""User-defined themes for Market Scan Themes tab"""
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, UniqueConstraint, Index
from sqlalchemy.sql import func
from ..database import Base


class UserTheme(Base):
    """
    User-defined investment theme (top-level container).
    Example: "AI", "Clean Energy", "Reshoring"
    """
    __tablename__ = "user_themes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    color = Column(String(20), nullable=True)
    position = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class UserThemeSubgroup(Base):
    """
    Subgroup within a theme.
    Example: AI theme -> "Memory", "Semiconductors", "Neoclouds"
    """
    __tablename__ = "user_theme_subgroups"

    id = Column(Integer, primary_key=True, index=True)
    theme_id = Column(Integer, ForeignKey("user_themes.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    position = Column(Integer, nullable=False, default=0)
    is_collapsed = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('theme_id', 'name', name='uix_theme_subgroup_name'),
        Index("idx_theme_subgroup", "theme_id", "position"),
    )


class UserThemeStock(Base):
    """
    Stock assignment to a subgroup within a theme.
    """
    __tablename__ = "user_theme_stocks"

    id = Column(Integer, primary_key=True, index=True)
    subgroup_id = Column(Integer, ForeignKey("user_theme_subgroups.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol = Column(String(20), nullable=False)
    display_name = Column(String(100), nullable=True)
    position = Column(Integer, nullable=False, default=0)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('subgroup_id', 'symbol', name='uix_subgroup_symbol'),
        Index("idx_subgroup_stock", "subgroup_id", "position"),
    )
