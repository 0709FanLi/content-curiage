"""
项目管理路由
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import structlog

from src.models.database import get_db
from src.models.schemas.project import (
    ProjectCreate, 
    ProjectUpdate, 
    ProjectResponse,
    ProjectDetailResponse
)
from src.models.tables import User
from src.services.project_service import ProjectService
from src.api.dependencies import get_current_active_user
from src.utils.exceptions import NotFoundError

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.get("")
async def get_projects(
    skip: int = Query(0, ge=0),
    page_size: int = Query(100, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取项目列表
    
    Args:
        skip: 跳过数量
        page_size: 每页数量
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        项目列表（包装格式）
    """
    try:
        project_service = ProjectService(db)
        projects = await project_service.get_projects(
            user_id=current_user.id,
            skip=skip,
            limit=page_size
        )
        
        # 将SQLAlchemy对象转换为Pydantic模型，使用别名序列化
        project_responses = []
        for project in projects:
            try:
                project_response = ProjectResponse.model_validate(project).model_dump(by_alias=True)
                project_responses.append(project_response)
            except Exception as validation_error:
                logger.warning(
                    "项目数据验证失败，跳过该项目",
                    project_id=project.id,
                    error=str(validation_error)
                )
                # 跳过有问题的项目，继续处理其他项目
                continue
        
        # 返回包装格式
        return {
            "code": 200,
            "message": "success",
            "data": {
                "items": project_responses,
                "total": len(project_responses)
            }
        }
    except Exception as e:
        logger.error("获取项目列表失败", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取项目列表失败"
        )


@router.get("/recent")
async def get_recent_projects(
    limit: int = Query(5, ge=1, le=20),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取最近项目列表
    
    Args:
        limit: 限制数量
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        最近项目列表（包装格式）
    """
    try:
        project_service = ProjectService(db)
        projects = await project_service.get_recent_projects(
            user_id=current_user.id,
            limit=limit
        )
        
        # 将SQLAlchemy对象转换为Pydantic模型，使用别名序列化
        project_responses = []
        for project in projects:
            try:
                project_response = ProjectResponse.model_validate(project).model_dump(by_alias=True)
                project_responses.append(project_response)
            except Exception as validation_error:
                logger.warning(
                    "项目数据验证失败，跳过该项目",
                    project_id=project.id,
                    error=str(validation_error)
                )
                # 跳过有问题的项目，继续处理其他项目
                continue
        
        # 返回包装格式，与其他API保持一致
        return {
            "code": 200,
            "message": "success",
            "data": project_responses
        }
    except Exception as e:
        logger.error("获取最近项目失败", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取最近项目失败"
        )


@router.get("/{project_id}")
async def get_project(
    project_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取项目详情
    
    Args:
        project_id: 项目ID
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        项目详情（包装格式）
    """
    try:
        project_service = ProjectService(db)
        project = await project_service.get_project(project_id, current_user.id)
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"项目 {project_id} 不存在"
            )
        
        # 将SQLAlchemy对象转换为字典
        project_dict = {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "status": project.status.value if hasattr(project.status, 'value') else project.status,
            "userId": project.user_id,
            "conversationContent": project.conversation_content,
            "imageModel": project.image_model,
            "aspectRatio": project.aspect_ratio,
            "quality": project.quality,
            "generationMode": project.generation_mode or 'step_by_step',
            "referenceImageUrls": (project.reference_image_urls or []) if hasattr(project, "reference_image_urls") else [],
            "createdAt": project.created_at.isoformat() if project.created_at else None,
            "updatedAt": project.updated_at.isoformat() if project.updated_at else None,
        }
        
        # 处理scripts关系：如果有脚本，取最新的一个作为script字段
        if project.scripts and len(project.scripts) > 0:
            # 按创建时间排序，取最新的
            sorted_scripts = sorted(project.scripts, key=lambda s: s.created_at, reverse=True)
            latest_script = sorted_scripts[0]
            
            # 设置script字段（单数）
            project_dict["script"] = {
                "id": latest_script.id,
                "projectId": latest_script.project_id,
                "content": latest_script.content,
                "style": latest_script.style,
                "totalDuration": latest_script.total_duration,
                "segmentDuration": latest_script.segment_duration,
                "segments": latest_script.segments or [],
                "optimizedContent": latest_script.optimized_content,
                "createdAt": latest_script.created_at.isoformat() if latest_script.created_at else None,
                "updatedAt": latest_script.updated_at.isoformat() if latest_script.updated_at else None,
            }
            
            # 同时保留scripts数组（复数）
            project_dict["scripts"] = [
                {
                    "id": s.id,
                    "projectId": s.project_id,
                    "content": s.content,
                    "style": s.style,
                    "totalDuration": s.total_duration,
                    "segmentDuration": s.segment_duration,
                    "segments": s.segments or [],
                    "optimizedContent": s.optimized_content,
                    "createdAt": s.created_at.isoformat() if s.created_at else None,
                    "updatedAt": s.updated_at.isoformat() if s.updated_at else None,
                }
                for s in sorted_scripts
            ]
        else:
            project_dict["script"] = None
            project_dict["scripts"] = []
        
        logger.info(
            "Retrieved project detail",
            project_id=project_id,
            has_scripts=len(project.scripts) > 0 if project.scripts else False,
            script_count=len(project.scripts) if project.scripts else 0
        )
        
        # 返回包装格式，与其他API保持一致
        return {
            "code": 200,
            "message": "success",
            "data": project_dict
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取项目详情失败", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取项目详情失败"
        )


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    创建项目
    
    Args:
        project_data: 项目创建数据
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        创建的项目
    """
    try:
        project_service = ProjectService(db)
        project = await project_service.create_project(project_data, current_user.id)
        return project
    except Exception as e:
        logger.error("创建项目失败", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建项目失败"
        )


@router.put("/{project_id}")
async def update_project(
    project_id: int,
    project_data: ProjectUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    更新项目
    
    Args:
        project_id: 项目ID
        project_data: 项目更新数据
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        更新后的项目（包装格式）
    """
    try:
        project_service = ProjectService(db)
        project = await project_service.update_project(
            project_id, 
            project_data, 
            current_user.id
        )
        
        # 将SQLAlchemy对象转换为Pydantic模型，使用别名序列化
        project_response = ProjectResponse.model_validate(project).model_dump(by_alias=True)
        
        # 返回包装格式，与其他API保持一致
        return {
            "code": 200,
            "message": "success",
            "data": project_response
        }
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error("更新项目失败", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新项目失败"
        )


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    删除项目
    
    Args:
        project_id: 项目ID
        current_user: 当前用户
        db: 数据库会话
    """
    try:
        project_service = ProjectService(db)
        await project_service.delete_project(project_id, current_user.id)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error("删除项目失败", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除项目失败"
        )
