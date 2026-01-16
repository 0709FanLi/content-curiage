"""
脚本相关数据模型
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class ScriptSegment(BaseModel):
    """脚本段落模型"""
    id: str
    time_start: float
    time_end: float
    content: str
    scene: Optional[str] = None
    presenter: Optional[str] = None
    subtitle: Optional[str] = None
    narration: Optional[str] = None  # 口播文案
    keyframe_desc: Optional[str] = None  # 关键帧描述
    video_desc: Optional[str] = None  # 视频描述
    voice_desc: Optional[str] = None  # 音色描述


class ScriptBase(BaseModel):
    """脚本基础模型"""
    content: str = Field(..., max_length=20000)
    style: Optional[str] = Field(None, max_length=50)
    total_duration: Optional[int] = Field(None, ge=60, le=1200)  # 60秒到20分钟
    segment_duration: Optional[int] = Field(None, ge=4, le=300)  # 4秒到5分钟


class ScriptCreate(ScriptBase):
    """脚本创建模型"""
    project_id: int


class ScriptUpdate(BaseModel):
    """脚本更新模型"""
    content: Optional[str] = Field(None, max_length=20000)
    style: Optional[str] = Field(None, max_length=50)
    total_duration: Optional[int] = Field(None, ge=60, le=3600)
    segment_duration: Optional[int] = Field(None, ge=4, le=300)
    segments: Optional[List[ScriptSegment]] = None
    optimized_content: Optional[str] = Field(None, max_length=20000)
    
    model_config = ConfigDict(extra='ignore')


class ScriptResponse(ScriptBase):
    """脚本响应模型"""
    id: int
    project_id: int
    segments: Optional[List[ScriptSegment]] = None
    optimized_content: Optional[str] = None
    exported_video_url: Optional[str] = Field(None, alias="exportedVideoUrl")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True


class GenerateScriptRequest(BaseModel):
    """生成脚本请求模型"""
    inspiration: str = Field(..., min_length=1, max_length=3000)
    style: str = Field(..., min_length=1, max_length=50)
    total_duration: int = Field(..., ge=1, le=3600, alias="totalDuration")  # 最小1秒
    segment_duration: int = Field(4, ge=4, le=300, alias="segmentDuration")
    project_id: Optional[int] = Field(None, alias="projectId")
    generation_mode: Optional[str] = Field('step_by_step', alias="generationMode")  # one_click 或 step_by_step
    reference_image_urls: Optional[List[str]] = Field(None, alias="referenceImageUrls")  # 参考图URL列表
    enable_search: bool = Field(False, alias="enableSearch")  # 是否启用联网搜索（如百炼联网搜索）
    
    class Config:
        populate_by_name = True  # 允许同时使用别名和原始字段名


class OptimizeScriptRequest(BaseModel):
    """优化脚本请求模型"""
    optimization: str = Field(..., min_length=1, max_length=500)
    enable_search: bool = Field(False, alias="enableSearch")  # 是否启用联网搜索

    class Config:
        populate_by_name = True
