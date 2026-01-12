"""App settings model for storing application configuration."""
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from ..database import Base


class AppSetting(Base):
    """
    Key-value store for application settings.
    Used for persisting configuration like LLM model selection.
    """
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), nullable=False, unique=True, index=True)
    value = Column(Text, nullable=False)
    category = Column(String(50), nullable=True, index=True)  # e.g., "llm", "theme", etc.
    description = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<AppSetting(key='{self.key}', value='{self.value[:50]}...')>"
