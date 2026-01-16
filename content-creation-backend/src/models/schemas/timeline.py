"""
时间线相关数据模型
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum


class TrackType(str, Enum):
    """轨道类型枚举"""
    VIDEO = "video"
    SPEECH = "speech"
    BGM = "bgm"
    CAPTION = "caption"


# ========== Clip ==========

class ClipBase(BaseModel):
    """片段基础模型"""
    asset_id: Optional[int] = Field(None, alias="assetId")
    start_ms: int = Field(..., alias="startMs", ge=0)
    end_ms: int = Field(..., alias="endMs", ge=0)
    asset_start_ms: int = Field(0, alias="assetStartMs", ge=0)
    asset_end_ms: Optional[int] = Field(None, alias="assetEndMs")
    content: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None

    class Config:
        populate_by_name = True


class ClipCreate(ClipBase):
    """片段创建模型"""
    track_id: int = Field(..., alias="trackId")


class ClipUpdate(BaseModel):
    """片段更新模型"""
    asset_id: Optional[int] = Field(None, alias="assetId")
    start_ms: Optional[int] = Field(None, alias="startMs", ge=0)
    end_ms: Optional[int] = Field(None, alias="endMs", ge=0)
    asset_start_ms: Optional[int] = Field(None, alias="assetStartMs", ge=0)
    asset_end_ms: Optional[int] = Field(None, alias="assetEndMs")
    content: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None

    class Config:
        populate_by_name = True


class ClipResponse(ClipBase):
    """片段响应模型"""
    id: int
    track_id: int = Field(..., alias="trackId")
    duration_ms: int = Field(..., alias="durationMs")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    class Config:
        from_attributes = True
        populate_by_name = True


# ========== Track ==========

class TrackBase(BaseModel):
    """轨道基础模型"""
    type: TrackType
    name: Optional[str] = Field(None, max_length=100)
    is_muted: bool = Field(False, alias="isMuted")
    is_locked: bool = Field(False, alias="isLocked")
    volume: float = Field(1.0, ge=0.0, le=2.0)
    sort_order: int = Field(0, alias="sortOrder")

    class Config:
        populate_by_name = True


class TrackCreate(TrackBase):
    """轨道创建模型"""
    timeline_id: int = Field(..., alias="timelineId")


class TrackUpdate(BaseModel):
    """轨道更新模型"""
    name: Optional[str] = Field(None, max_length=100)
    is_muted: Optional[bool] = Field(None, alias="isMuted")
    is_locked: Optional[bool] = Field(None, alias="isLocked")
    volume: Optional[float] = Field(None, ge=0.0, le=2.0)
    sort_order: Optional[int] = Field(None, alias="sortOrder")

    class Config:
        populate_by_name = True


class TrackResponse(TrackBase):
    """轨道响应模型"""
    id: int
    timeline_id: int = Field(..., alias="timelineId")
    clips: List[ClipResponse] = []
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    class Config:
        from_attributes = True
        populate_by_name = True


# ========== Timeline ==========

class TimelineBase(BaseModel):
    """时间线基础模型"""
    duration_ms: int = Field(0, alias="durationMs", ge=0)
    aspect_ratio: str = Field("9:16", alias="aspectRatio")
    fps: int = Field(30, ge=1, le=120)
    playhead_ms: int = Field(0, alias="playheadMs", ge=0)

    class Config:
        populate_by_name = True


class TimelineCreate(TimelineBase):
    """时间线创建模型"""
    project_id: int = Field(..., alias="projectId")


class TimelineUpdate(BaseModel):
    """时间线更新模型"""
    duration_ms: Optional[int] = Field(None, alias="durationMs", ge=0)
    aspect_ratio: Optional[str] = Field(None, alias="aspectRatio")
    fps: Optional[int] = Field(None, ge=1, le=120)
    playhead_ms: Optional[int] = Field(None, alias="playheadMs", ge=0)
    version: Optional[int] = None  # 用于乐观锁

    class Config:
        populate_by_name = True


class TimelineResponse(TimelineBase):
    """时间线响应模型"""
    id: int
    project_id: int = Field(..., alias="projectId")
    version: int
    tracks: List[TrackResponse] = []
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    class Config:
        from_attributes = True
        populate_by_name = True


# ========== Batch Operations ==========

class ClipBatchCreate(BaseModel):
    """批量创建片段"""
    clips: List[ClipCreate]


class ClipBatchUpdate(BaseModel):
    """批量更新片段"""
    updates: List[Dict[str, Any]]  # [{id: 1, startMs: 0, endMs: 1000}, ...]


class ClipBatchDelete(BaseModel):
    """批量删除片段"""
    clip_ids: List[int] = Field(..., alias="clipIds")

    class Config:
        populate_by_name = True


# ========== Timeline Patch (用于撤销/重做) ==========

class TimelinePatch(BaseModel):
    """时间线补丁操作"""
    operation: str  # "add_clip", "update_clip", "delete_clip", "move_clip", etc.
    target_type: str = Field(..., alias="targetType")  # "clip", "track", "timeline"
    target_id: Optional[int] = Field(None, alias="targetId")
    data: Optional[Dict[str, Any]] = None
    version: int  # 期望的版本号，用于乐观锁

    class Config:
        populate_by_name = True


class TimelinePatchResponse(BaseModel):
    """时间线补丁响应"""
    success: bool
    new_version: int = Field(..., alias="newVersion")
    affected_ids: List[int] = Field(default=[], alias="affectedIds")
    error: Optional[str] = None

    class Config:
        populate_by_name = True


