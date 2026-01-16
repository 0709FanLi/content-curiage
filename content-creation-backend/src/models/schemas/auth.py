"""
认证相关数据模型
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    """用户基础模型"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr


class UserCreate(UserBase):
    """用户创建模型"""
    password: str = Field(..., min_length=6, max_length=100)


class UserUpdate(BaseModel):
    """用户更新模型"""
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    avatar: Optional[str] = None


class UserResponse(UserBase):
    """用户响应模型"""
    id: int
    avatar: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    """令牌模型"""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """令牌数据模型"""
    username: Optional[str] = None


class LoginRequest(BaseModel):
    """登录请求模型"""
    username: str
    password: str


class LoginResponse(BaseModel):
    """登录响应模型"""
    user: UserResponse
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    """刷新令牌请求模型"""
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    """修改密码请求模型"""
    old_password: str
    new_password: str = Field(..., min_length=8, max_length=100)
