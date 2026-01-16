"""
资产表模型

存储项目中的所有媒体资产（图片、视频、音频、文档）
"""

from datetime import datetime
from sqlalchemy import String, DateTime, Text, Integer, ForeignKey, Enum, JSON, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import enum

from src.models.database import Base


class AssetType(str, enum.Enum):
    """资产类型枚举"""
    IMAGE = "image"           # 图片（关键帧、参考图等）
    VIDEO = "video"           # 视频片段
    AUDIO = "audio"           # 音频（配音、BGM）
    DOCUMENT = "document"     # 文档（脚本等）


class AssetSource(str, enum.Enum):
    """资产来源枚举"""
    GENERATED = "generated"   # AI 生成
    UPLOADED = "uploaded"     # 用户上传
    LIBRARY = "library"       # 素材库


class Asset(Base):
    """资产表
    
    存储项目中的所有媒体资产，供时间线编辑器使用
    """

    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    # 关联项目
    project_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("projects.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    
    # 基本信息
    name: Mapped[str] = mapped_column(String(500), nullable=True)
    type: Mapped[AssetType] = mapped_column(Enum(AssetType), nullable=False)
    source: Mapped[AssetSource] = mapped_column(Enum(AssetSource), default=AssetSource.GENERATED)
    
    # 文件信息
    url: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=True)  # 字节
    mime_type: Mapped[str] = mapped_column(String(100), nullable=True)
    
    # 媒体元数据
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=True)  # 时长（毫秒），视频/音频用
    width: Mapped[int] = mapped_column(Integer, nullable=True)        # 宽度，图片/视频用
    height: Mapped[int] = mapped_column(Integer, nullable=True)       # 高度，图片/视频用
    
    # 生成相关元数据（JSON 格式存储灵活信息）
    # 例如：prompt、seed、model、voice_id、reference_image_id 等
    extra_data: Mapped[dict] = mapped_column(JSON, nullable=True, default=dict)
    
    # 关联的原始资产（如 I2I 生成的图片关联参考图）
    parent_asset_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("assets.id", ondelete="SET NULL"), 
        nullable=True
    )
    
    # 排序字段（用于 Assets 面板排序）
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    # 关联关系
    project: Mapped["Project"] = relationship("Project", backref="assets")
    parent_asset: Mapped["Asset"] = relationship(
        "Asset", 
        remote_side=[id],
        backref="derived_assets"
    )
    clips: Mapped[list["Clip"]] = relationship(
        "Clip",
        back_populates="asset",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Asset(id={self.id}, type={self.type.value}, name={self.name})>"

