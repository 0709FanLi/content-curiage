"""
Medeo API 代理路由

前端只调用本系统后端，后端使用 MEDEO_API_KEY 与 Medeo 通信。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.api.dependencies import get_current_active_user
from src.models.database import get_db
from src.models.schemas.medeo import (
    MedeoLastTaskStatusResponse,
    MedeoProjectInitiateRequest,
    MedeoProjectInitiateResponse,
    MedeoProjectSnapshotResponse,
    MedeoProjectUpdateRequest,
    MedeoRenderJobCreateRequest,
    MedeoRenderJobResponse,
    MedeoRecipeListResponse,
)
from src.models.schemas.project import ProjectCreate
from src.models.tables import MedeoProject, Project, User
from src.services.medeo_service import MedeoService, MedeoServiceError
from src.services.project_service import ProjectService
from src.config.settings import settings

logger = structlog.get_logger(__name__)
router = APIRouter()


def _oss_full_url(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    base = (settings.medeo_oss_base_url or "https://oss.prd.medeo.app").rstrip("/")
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"{base}/{path.lstrip('/')}"


@router.get("/recipes")
async def list_recipes(
    limit: int = Query(20, ge=1, le=100),
    order: str = Query("desc"),
    current_user: User = Depends(get_current_active_user),
):
    """Public recipes：后端代转（无需 key）。"""
    try:
        svc = MedeoService()
        data = await svc.list_recipes(limit=limit, order=order)
        resp = MedeoRecipeListResponse(
            has_more=bool(data.get("has_more", False)),
            next_cursor=data.get("next_cursor"),
            list=list(data.get("list") or []),
        )
        return {"code": 200, "message": "success", "data": resp.model_dump()}
    except MedeoServiceError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        logger.error("list_recipes failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="获取 recipes 失败")


@router.post("/projects/initiate")
async def initiate_project(
    request: MedeoProjectInitiateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """创建本系统 Project（generation_mode=medeo）并发起 Medeo initiate。"""
    created_project_id: Optional[int] = None
    try:
        project_service = ProjectService(db)
        title = (request.prompt or "").strip()[:40] or "Medeo Project"
        project = await project_service.create_project(
            ProjectCreate(name=title, description=None, generationMode="medeo"),
            user_id=current_user.id,
        )
        created_project_id = project.id

        payload: Dict[str, Any] = {
            "media_ids": request.media_ids or [],
            "message": {
                "sender_id": str(current_user.id),
                "content": [{"text": {"type": "text", "text": request.prompt}}],
            },
            "settings": request.settings.model_dump(exclude_none=True),
        }

        svc = MedeoService()
        medeo_resp = await svc.initiate_video_creation(payload=payload)
        mp = MedeoProject(
            project_id=project.id,
            medeo_project_id=str(medeo_resp.get("project_id") or ""),
            video_draft_id=str(medeo_resp.get("video_draft_id") or ""),
            chat_session_id=str(medeo_resp.get("chat_session_id") or ""),
        )
        db.add(mp)
        await db.commit()
        await db.refresh(mp)

        resp = MedeoProjectInitiateResponse(
            project_id=project.id,
            medeo_project_id=mp.medeo_project_id or "",
            video_draft_id=mp.video_draft_id or "",
            chat_session_id=mp.chat_session_id or "",
        )
        return {"code": 200, "message": "success", "data": resp.model_dump()}
    except MedeoServiceError as e:
        # 失败时清理刚创建的 project，避免项目列表出现“空壳 medeo 项目”
        try:
            if created_project_id:
                p = (await db.execute(select(Project).where(Project.id == created_project_id))).scalar_one_or_none()
                if p:
                    await db.delete(p)
                    await db.commit()
        except Exception:
            pass
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        logger.error("initiate_project failed", error=str(e), exc_info=True)
        # 失败时清理刚创建的 project
        try:
            if created_project_id:
                p = (await db.execute(select(Project).where(Project.id == created_project_id))).scalar_one_or_none()
                if p:
                    await db.delete(p)
                    await db.commit()
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"发起 Medeo 项目失败: {str(e)}",
        )


@router.get("/projects/{project_id}")
async def get_project_snapshot(
    project_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """读取 Medeo 项目映射信息（用于项目列表直接进入预览页恢复）。"""
    try:
        p = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
        if not p or p.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在或无权限")

        mp = (
            await db.execute(select(MedeoProject).where(MedeoProject.project_id == project_id))
        ).scalar_one_or_none()
        if not mp:
            return {"code": 200, "message": "success", "data": MedeoProjectSnapshotResponse(project_id=project_id).model_dump()}

        resp = MedeoProjectSnapshotResponse(
            project_id=project_id,
            chat_session_id=mp.chat_session_id,
            video_draft_id=mp.video_draft_id,
            video_draft_op_record_id=mp.video_draft_op_record_id,
            last_task_status=mp.last_task_status,
            render_status=mp.render_status,
            render_url=mp.render_url,
            render_full_url=_oss_full_url(mp.render_url),
            render_metadata=mp.render_metadata,
            last_error=mp.last_error,
        )
        return {"code": 200, "message": "success", "data": resp.model_dump()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_project_snapshot failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="获取 Medeo 项目失败")


@router.patch("/projects/{project_id}")
async def update_project_snapshot(
    project_id: int,
    request: MedeoProjectUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """写回轮询到的 Medeo 状态，便于恢复/项目列表直达预览。"""
    try:
        p = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
        if not p or p.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在或无权限")

        mp = (
            await db.execute(select(MedeoProject).where(MedeoProject.project_id == project_id))
        ).scalar_one_or_none()
        if not mp:
            mp = MedeoProject(project_id=project_id)
            db.add(mp)

        if request.video_draft_op_record_id is not None:
            mp.video_draft_op_record_id = request.video_draft_op_record_id
        if request.last_task_status is not None:
            mp.last_task_status = request.last_task_status
        if request.render_status is not None:
            mp.render_status = request.render_status
        if request.render_url is not None:
            mp.render_url = request.render_url
        if request.render_metadata is not None:
            mp.render_metadata = request.render_metadata
        if request.last_error is not None:
            mp.last_error = request.last_error

        await db.commit()
        await db.refresh(mp)
        return {"code": 200, "message": "success", "data": {"project_id": project_id}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("update_project_snapshot failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="更新 Medeo 项目失败")


@router.get("/chat-sessions/{chat_session_id}/last-task-status")
async def get_last_task_status(
    chat_session_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """轮询生成状态：last_task_status。"""
    try:
        svc = MedeoService()
        data = await svc.get_last_task_status(chat_session_id=chat_session_id)
        resp = MedeoLastTaskStatusResponse(
            status=str(data.get("status") or ""),
            video_draft_op_record_id=data.get("video_draft_op_record_id"),
        )
        return {"code": 200, "message": "success", "data": resp.model_dump()}
    except MedeoServiceError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        logger.error("get_last_task_status failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="获取生成状态失败")


@router.post("/render-video-jobs")
async def create_render_job(
    request: MedeoRenderJobCreateRequest,
    current_user: User = Depends(get_current_active_user),
):
    """触发渲染任务（前端默认自动调用）。"""
    try:
        svc = MedeoService()
        data = await svc.create_render_job(video_draft_op_record_id=request.video_draft_op_record_id)
        resp = MedeoRenderJobResponse(
            video_draft_op_record_id=str(data.get("video_draft_op_record_id") or request.video_draft_op_record_id),
            status=str(data.get("status") or ""),
            result=data.get("result"),
        )
        return {"code": 200, "message": "success", "data": resp.model_dump()}
    except MedeoServiceError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        logger.error("create_render_job failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="创建渲染任务失败")


@router.get("/render-video-jobs")
async def query_render_job(
    video_draft_op_record_id: str = Query(..., min_length=1),
    current_user: User = Depends(get_current_active_user),
):
    """查询渲染任务状态与结果。"""
    try:
        svc = MedeoService()
        data = await svc.query_render_job(video_draft_op_record_id=video_draft_op_record_id)
        result = data.get("result") if isinstance(data, dict) else None
        # 兼容：补 full_url
        if isinstance(result, dict) and result.get("url"):
            result = dict(result)
            result["full_url"] = _oss_full_url(str(result.get("url")))
        resp = MedeoRenderJobResponse(
            video_draft_op_record_id=str(data.get("video_draft_op_record_id") or video_draft_op_record_id),
            status=str(data.get("status") or ""),
            result=result,
        )
        return {"code": 200, "message": "success", "data": resp.model_dump()}
    except MedeoServiceError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        logger.error("query_render_job failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="查询渲染任务失败")

