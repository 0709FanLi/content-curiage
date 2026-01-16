"""
视频管理路由
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import os
from typing import List
import structlog

from src.models.database import get_db
from src.models.tables.video_segment import VideoSegment
from src.models.schemas.video import (
    GenerateVideoRequest,
    GenerateVideosResponse,
    VideoSegmentResponse,
    RegenerateVideoSegmentRequest,
    UpdateVideoSegmentRequest,
    ExportVideosRequest,
    ExportVideosResponse,
    VideoModelsResponse,
    VideoModelInfo
)
from src.models.tables import User
from src.services.video_service import VideoService
from src.api.dependencies import get_current_active_user
from src.utils.exceptions import NotFoundError, ValidationError

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.get('/models')
async def get_video_models(
    current_user: User = Depends(get_current_active_user)
):
    """获取可用的视频生成模型列表.

    Returns:
        模型列表（包装格式）
    """
    try:
        models = VideoService.get_available_models()
        
        model_infos = [
            VideoModelInfo(
                id=m['id'],
                name=m['name'],
                description=m['description'],
                supports_first_last_frame=m['supports_first_last_frame']
            )
            for m in models
        ]
        
        result = VideoModelsResponse(models=model_infos)
        
        return {
            "code": 200,
            "message": "success",
            "data": result.model_dump(by_alias=True)
        }
    except Exception as e:
        logger.error('获取视频模型列表失败', error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='获取视频模型列表失败'
        )


@router.post('/generate')
async def generate_videos(
    request: GenerateVideoRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """生成视频片段（异步）.

    Args:
        request: 生成视频请求
        current_user: 当前用户
        db: 数据库会话

    Returns:
        视频片段列表（状态为generating，包装格式）

    Raises:
        HTTPException: 生成失败
    """
    try:
        video_service = VideoService(db)
        video_segments = await video_service.generate_videos(
            script_id=request.script_id,
            model=request.model,
            aspect_ratio=request.aspect_ratio,
            duration=request.duration
        )

        # 转换为响应模型
        segment_responses = [
            VideoSegmentResponse(
                id=vs.id,
                script_id=vs.script_id,
                segment_index=vs.segment_index,
                first_frame_url=vs.first_frame_url,
                last_frame_url=vs.last_frame_url,
                prompt=vs.prompt,
                video_url=vs.video_url,
                model=vs.model,
                aspect_ratio=vs.aspect_ratio,
                status=vs.status,
                duration=vs.duration,
                error_message=vs.error_message,
                audio_url=getattr(vs, 'audio_url', None),
                audio_status=getattr(vs, 'audio_status', None),
                audio_error_message=getattr(vs, 'audio_error_message', None),
                audio_duration_sec=getattr(vs, 'audio_duration_sec', None),
                created_at=vs.created_at,
                updated_at=vs.updated_at
            )
            for vs in video_segments
        ]

        result = GenerateVideosResponse(
            video_segments=segment_responses,
            total_count=len(segment_responses)
        )

        return {
            "code": 200,
            "message": "success",
            "data": result.model_dump(by_alias=True)
        }

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error('生成视频失败', error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='生成视频失败'
        )


@router.post('/script/{script_id}/prepare-audio')
async def prepare_audio_for_export(
    script_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """导出前准备配音：可听、重试一次、失败统一返回“模型维护中”."""
    try:
        video_service = VideoService(db)
        await video_service.prepare_audio_for_export(
            script_id=script_id,
            timeout_sec=int(os.getenv("EXPORT_WAIT_AUDIO_TIMEOUT_SEC", "600")),
            poll_interval_sec=float(os.getenv("EXPORT_WAIT_AUDIO_POLL_SEC", "2")),
        )
        return {"code": 200, "message": "success", "data": {"scriptId": script_id}}
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error("准备配音失败", script_id=script_id, error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="准备配音失败",
        )


@router.get('/script/{script_id}')
async def get_video_segments_by_script(
    script_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """获取脚本的视频片段列表.

    Args:
        script_id: 脚本ID
        current_user: 当前用户
        db: 数据库会话

    Returns:
        视频片段列表（包装格式）

    Raises:
        HTTPException: 获取失败
    """
    try:
        video_service = VideoService(db)
        segment_responses = await video_service.get_video_segments_by_script(
            script_id
        )

        result = GenerateVideosResponse(
            video_segments=segment_responses,
            total_count=len(segment_responses)
        )

        return {
            "code": 200,
            "message": "success",
            "data": result.model_dump(by_alias=True)
        }

    except Exception as e:
        logger.error('获取视频片段列表失败', error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='获取视频片段列表失败'
        )


@router.put('/{video_segment_id}')
async def update_video_segment(
    video_segment_id: int,
    request: UpdateVideoSegmentRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """更新视频片段（prompt、状态等）.

    Args:
        video_segment_id: 视频片段ID
        request: 更新请求
        current_user: 当前用户
        db: 数据库会话

    Returns:
        更新后的视频片段

    Raises:
        HTTPException: 更新失败
    """
    try:
        # 获取视频片段
        result = await db.execute(
            select(VideoSegment).where(VideoSegment.id == video_segment_id)
        )
        video_segment = result.scalar_one_or_none()
        
        if not video_segment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='视频片段不存在'
            )
        
        # 更新字段
        need_commit = False
        if request.prompt is not None:
            video_segment.prompt = request.prompt
            need_commit = True
            
        if request.video_url is not None:
            video_segment.video_url = request.video_url
            need_commit = True
            
        if request.status is not None:
            video_segment.status = request.status
            need_commit = True
            
        if request.error_message is not None:
            video_segment.error_message = request.error_message
            need_commit = True
            
        if need_commit:
            await db.commit()
            await db.refresh(video_segment)
        
        result = VideoSegmentResponse(
            id=video_segment.id,
            script_id=video_segment.script_id,
            segment_index=video_segment.segment_index,
            first_frame_url=video_segment.first_frame_url,
            last_frame_url=video_segment.last_frame_url,
            prompt=video_segment.prompt,
            video_url=video_segment.video_url,
            model=video_segment.model,
            aspect_ratio=video_segment.aspect_ratio,
            status=video_segment.status,
            duration=video_segment.duration,
            error_message=video_segment.error_message,
            created_at=video_segment.created_at,
            updated_at=video_segment.updated_at
        )
        
        return {
            "code": 200,
            "message": "success",
            "data": result.model_dump(by_alias=True)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            'Failed to update video segment',
            video_segment_id=video_segment_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='更新视频片段失败'
        )


@router.post('/{video_segment_id}/regenerate')
async def regenerate_video_segment(
    video_segment_id: int,
    request: RegenerateVideoSegmentRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """重新生成单个视频片段（提示词不可修改）.

    Args:
        video_segment_id: 视频片段ID
        request: 重新生成请求
        current_user: 当前用户
        db: 数据库会话

    Returns:
        更新后的视频片段（状态为generating，包装格式）

    Raises:
        HTTPException: 重新生成失败
    """
    try:
        video_service = VideoService(db)
        video_segment = await video_service.regenerate_video_segment(
            video_segment_id=video_segment_id,
            model=request.model
        )

        # 刷新对象以避免懒加载错误
        await db.refresh(video_segment)

        result = VideoSegmentResponse(
            id=video_segment.id,
            script_id=video_segment.script_id,
            segment_index=video_segment.segment_index,
            first_frame_url=video_segment.first_frame_url,
            last_frame_url=video_segment.last_frame_url,
            prompt=video_segment.prompt,
            video_url=video_segment.video_url,
            model=video_segment.model,
            aspect_ratio=video_segment.aspect_ratio,
            status=video_segment.status,
            duration=video_segment.duration,
            error_message=video_segment.error_message,
            created_at=video_segment.created_at,
            updated_at=video_segment.updated_at
        )

        return {
            "code": 200,
            "message": "success",
            "data": result.model_dump(by_alias=True)
        }

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error('重新生成视频失败', error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='重新生成视频失败'
        )


@router.post('/export')
async def export_videos(
    request: ExportVideosRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """导出脚本的所有视频.
    
    支持两种导出模式：
    - separate: 导出所有视频片段（单独文件，打包成ZIP）
    - concatenated: 拼接成一个完整视频（自动去除重复帧）

    Args:
        request: 导出请求（包含 scriptId 和 exportType）
        current_user: 当前用户
        db: 数据库会话

    Returns:
        包含下载URL和过期时间（包装格式）

    Raises:
        HTTPException: 导出失败
    """
    try:
        video_service = VideoService(db)
        export_result = await video_service.export_videos(
            script_id=request.script_id,
            export_type=request.export_type.value
        )

        # 仅在“拼接成一个完整视频”的导出模式下，才更新 script.exported_video_url。
        # separate 模式会返回 zip（片段打包），不应覆盖“最终成片地址”，否则前端会把 zip 当 mp4 播放。
        if request.export_type.value == 'concatenated':
            from src.models.tables.script import Script

            script_result = await db.execute(
                select(Script).where(Script.id == request.script_id)
            )
            script = script_result.scalar_one_or_none()
            if script:
                script.exported_video_url = export_result['download_url']
                await db.commit()

        result = ExportVideosResponse(
            download_url=export_result['download_url'],
            expires_in=export_result['expires_in']
        )

        return {
            "code": 200,
            "message": "success",
            "data": result.model_dump(by_alias=True)
        }

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValidationError as e:
        # 业务型错误（例如：用户取消生成）不应返回 500，保持与前端约定的 code/message
        return {
            "code": 400,
            "message": str(e),
            "data": None,
        }
    except Exception as e:
        logger.error('导出视频失败', error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='导出视频失败'
        )
