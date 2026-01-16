"""
文件相关数据模型
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class FileBase(BaseModel):
    """文件基础模型"""
    filename: str = Field(..., max_length=255)
    original_filename: str = Field(..., max_length=255)
    file_path: str = Field(..., max_length=500)
    file_size: int = Field(..., gt=0)
    mime_type: str = Field(..., max_length=100)
    file_type: str = Field(..., max_length=50)


class FileCreate(FileBase):
    """文件创建模型"""
    uploaded_by: Optional[int] = None


class FileUpdate(BaseModel):
    """文件更新模型"""
    file_url: Optional[str] = Field(None, max_length=500)


class FileResponse(FileBase):
    """文件响应模型"""
    id: int
    file_url: Optional[str] = None
    uploaded_by: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class UploadFileResponse(BaseModel):
    """上传文件响应模型"""
    file_id: int
    filename: str
    file_url: str
    file_size: int
    mime_type: str


class FileUploadRequest(BaseModel):
    """文件上传请求模型（用于文档）"""
    file: bytes
    filename: str
    content_type: Optional[str] = None
