"""
项目表模型
"""

from datetime import datetime
from sqlalchemy import String, DateTime, Text, Integer, ForeignKey, Enum, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import enum

from src.models.database import Base


class ProjectStatus(str, enum.Enum):
    """项目状态枚举"""
    DRAFT = "draft"
    SCRIPT_GENERATED = "script_generated"
    KEYFRAMES_GENERATING = "keyframes_generating"
    KEYFRAMES_COMPLETED = "keyframes_completed"
    VIDEO_GENERATING = "video_generating"
    COMPLETED = "completed"


class Project(Base):
    """项目表"""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(Enum(ProjectStatus), default=ProjectStatus.DRAFT)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # 对话内容
    conversation_content: Mapped[str] = mapped_column(Text, nullable=True)
    # 图像模型配置
    image_model: Mapped[str] = mapped_column(String(100), nullable=True)
    aspect_ratio: Mapped[str] = mapped_column(String(50), nullable=True)
    quality: Mapped[str] = mapped_column(String(50), nullable=True)
    # 参考图（用于 keyframes segment_0 定调）。持久化以支持刷新/重进项目后仍可继续生成。
    reference_image_urls: Mapped[list] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )
    # 第一次生成脚本的时间(作为项目记录时间,不再改变)
    first_script_generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    # 生成模式：one_click(一键生成) 或 step_by_step(分步生成)
    generation_mode: Mapped[str] = mapped_column(String(20), default='step_by_step', nullable=True)

    # 关联关系
    user: Mapped["User"] = relationship("User", back_populates="projects")
    scripts: Mapped[list["Script"]] = relationship(
        "Script",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, name={self.name}, status={self.status.value})>"
