"""
时间线相关表模型

包含 Timeline（时间线）、Track（轨道）、Clip（片段）三个核心表
"""

from datetime import datetime
from sqlalchemy import String, DateTime, Text, Integer, ForeignKey, Enum, JSON, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import enum

from src.models.database import Base


class TrackType(str, enum.Enum):
    """轨道类型枚举"""
    VIDEO = "video"       # 视频轨
    SPEECH = "speech"     # 配音轨
    BGM = "bgm"           # 背景音乐轨
    CAPTION = "caption"   # 字幕轨


class Timeline(Base):
    """时间线表
    
    每个项目对应一个时间线，包含多个轨道
    """

    __tablename__ = "timelines"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    # 关联项目（一对一）
    project_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("projects.id", ondelete="CASCADE"), 
        nullable=False, 
        unique=True,
        index=True
    )
    
    # 时间线配置
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)  # 总时长（毫秒）
    aspect_ratio: Mapped[str] = mapped_column(String(20), default="9:16")  # 画面比例
    fps: Mapped[int] = mapped_column(Integer, default=30)  # 帧率
    
    # 播放状态（用于前端同步）
    playhead_ms: Mapped[int] = mapped_column(Integer, default=0)  # 播放头位置
    
    # 版本号（用于乐观锁/冲突检测）
    version: Mapped[int] = mapped_column(Integer, default=1)
    
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
    project: Mapped["Project"] = relationship("Project", backref="timeline")
    tracks: Mapped[list["Track"]] = relationship(
        "Track",
        back_populates="timeline",
        cascade="all, delete-orphan",
        order_by="Track.sort_order"
    )

    def __repr__(self) -> str:
        return f"<Timeline(id={self.id}, project_id={self.project_id}, duration={self.duration_ms}ms)>"


class Track(Base):
    """轨道表
    
    时间线包含多个轨道，每个轨道有特定类型（视频/配音/BGM/字幕）
    """

    __tablename__ = "tracks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    # 关联时间线
    timeline_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("timelines.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    
    # 轨道信息
    type: Mapped[TrackType] = mapped_column(Enum(TrackType), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=True)
    
    # 轨道配置
    is_muted: Mapped[bool] = mapped_column(Boolean, default=False)  # 是否静音
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)  # 是否锁定
    volume: Mapped[float] = mapped_column(Float, default=1.0)  # 音量（0.0-1.0），音频轨用
    
    # 排序（从上到下）
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
    timeline: Mapped["Timeline"] = relationship("Timeline", back_populates="tracks")
    clips: Mapped[list["Clip"]] = relationship(
        "Clip",
        back_populates="track",
        cascade="all, delete-orphan",
        order_by="Clip.start_ms"
    )

    def __repr__(self) -> str:
        return f"<Track(id={self.id}, type={self.type.value}, name={self.name})>"


class Clip(Base):
    """片段表
    
    轨道上的具体内容片段，关联到资产
    """

    __tablename__ = "clips"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    # 关联轨道
    track_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("tracks.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    
    # 关联资产（可为空，如纯文本字幕）
    asset_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("assets.id", ondelete="SET NULL"), 
        nullable=True,
        index=True
    )
    
    # 时间位置（毫秒）
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)  # 开始时间
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False)    # 结束时间
    
    # 资产内裁剪（用于截取资产的一部分）
    asset_start_ms: Mapped[int] = mapped_column(Integer, default=0)  # 资产内开始位置
    asset_end_ms: Mapped[int] = mapped_column(Integer, nullable=True)  # 资产内结束位置（空=到末尾）
    
    # 片段内容（用于字幕等无需资产的片段）
    content: Mapped[str] = mapped_column(Text, nullable=True)
    
    # 片段配置（JSON 格式存储灵活属性）
    # 例如：字幕样式、转场效果、音量调整等
    properties: Mapped[dict] = mapped_column(JSON, nullable=True, default=dict)
    
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
    track: Mapped["Track"] = relationship("Track", back_populates="clips")
    asset: Mapped["Asset"] = relationship("Asset", back_populates="clips")

    @property
    def duration_ms(self) -> int:
        """片段时长（毫秒）"""
        return self.end_ms - self.start_ms

    def __repr__(self) -> str:
        return f"<Clip(id={self.id}, track_id={self.track_id}, {self.start_ms}-{self.end_ms}ms)>"


