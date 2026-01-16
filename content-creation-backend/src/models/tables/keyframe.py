"""
关键帧表模型
"""

from datetime import datetime
from sqlalchemy import String, DateTime, Text, Integer, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import enum

from src.models.database import Base


class KeyframeStatus(str, enum.Enum):
    """关键帧状态枚举"""
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class Keyframe(Base):
    """关键帧表"""

    __tablename__ = "keyframes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    script_id: Mapped[int] = mapped_column(Integer, ForeignKey("scripts.id"), nullable=False, index=True)
    segment_id: Mapped[str] = mapped_column(String(100), nullable=False)  # 脚本段落ID
    image_url: Mapped[str] = mapped_column(String(500), nullable=True)
    prompt: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[KeyframeStatus] = mapped_column(Enum(KeyframeStatus), default=KeyframeStatus.PENDING)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    # 关联关系
    script: Mapped["Script"] = relationship("Script", back_populates="keyframes")

    def __repr__(self) -> str:
        return f"<Keyframe(id={self.id}, segment_id={self.segment_id}, status={self.status.value})>"
