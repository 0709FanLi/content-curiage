"""
一步生成：Run 事件流（用于 SSE/审计）表模型
"""

from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.models.database import Base


class StepRunEvent(Base):
    """一步生成事件（用于前端实时展示与问题追踪）."""

    __tablename__ = "step_run_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("step_runs.id", ondelete="CASCADE"), nullable=False, index=True)

    level: Mapped[str] = mapped_column(String(20), nullable=False, default="info")
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, default="log")
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped["StepRun"] = relationship("StepRun", back_populates="events")

