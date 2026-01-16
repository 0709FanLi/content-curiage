"""
热点情报相关数据模型
"""

from typing import Optional, List
from pydantic import BaseModel, Field


class HotspotItem(BaseModel):
    """热点项模型"""
    title: str = Field(..., description="热点标题")
    track: str = Field(..., description="所属赛道")
    source: str = Field(..., description="热点来源")
    angle: str = Field(..., description="切入角度")


class HotspotListResponse(BaseModel):
    """热点列表响应模型"""
    daily_summary: str = Field(..., description="今日总结")
    hotspots: List[HotspotItem] = Field(default_factory=list, description="热点列表")


class HotspotDetailSection(BaseModel):
    """热点详情章节模型"""
    title: str = Field(..., description="章节标题")
    content: str = Field(..., description="章节内容")
    items: Optional[List[str]] = Field(default=None, description="内容要点列表")


class HotspotDetailResponse(BaseModel):
    """热点详情响应模型"""
    title: str = Field(..., description="热点标题")
    trust: HotspotDetailSection = Field(..., description="科学支撑 (TRUST)")
    conversion: HotspotDetailSection = Field(..., description="转化策略 (CONVERSION)")
    structure: HotspotDetailSection = Field(..., description="建议结构 (STRUCTURE)")
    raw_content: Optional[str] = Field(None, description="原始完整内容")


class HotspotDetailRequest(BaseModel):
    """热点详情请求模型"""
    title: str = Field(..., description="热点标题", min_length=1, max_length=500)

