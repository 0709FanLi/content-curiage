"""
时间线管理路由

提供 Timeline、Track、Clip 的 RESTful API
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import structlog

from src.models.database import get_db
from src.models.schemas.timeline import (
    TimelineCreate, TimelineUpdate, TimelineResponse,
    TrackCreate, TrackUpdate, TrackResponse,
    ClipCreate, ClipUpdate, ClipResponse,
    ClipBatchCreate, ClipBatchDelete,
    TimelinePatch, TimelinePatchResponse,
    TrackType,
)
from src.models.tables import User
from src.services.timeline_service import TimelineService
from src.api.dependencies import get_current_active_user
from src.utils.exceptions import NotFoundError, BusinessError

router = APIRouter()
logger = structlog.get_logger(__name__)


# ========== Timeline Endpoints ==========

@router.get("/project/{project_id}", response_model=TimelineResponse)
async def get_timeline_by_project(
    project_id: int = Path(..., description="项目ID"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    根据项目ID获取时间线（包含所有轨道和片段）
    
    Args:
        project_id: 项目ID
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        时间线详情
    """
    try:
        service = TimelineService(db)
        timeline = await service.get_timeline_by_project(project_id)
        
        if not timeline:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"项目 {project_id} 没有时间线"
            )
        
        return TimelineResponse.model_validate(timeline)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取时间线失败", error=str(e), project_id=project_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/project/{project_id}", response_model=TimelineResponse, status_code=status.HTTP_201_CREATED)
