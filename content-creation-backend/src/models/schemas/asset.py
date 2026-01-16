"""
资产相关数据模型
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum


class AssetType(str, Enum):
    """资产类型枚举"""
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"


class AssetSource(str, Enum):
    """资产来源枚举"""
    GENERATED = "generated"
    UPLOADED = "uploaded"
    LIBRARY = "library"


class AssetBase(BaseModel):
    """资产基础模型"""
    name: Optional[str] = Field(None, max_length=500)
    type: AssetType
    source: AssetSource = AssetSource.GENERATED


class AssetCreate(AssetBase):
    """资产创建模型"""
    project_id: int = Field(..., alias="projectId")
    url: str
    file_size: Optional[int] = Field(None, alias="fileSize")
    mime_type: Optional[str] = Field(None, alias="mimeType")
    duration_ms: Optional[int] = Field(None, alias="durationMs")
    width: Optional[int] = None
    height: Optional[int] = None
    extra_data: Optional[Dict[str, Any]] = Field(None, alias="extraData")
    parent_asset_id: Optional[int] = Field(None, alias="parentAssetId")

    class Config:
        populate_by_name = True


class AssetUpdate(BaseModel):
    """资产更新模型"""
    name: Optional[str] = Field(None, max_length=500)
    extra_data: Optional[Dict[str, Any]] = Field(None, alias="extraData")
    sort_order: Optional[int] = Field(None, alias="sortOrder")

    class Config:
        populate_by_name = True


class AssetResponse(AssetBase):
    """资产响应模型"""
    id: int
    project_id: int = Field(..., alias="projectId")
    url: str
    file_size: Optional[int] = Field(None, alias="fileSize")
    mime_type: Optional[str] = Field(None, alias="mimeType")
    duration_ms: Optional[int] = Field(None, alias="durationMs")
    width: Optional[int] = None
    height: Optional[int] = None
    extra_data: Optional[Dict[str, Any]] = Field(None, alias="extraData")
    parent_asset_id: Optional[int] = Field(None, alias="parentAssetId")
    sort_order: int = Field(0, alias="sortOrder")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    class Config:
        from_attributes = True
        populate_by_name = True


class AssetListResponse(BaseModel):
    """资产列表响应"""
    items: List[AssetResponse]
    total: int

