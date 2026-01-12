"""Task execution history model for tracking Celery task runs"""
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Text, Index
from sqlalchemy.sql import func
from ..database import Base


class TaskExecutionHistory(Base):
    """Track execution history of scheduled Celery tasks"""

    __tablename__ = "task_execution_history"

    id = Column(Integer, primary_key=True, index=True)
    task_name = Column(String(100), nullable=False, index=True)  # e.g., "daily-cache-warmup"
    task_function = Column(String(200))  # e.g., "app.tasks.cache_tasks.daily_cache_warmup"
    task_id = Column(String(100), nullable=True)  # Celery task ID

    # Execution details
    status = Column(String(20), default="queued")  # queued, running, completed, failed
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    duration_seconds = Column(Float)

    # Result
    result_summary = Column(JSON)  # Store task return value summary
    error_message = Column(Text)

    # Trigger source
    triggered_by = Column(String(20), default="manual")  # schedule, manual

    __table_args__ = (
        Index("idx_task_name_started", "task_name", "started_at"),
    )
