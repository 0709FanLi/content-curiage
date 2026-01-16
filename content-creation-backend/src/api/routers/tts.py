"""
TTS 语音合成路由
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
import structlog

from src.models.schemas.tts import (
    VoiceInfo,
    VoiceListResponse,
    TTSSynthesizeRequest,
    TTSSynthesizeResponse,
    TTSBatchRequest,
    TTSBatchResponse,
    TTSBatchItemResult,
)
from src.models.tables import User
from src.services.tts_service import get_tts_service
from src.api.dependencies import get_current_active_user
from src.utils.exceptions import ExternalServiceError

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.get("/voices", response_model=VoiceListResponse)
async def get_voices(
    language: Optional[str] = Query(None, description="语言过滤（zh/en）"),
    current_user: User = Depends(get_current_active_user)
):
    """
    获取可用音色列表
    
    Args:
        language: 语言过滤（可选）
        current_user: 当前用户
        
    Returns:
        音色列表
    """
    try:
        tts_service = get_tts_service()
        voices = tts_service.get_voices(language=language)
        
        return VoiceListResponse(
            voices=[VoiceInfo(**v) for v in voices],
            total=len(voices)
        )
        
    except Exception as e:
        logger.error("获取音色列表失败", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/voices/{voice_id}", response_model=VoiceInfo)
async def get_voice(
    voice_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    获取单个音色信息
    
    Args:
        voice_id: 音色 ID
        current_user: 当前用户
        
    Returns:
        音色信息
    """
    try:
        tts_service = get_tts_service()
        voice = tts_service.get_voice_by_id(voice_id)
        
        if not voice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"音色 {voice_id} 不存在"
            )
        
        return VoiceInfo(**voice)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取音色信息失败", error=str(e), voice_id=voice_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/synthesize", response_model=TTSSynthesizeResponse)
async def synthesize(
    request: TTSSynthesizeRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    文本转语音
    
    Args:
        request: 合成请求
        current_user: 当前用户
        
    Returns:
        合成结果（包含音频 URL）
    """
    try:
        tts_service = get_tts_service()
        
        result = await tts_service.synthesize(
            text=request.text,
            voice=request.voice,
            format=request.format,
            sample_rate=request.sample_rate,
            volume=request.volume,
            speech_rate=request.speech_rate,
            pitch_rate=request.pitch_rate,
        )
        
        logger.info(
            "TTS 合成成功",
            voice=request.voice,
            text_length=len(request.text),
            user_id=current_user.id
        )
        
        return TTSSynthesizeResponse(**result)
        
    except ExternalServiceError as e:
        logger.error("TTS 服务错误", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )
    except Exception as e:
        logger.error("TTS 合成失败", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/synthesize/batch", response_model=TTSBatchResponse)
async def synthesize_batch(
    request: TTSBatchRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    批量文本转语音
    
    Args:
        request: 批量合成请求
        current_user: 当前用户
        
    Returns:
        批量合成结果
    """
    try:
        tts_service = get_tts_service()
        
        items = [{"id": item.id, "text": item.text} for item in request.items]
        
        results = await tts_service.synthesize_batch(
            items=items,
            voice=request.voice,
            format=request.format,
            sample_rate=request.sample_rate,
            volume=request.volume,
            speech_rate=request.speech_rate,
            pitch_rate=request.pitch_rate,
        )
        
        # 转换为响应格式
        result_items = []
        success_count = 0
        failure_count = 0
        
        for r in results:
            item_result = TTSBatchItemResult(
                id=r["id"],
                success=r["success"],
                url=r.get("url"),
                duration_ms=r.get("duration_ms"),
                error=r.get("error"),
            )
            result_items.append(item_result)
            
            if r["success"]:
                success_count += 1
            else:
                failure_count += 1
        
        logger.info(
            "TTS 批量合成完成",
            total=len(items),
            success=success_count,
            failure=failure_count,
            user_id=current_user.id
        )
        
        return TTSBatchResponse(
            results=result_items,
            success_count=success_count,
            failure_count=failure_count,
        )
        
    except Exception as e:
        logger.error("TTS 批量合成失败", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


