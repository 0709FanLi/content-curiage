"""
系统配置相关的Pydantic模型
"""

from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class SystemConfigBase(BaseModel):
    """系统配置基础模型"""
    config_key: str = Field(..., max_length=100, description="配置键")
    config_value: str = Field(..., description="配置值")
    description: Optional[str] = Field(None, max_length=500, description="配置描述")


class SystemConfigCreate(SystemConfigBase):
    """创建系统配置请求模型"""
    pass


class SystemConfigUpdate(BaseModel):
    """更新系统配置请求模型"""
    config_value: str = Field(..., description="配置值")
    description: Optional[str] = Field(None, max_length=500, description="配置描述")


class SystemConfigResponse(SystemConfigBase):
    """系统配置响应模型"""
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

