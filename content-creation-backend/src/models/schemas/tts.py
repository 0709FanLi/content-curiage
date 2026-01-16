"""
TTS 语音合成相关数据模型

使用阿里云百炼 Sambert 模型
"""

from typing import Optional, List
from pydantic import BaseModel, Field


class VoiceInfo(BaseModel):
    """音色信息"""
    id: str
    name: str
    language: str
    gender: str
    description: str


class VoiceListResponse(BaseModel):
    """音色列表响应"""
    voices: List[VoiceInfo]
    total: int


class TTSSynthesizeRequest(BaseModel):
    """TTS 合成请求
    
    使用 Sambert 模型参数
    """
    text: str = Field(..., min_length=1, max_length=2000, description="要合成的文本")
    voice: str = Field("sambert-zhichu-v1", description="音色 ID，如 sambert-zhichu-v1")
    format: str = Field("mp3", description="输出格式：pcm, wav, mp3")
    sample_rate: int = Field(16000, alias="sampleRate", description="采样率：16000 或 48000")
    volume: int = Field(50, ge=0, le=100, description="音量 (0-100)")
    speech_rate: int = Field(0, alias="speechRate", ge=-500, le=500, description="语速 (-500到500，0为正常)")
    pitch_rate: int = Field(0, alias="pitchRate", ge=-500, le=500, description="音调 (-500到500，0为正常)")

    class Config:
        populate_by_name = True


class TTSSynthesizeResponse(BaseModel):
    """TTS 合成响应"""
    url: str = Field(..., description="音频 URL")
    duration_ms: int = Field(..., alias="durationMs", description="时长（毫秒）")
    text: Optional[str] = Field(None, description="原文本")
    voice: Optional[str] = Field(None, description="使用的音色")
    format: Optional[str] = Field(None, description="音频格式")

    class Config:
        populate_by_name = True


class TTSBatchItem(BaseModel):
    """批量合成单项"""
    id: str = Field(..., description="项目 ID")
    text: str = Field(..., min_length=1, max_length=2000, description="要合成的文本")


class TTSBatchRequest(BaseModel):
    """TTS 批量合成请求"""
    items: List[TTSBatchItem]
    voice: str = Field("sambert-zhichu-v1", description="音色 ID")
    format: str = Field("mp3", description="输出格式：pcm, wav, mp3")
    sample_rate: int = Field(16000, alias="sampleRate", description="采样率")
    volume: int = Field(50, ge=0, le=100, description="音量")
    speech_rate: int = Field(0, alias="speechRate", ge=-500, le=500, description="语速")
    pitch_rate: int = Field(0, alias="pitchRate", ge=-500, le=500, description="音调")

    class Config:
        populate_by_name = True


class TTSBatchItemResult(BaseModel):
    """批量合成单项结果"""
    id: str
    success: bool
    url: Optional[str] = None
    duration_ms: Optional[int] = Field(None, alias="durationMs")
    error: Optional[str] = None

    class Config:
        populate_by_name = True


class TTSBatchResponse(BaseModel):
    """TTS 批量合成响应"""
    results: List[TTSBatchItemResult]
    success_count: int = Field(..., alias="successCount")
    failure_count: int = Field(..., alias="failureCount")

    class Config:
        populate_by_name = True
