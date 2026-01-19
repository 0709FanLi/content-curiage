"""
Medeo 项目映射表

用于将本系统 Project 与 Medeo 的 project/chat_session/video_draft 等资源绑定，
以支持“项目列表直接进入预览页并自动恢复”。
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.models.database import Base


class MedeoProject(Base):
    """Medeo 项目映射表."""

    __tablename__ = "medeo_projects"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )

    # Medeo 返回的外部 ID
    medeo_project_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    video_draft_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    chat_session_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    # last_task_status 返回的 op_record，用于 render
    video_draft_op_record_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    last_task_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # 渲染结果
    render_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    render_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    render_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    project = relationship("Project", backref="medeo_project")

