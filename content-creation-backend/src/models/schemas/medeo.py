"""
Medeo 代理相关 Schema
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MedeoRecipeListResponse(BaseModel):
    has_more: bool = False
    next_cursor: Optional[str] = None
    list: List[Dict[str, Any]] = Field(default_factory=list)


class MedeoInitiateSettings(BaseModel):
    duration_ms: int = Field(..., ge=1, le=600_000)
    aspect_ratio: str = Field("16:9")
    recipe_id: Optional[str] = None
    voice_id: Optional[str] = None
    video_style_id: Optional[str] = None
    asset_sources: Optional[List[str]] = None


class MedeoProjectInitiateRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    settings: MedeoInitiateSettings
    media_ids: Optional[List[str]] = None


class MedeoProjectInitiateResponse(BaseModel):
    project_id: int
    medeo_project_id: str
    video_draft_id: str
    chat_session_id: str


class MedeoLastTaskStatusResponse(BaseModel):
    status: str
    video_draft_op_record_id: Optional[str] = None


class MedeoRenderJobCreateRequest(BaseModel):
    video_draft_op_record_id: str = Field(..., min_length=1)


class MedeoRenderJobResponse(BaseModel):
    video_draft_op_record_id: str
    status: str
    result: Optional[Dict[str, Any]] = None


class MedeoProjectSnapshotResponse(BaseModel):
    project_id: int
    chat_session_id: Optional[str] = None
    video_draft_id: Optional[str] = None
    video_draft_op_record_id: Optional[str] = None
    last_task_status: Optional[str] = None
    render_status: Optional[str] = None
    render_url: Optional[str] = None
    render_full_url: Optional[str] = None
    render_metadata: Optional[Dict[str, Any]] = None
    last_error: Optional[str] = None


class MedeoProjectUpdateRequest(BaseModel):
    """前端将轮询到的关键字段写回，便于项目列表恢复。"""

    video_draft_op_record_id: Optional[str] = None
    last_task_status: Optional[str] = None
    render_status: Optional[str] = None
    render_url: Optional[str] = None
    render_metadata: Optional[Dict[str, Any]] = None
    last_error: Optional[str] = None

