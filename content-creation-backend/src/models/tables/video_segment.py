"""
视频片段表模型
"""

from datetime import datetime
from sqlalchemy import String, DateTime, Text, Integer, ForeignKey, Enum, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import enum

from src.models.database import Base


class VideoStatus(str, enum.Enum):
    """视频状态枚举"""
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class AudioStatus(str, enum.Enum):
    """配音音频状态枚举."""

    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class VideoSegment(Base):
    """视频片段表"""

    __tablename__ = "video_segments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    script_id: Mapped[int] = mapped_column(Integer, ForeignKey("scripts.id"), nullable=False, index=True)
    segment_index: Mapped[int] = mapped_column(Integer, nullable=False)  # 段落索引
    first_frame_url: Mapped[str] = mapped_column(String(500), nullable=True)  # 首帧图片URL
    last_frame_url: Mapped[str] = mapped_column(String(500), nullable=True)  # 尾帧图片URL
    prompt: Mapped[str] = mapped_column(Text, nullable=True)  # 视频生成提示词
    video_url: Mapped[str] = mapped_column(String(500), nullable=True)
    model: Mapped[str] = mapped_column(String(50), nullable=True)  # 使用的模型
    aspect_ratio: Mapped[str] = mapped_column(String(20), nullable=True)  # 视频比例
    status: Mapped[VideoStatus] = mapped_column(Enum(VideoStatus), default=VideoStatus.PENDING)
    duration: Mapped[float] = mapped_column(Float, nullable=False, default=4.0)  # 时长（秒）
    task_id: Mapped[str] = mapped_column(String(200), nullable=True)  # 第三方API任务ID
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    audio_url: Mapped[str] = mapped_column(String(500), nullable=True)
    audio_status: Mapped[AudioStatus] = mapped_column(
        Enum(AudioStatus),
        default=AudioStatus.PENDING,
    )
    audio_error_message: Mapped[str] = mapped_column(Text, nullable=True)
    audio_duration_sec: Mapped[float] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    # 关联关系
    script: Mapped["Script"] = relationship("Script", back_populates="video_segments")

    def __repr__(self) -> str:
        return f"<VideoSegment(id={self.id}, script_id={self.script_id}, segment_index={self.segment_index}, status={self.status.value})>"
