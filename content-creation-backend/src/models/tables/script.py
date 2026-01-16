"""
脚本表模型
"""

from datetime import datetime
from sqlalchemy import String, DateTime, Text, Integer, ForeignKey, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.models.database import Base


class Script(Base):
    """脚本表"""

    __tablename__ = "scripts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    style: Mapped[str] = mapped_column(String(50), nullable=True)
    total_duration: Mapped[int] = mapped_column(Integer, nullable=True)  # 总时长（秒）
    segment_duration: Mapped[int] = mapped_column(Integer, nullable=True)  # 单段时长（秒）
    segments: Mapped[dict] = mapped_column(JSON, nullable=True)  # 脚本分段数据
    optimized_content: Mapped[str] = mapped_column(Text, nullable=True)  # 优化后的内容
    exported_video_url: Mapped[str] = mapped_column(String(500), nullable=True)  # 导出的视频URL
    cancelled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    # 关键帧/视频规则片段审查（Gemini）标记：用于日间定时任务挑选“未处理脚本”
    rules_audit_status: Mapped[str] = mapped_column(String(20), nullable=True, index=True)
    rules_audit_changed: Mapped[bool] = mapped_column(Boolean, nullable=True)
    rules_audit_model: Mapped[str] = mapped_column(String(50), nullable=True)
    rules_audit_checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    rules_audit_error: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    # 关联关系
    project: Mapped["Project"] = relationship("Project", back_populates="scripts")
    keyframes: Mapped[list["Keyframe"]] = relationship(
        "Keyframe",
        back_populates="script",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    video_segments: Mapped[list["VideoSegment"]] = relationship(
        "VideoSegment",
        back_populates="script",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<Script(id={self.id}, project_id={self.project_id})>"