async def create_timeline(
    project_id: int = Path(..., description="项目ID"),
    data: Optional[TimelineCreate] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    为项目创建时间线（自动创建默认轨道）
    
    Args:
        project_id: 项目ID
        data: 时间线配置（可选）
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        创建的时间线
    """
    try:
        service = TimelineService(db)
        timeline = await service.create_timeline(project_id, data)
        return TimelineResponse.model_validate(timeline)
        
    except BusinessError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("创建时间线失败", error=str(e), project_id=project_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/project/{project_id}/ensure", response_model=TimelineResponse)
async def get_or_create_timeline(
    project_id: int = Path(..., description="项目ID"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取或创建项目的时间线（确保存在）
    
    Args:
        project_id: 项目ID
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        时间线详情
    """
    try:
        service = TimelineService(db)
        timeline = await service.get_or_create_timeline(project_id)
        return TimelineResponse.model_validate(timeline)
        
    except Exception as e:
        logger.error("获取/创建时间线失败", error=str(e), project_id=project_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{timeline_id}", response_model=TimelineResponse)
async def get_timeline(
    timeline_id: int = Path(..., description="时间线ID"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取时间线详情
    
    Args:
        timeline_id: 时间线ID
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        时间线详情
    """
    try:
        service = TimelineService(db)
        timeline = await service.get_timeline(timeline_id)
        
        if not timeline:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"时间线 {timeline_id} 不存在"
            )
        
        return TimelineResponse.model_validate(timeline)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取时间线失败", error=str(e), timeline_id=timeline_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.patch("/{timeline_id}", response_model=TimelineResponse)
async def update_timeline(
    timeline_id: int = Path(..., description="时间线ID"),
    data: TimelineUpdate = None,
    expected_version: Optional[int] = Query(None, alias="expectedVersion", description="期望版本号（乐观锁）"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    更新时间线
    
    Args:
        timeline_id: 时间线ID
        data: 更新数据
        expected_version: 期望版本号（用于乐观锁）
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        更新后的时间线
    """
    try:
        service = TimelineService(db)
        timeline = await service.update_timeline(timeline_id, data, expected_version)
        return TimelineResponse.model_validate(timeline)
        
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        logger.error("更新时间线失败", error=str(e), timeline_id=timeline_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/{timeline_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_timeline(
    timeline_id: int = Path(..., description="时间线ID"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    删除时间线
    
    Args:
        timeline_id: 时间线ID
        current_user: 当前用户
        db: 数据库会话
    """
    try:
        service = TimelineService(db)
        deleted = await service.delete_timeline(timeline_id)
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"时间线 {timeline_id} 不存在"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("删除时间线失败", error=str(e), timeline_id=timeline_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ========== Track Endpoints ==========

@router.post("/tracks", response_model=TrackResponse, status_code=status.HTTP_201_CREATED)
async def create_track(
    data: TrackCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    创建轨道
    
    Args:
        data: 轨道创建数据
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        创建的轨道
    """
    try:
        service = TimelineService(db)
        track = await service.create_track(data)
        return TrackResponse.model_validate(track)
        
    except Exception as e:
        logger.error("创建轨道失败", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/tracks/{track_id}", response_model=TrackResponse)
async def get_track(
    track_id: int = Path(..., description="轨道ID"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取轨道详情
    
    Args:
        track_id: 轨道ID
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        轨道详情
    """
    try:
        service = TimelineService(db)
        track = await service.get_track(track_id)
        
        if not track:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"轨道 {track_id} 不存在"
            )
        
        return TrackResponse.model_validate(track)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取轨道失败", error=str(e), track_id=track_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.patch("/tracks/{track_id}", response_model=TrackResponse)
async def update_track(
    track_id: int = Path(..., description="轨道ID"),
    data: TrackUpdate = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    更新轨道
    
    Args:
        track_id: 轨道ID
        data: 更新数据
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        更新后的轨道
    """
    try:
        service = TimelineService(db)
        track = await service.update_track(track_id, data)
        return TrackResponse.model_validate(track)
        
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("更新轨道失败", error=str(e), track_id=track_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/tracks/{track_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_track(
    track_id: int = Path(..., description="轨道ID"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    删除轨道
    
    Args:
        track_id: 轨道ID
        current_user: 当前用户
        db: 数据库会话
    """
    try:
        service = TimelineService(db)
        deleted = await service.delete_track(track_id)
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"轨道 {track_id} 不存在"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("删除轨道失败", error=str(e), track_id=track_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ========== Clip Endpoints ==========

@router.post("/clips", response_model=ClipResponse, status_code=status.HTTP_201_CREATED)
async def create_clip(
    data: ClipCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    创建片段
    
    Args:
        data: 片段创建数据
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        创建的片段
    """
    try:
        service = TimelineService(db)
        clip = await service.create_clip(data)
        return ClipResponse.model_validate(clip)
        
    except BusinessError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("创建片段失败", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/clips/batch", response_model=List[ClipResponse], status_code=status.HTTP_201_CREATED)
async def create_clips_batch(
    data: ClipBatchCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    批量创建片段
    
    Args:
        data: 片段创建数据列表
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        创建的片段列表
    """
    try:
        service = TimelineService(db)
        clips = await service.create_clips_batch(data.clips)
        return [ClipResponse.model_validate(clip) for clip in clips]
        
    except BusinessError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("批量创建片段失败", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/clips/{clip_id}", response_model=ClipResponse)
async def get_clip(
    clip_id: int = Path(..., description="片段ID"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取片段详情
    
    Args:
        clip_id: 片段ID
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        片段详情
    """
    try:
        service = TimelineService(db)
        clip = await service.get_clip(clip_id)
        
        if not clip:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"片段 {clip_id} 不存在"
            )
        
        return ClipResponse.model_validate(clip)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取片段失败", error=str(e), clip_id=clip_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.patch("/clips/{clip_id}", response_model=ClipResponse)
async def update_clip(
    clip_id: int = Path(..., description="片段ID"),
    data: ClipUpdate = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    更新片段
    
    Args:
        clip_id: 片段ID
        data: 更新数据
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        更新后的片段
    """
    try:
        service = TimelineService(db)
        clip = await service.update_clip(clip_id, data)
        return ClipResponse.model_validate(clip)
        
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("更新片段失败", error=str(e), clip_id=clip_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/clips/{clip_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_clip(
    clip_id: int = Path(..., description="片段ID"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    删除片段
    
    Args:
        clip_id: 片段ID
        current_user: 当前用户
        db: 数据库会话
    """
    try:
        service = TimelineService(db)
        deleted = await service.delete_clip(clip_id)
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"片段 {clip_id} 不存在"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("删除片段失败", error=str(e), clip_id=clip_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/clips/batch/delete", status_code=status.HTTP_200_OK)
async def delete_clips_batch(
    data: ClipBatchDelete,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    批量删除片段
    
    Args:
        data: 片段ID列表
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        删除结果
    """
    try:
        service = TimelineService(db)
        count = await service.delete_clips_batch(data.clip_ids)
        return {"deleted": count}
        
    except Exception as e:
        logger.error("批量删除片段失败", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ========== Patch Endpoint (用于撤销/重做) ==========

@router.post("/patch", response_model=TimelinePatchResponse)
async def apply_patch(
    patch: TimelinePatch,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    应用时间线补丁操作（用于撤销/重做）
    
    Args:
        patch: 补丁数据
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        补丁应用结果
    """
    try:
        service = TimelineService(db)
        result = await service.apply_patch(patch)
        return result
        
    except Exception as e:
        logger.error("应用补丁失败", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


