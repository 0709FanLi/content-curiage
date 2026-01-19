"""
一步生成：Run（会话/任务）表模型
"""

from datetime import datetime
import enum
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.models.database import Base


class StepRunStatus(str, enum.Enum):
    """一步生成任务状态."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepRun(Base):
    """一步生成任务（对话会话）."""

    __tablename__ = "step_runs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # 关联到现有项目/脚本（复用导出与资源管理）
    project_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("projects.id"), nullable=True, index=True)
    script_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("scripts.id"), nullable=True, index=True)

    # 用户输入（对话/灵感）
    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    inspiration: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # 约束
    total_duration_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    segment_duration_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    aspect_ratio: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # one_step 扩展能力开关（后续可在前端配置）
    # - enable_storyboard: 是否生成“智能分镜首帧”
    # - enable_seedream_group: 是否使用 Seedream 4.5 文生组图（一次生成 N 张，天然一致性更强）
    # - video_mode: auto/i2v/t2v（auto: 有分镜则 i2v，否则 t2v）
    enable_storyboard: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    enable_seedream_group: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    video_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="auto")

    # Agent 决策模型优先级（按你确认：DeepSeek -> Gemini，低思考）
    decision_model_primary: Mapped[str] = mapped_column(String(50), nullable=False, default="deepseek-chat")
    decision_model_fallback: Mapped[str] = mapped_column(String(50), nullable=False, default="gemini-3-pro")
    decision_thinking_level: Mapped[str] = mapped_column(String(20), nullable=False, default="low")

    # 进度
    status: Mapped[StepRunStatus] = mapped_column(Enum(StepRunStatus), default=StepRunStatus.PENDING)
    current_step: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 0~7
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    final_video_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # 关联关系
    user: Mapped["User"] = relationship("User", lazy="joined")
    segments: Mapped[list["StepSegment"]] = relationship(
        "StepSegment",
        back_populates="run",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="StepSegment.segment_index",
    )
    events: Mapped[list["StepRunEvent"]] = relationship(
        "StepRunEvent",
        back_populates="run",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="StepRunEvent.id",
    )

