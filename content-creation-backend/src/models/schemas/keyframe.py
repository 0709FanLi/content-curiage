"""
关键帧相关数据模型
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class KeyframeStatus(str, Enum):
    """关键帧状态枚举"""
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class KeyframeBase(BaseModel):
    """关键帧基础模型"""
    segment_id: str = Field(..., max_length=100)
    # prompt 可能包含较长的关键帧描述（尤其是一键生成/模型输出更长时），
    # 1000 字符上限会导致接口返回阶段直接 500（Pydantic 校验失败）。
    # 这里放宽上限，避免影响生成链路。
    prompt: Optional[str] = Field(None, max_length=10000)


class KeyframeCreate(KeyframeBase):
    """关键帧创建模型"""
    script_id: int


class KeyframeUpdate(BaseModel):
    """关键帧更新模型"""
    image_url: Optional[str] = Field(None, max_length=500, alias="imageUrl")
    prompt: Optional[str] = Field(None, max_length=10000)
    status: Optional[KeyframeStatus] = None
    error_message: Optional[str] = Field(None, max_length=500, alias="errorMessage")

    class Config:
        populate_by_name = True


class KeyframeResponse(KeyframeBase):
    """关键帧响应模型"""
    id: int
    script_id: int = Field(..., alias="scriptId")
    image_url: Optional[str] = Field(None, alias="imageUrl")
    status: KeyframeStatus
    error_message: Optional[str] = Field(None, alias="errorMessage")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")
    segment_id: str = Field(..., alias="segmentId")

    class Config:
        from_attributes = True
        populate_by_name = True


class GenerateKeyframeRequest(BaseModel):
    """生成关键帧请求模型"""
    script_id: int
    model: str = Field(..., max_length=50)
    aspect_ratio: str = Field(..., max_length=20)
    quality: Optional[str] = Field(None, max_length=20)
    # 全局移除“第0帧”后，该字段语义变更为：是否只生成第一段关键帧（segment_0）用于确认。
    # - only_first_frame=True：只生成 segment_0；后续需调用 continue 接口继续生成 segment_1..N
    # - only_first_frame=False：直接生成全部关键帧 segment_0..N
    # 仍沿用字段名是为了兼容历史前端/脚本传参。
    only_first_frame: bool = Field(
        default=True,
        description="是否只生成第一段关键帧 segment_0（用于确认）。False 则生成全部。",
    )

    # 参考图仍保留：用于第一段关键帧（segment_0）生成，帮助统一风格/定调。
    reference_image_urls: Optional[List[str]] = Field(
        default=None,
        description="参考图URL列表（用于第一段关键帧 segment_0 生成）",
    )
    
    class Config:
        populate_by_name = True


class GenerateKeyframesResponse(BaseModel):
    """批量生成关键帧响应模型"""
    keyframes: List[KeyframeResponse]
    total_count: int = Field(..., alias="totalCount")
    
    class Config:
        populate_by_name = True


class UploadKeyframeImageRequest(BaseModel):
    """上传关键帧图片请求模型"""
    file: bytes
    filename: str
