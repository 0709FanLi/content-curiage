"""
一步生成相关 Schema
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class StepRunCreateRequest(BaseModel):
    title: Optional[str] = Field(None, description="可选标题")
    inspiration: str = Field(..., min_length=1, description="用户输入/创意描述")
    total_duration_sec: int = Field(20, ge=4, le=3600, description="总时长（秒）")
    segment_duration_sec: int = Field(4, ge=1, le=60, description="单段目标时长（秒）")
    aspect_ratio: Optional[str] = Field("16:9", description="画幅比例（例如 16:9 / 9:16）")

    # Agent 决策模型优先级（按需求默认 DeepSeek -> Gemini，低思考）
    decision_model_primary: str = Field("deepseek-chat", description="主模型（低思考）")
    decision_model_fallback: str = Field("gemini-3-pro", description="回退模型（低思考）")
    decision_thinking_level: str = Field("low", description="思考等级（目前仅用于 Gemini 3）")

    # 脚本风格（复用现有脚本生成能力）
    style: str = Field("默认", description="脚本风格")

    # one_step 扩展能力开关（可选，不传则按默认）
    enable_storyboard: bool = Field(True, description="是否生成智能分镜首帧（用于图生视频）")
    enable_seedream_group: bool = Field(True, description="是否使用 Seedream 4.5 文生组图生成分镜（更强一致性）")
    video_mode: str = Field("auto", description="视频生成模式：auto/i2v/t2v（auto: 有分镜则 i2v，否则 t2v）")


class StepRunCreateResponse(BaseModel):
    run_id: int
    project_id: int
    script_id: int


class StepSegmentResponse(BaseModel):
    id: int
    segment_index: int
    segment_id: str
    start_ms: Optional[int] = None
    end_ms: Optional[int] = None
    narration: Optional[str] = None
    video_desc: Optional[str] = None
    audio_url: Optional[str] = None
    audio_duration_sec: Optional[float] = None
    video_url: Optional[str] = None
    merged_video_url: Optional[str] = None
    error_message: Optional[str] = None


class StepRunStatusResponse(BaseModel):
    id: int
    title: Optional[str] = None
    inspiration: Optional[str] = None
    status: str
    current_step: int
    error_message: Optional[str] = None
    final_video_url: Optional[str] = None
    project_id: Optional[int] = None
    script_id: Optional[int] = None
    total_duration_sec: Optional[int] = None
    segment_duration_sec: Optional[int] = None
    aspect_ratio: Optional[str] = None
    enable_storyboard: Optional[bool] = None
    enable_seedream_group: Optional[bool] = None
    video_mode: Optional[str] = None
    segments: List[StepSegmentResponse] = Field(default_factory=list)


class SnapshotScriptResponse(BaseModel):
    id: int
    content: str = ""
    segments: List[Dict[str, Any]] = Field(default_factory=list)


class SnapshotKeyframeResponse(BaseModel):
    id: int
    segment_id: str
    image_url: Optional[str] = None
    status: str
    error_message: Optional[str] = None


class SnapshotVideoSegmentResponse(BaseModel):
    id: int
    segment_index: int
    first_frame_url: Optional[str] = None
    video_url: Optional[str] = None
    status: str
    duration: Optional[float] = None
    error_message: Optional[str] = None


class StepRunSnapshotResponse(BaseModel):
    """一步生成快照：按步骤返回目前已产出的内容，供前端单接口轮询。"""

    run: StepRunStatusResponse
    script: Optional[SnapshotScriptResponse] = None
    step_segments: List[StepSegmentResponse] = Field(default_factory=list)
    keyframes: List[SnapshotKeyframeResponse] = Field(default_factory=list)
    videos: List[SnapshotVideoSegmentResponse] = Field(default_factory=list)


class StepRunEventResponse(BaseModel):
    id: int
    level: str
    event_type: str
    message: str
    data: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None


class StepRunCommandRequest(BaseModel):
    message: str = Field(..., min_length=1, description="用户对话指令，例如：第10s视频重新生成")

