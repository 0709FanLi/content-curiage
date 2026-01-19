"""
一步生成：Segment（分段产物）表模型
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.models.database import Base


class StepSegment(Base):
    """一步生成的单段产物（口播/描述/音频/视频/合并结果）."""

    __tablename__ = "step_segments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("step_runs.id", ondelete="CASCADE"), nullable=False, index=True)

    segment_index: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    segment_id: Mapped[str] = mapped_column(String(50), nullable=False, default="segment_0")

    # 时间轴（由音频时长累计得到，用于“第10s重生成”定位）
    start_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    end_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 内容产物
    narration: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    video_desc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    voice_desc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 音频产物
    audio_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    audio_duration_sec: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # 视频产物（复用现有 video_segments 体系）
    video_segment_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("video_segments.id"), nullable=True, index=True)
    video_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    merged_video_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    run: Mapped["StepRun"] = relationship("StepRun", back_populates="segments")
    video_segment: Mapped["VideoSegment"] = relationship("VideoSegment", lazy="joined")

