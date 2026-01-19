"""
一步生成（Agent 对话式长视频生成）路由
"""

import asyncio
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog
import json

from src.models.database import get_db
from src.models.database import async_session_maker
from src.models.tables import User
from src.models.tables.step_run import StepRun, StepRunStatus
from src.models.tables.step_run_event import StepRunEvent
from src.models.tables.step_segment import StepSegment
from src.models.tables.keyframe import Keyframe
from src.models.tables.video_segment import VideoSegment
from src.models.tables.script import Script
from src.models.schemas.step_generate import (
    StepRunCreateRequest,
    StepRunCreateResponse,
    StepRunStatusResponse,
    StepRunSnapshotResponse,
    StepSegmentResponse,
    SnapshotScriptResponse,
    SnapshotKeyframeResponse,
    SnapshotVideoSegmentResponse,
    StepRunEventResponse,
    StepRunCommandRequest,
)
from src.api.dependencies import get_current_active_user
from src.services.step_generate_service import StepGenerateService

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.get("/projects/{project_id}/latest-run")
async def get_latest_run_by_project(
    project_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """根据 project_id 获取最新一步生成 run（用于“从项目进入一步生成页面/刷新恢复”）。"""
    try:
        result = await db.execute(
            select(StepRun)
            .where(StepRun.project_id == project_id)
            .order_by(StepRun.id.desc())
            .limit(1)
        )
        run = result.scalar_one_or_none()
        if not run or run.user_id != current_user.id:
            # 统一返回空，前端可展示“无可恢复 run”
            return {"code": 200, "message": "success", "data": {"run_id": None}}
        return {
            "code": 200,
            "message": "success",
            "data": {"run_id": run.id, "script_id": run.script_id, "project_id": run.project_id},
        }
    except Exception as e:
        logger.error("Get latest run failed", project_id=project_id, error=str(e), exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="获取最新 run 失败")


@router.post("/runs")
async def create_step_run(
    request: StepRunCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        svc = StepGenerateService(db)
        run = await svc.create_run_with_project_and_script(
            user=current_user,
            title=request.title,
            inspiration=request.inspiration,
            total_duration_sec=request.total_duration_sec,
            segment_duration_sec=request.segment_duration_sec,
            aspect_ratio=request.aspect_ratio,
            style=request.style,
            enable_storyboard=request.enable_storyboard,
            enable_seedream_group=request.enable_seedream_group,
            video_mode=request.video_mode,
            decision_model_primary=request.decision_model_primary,
            decision_model_fallback=request.decision_model_fallback,
            decision_thinking_level=request.decision_thinking_level,
        )

        await svc.start_run_background(run.id)

        resp = StepRunCreateResponse(
            run_id=run.id,
            project_id=run.project_id or 0,
            script_id=run.script_id or 0,
        )
        return {"code": 200, "message": "success", "data": resp.model_dump()}
    except Exception as e:
        logger.error("Create step run failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"创建一步生成任务失败: {str(e)}")


@router.get("/runs/{run_id}")
async def get_step_run_status(
    run_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(select(StepRun).where(StepRun.id == run_id))
        run = result.scalar_one_or_none()
        if not run or run.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在或无权限")

        # segments 先不强依赖，后续补齐（目前 MVP 先复用 script+videos 页面查看产物）
        resp = StepRunStatusResponse(
            id=run.id,
            title=run.title,
            inspiration=run.inspiration,
            status=run.status.value if hasattr(run.status, "value") else str(run.status),
            current_step=run.current_step,
            error_message=run.error_message,
            final_video_url=run.final_video_url,
            project_id=run.project_id,
            script_id=run.script_id,
            total_duration_sec=run.total_duration_sec,
            segment_duration_sec=run.segment_duration_sec,
            aspect_ratio=run.aspect_ratio,
            enable_storyboard=getattr(run, "enable_storyboard", None),
            enable_seedream_group=getattr(run, "enable_seedream_group", None),
            video_mode=getattr(run, "video_mode", None),
            segments=[],
        )
        return {"code": 200, "message": "success", "data": resp.model_dump()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Get step run failed", run_id=run_id, error=str(e), exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="获取任务失败")


@router.get("/runs/{run_id}/snapshot")
async def get_step_run_snapshot(
    run_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """一步生成快照：单接口返回当前 run 已产出的内容（口播/分镜/视频等）。

    设计目标：前端可以“按步骤逐步展示”，而不是同时轮询多个资源接口。
    """
    try:
        result = await db.execute(select(StepRun).where(StepRun.id == run_id))
        run = result.scalar_one_or_none()
        if not run or run.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在或无权限")

        run_resp = StepRunStatusResponse(
            id=run.id,
            title=run.title,
            inspiration=run.inspiration,
            status=run.status.value if hasattr(run.status, "value") else str(run.status),
            current_step=run.current_step,
            error_message=run.error_message,
            final_video_url=run.final_video_url,
            project_id=run.project_id,
            script_id=run.script_id,
            total_duration_sec=run.total_duration_sec,
            segment_duration_sec=run.segment_duration_sec,
            aspect_ratio=run.aspect_ratio,
            enable_storyboard=getattr(run, "enable_storyboard", None),
            enable_seedream_group=getattr(run, "enable_seedream_group", None),
            video_mode=getattr(run, "video_mode", None),
            segments=[],
        )

        # 1) StepSegments（口播/视频描述）：有就返回
        step_segments_rows = (
            await db.execute(
                select(StepSegment).where(StepSegment.run_id == run_id).order_by(StepSegment.segment_index.asc())
            )
        ).scalars().all()
        step_segments = [
            StepSegmentResponse(
                id=s.id,
                segment_index=s.segment_index,
                segment_id=s.segment_id,
                start_ms=s.start_ms,
                end_ms=s.end_ms,
                narration=s.narration,
                video_desc=s.video_desc,
                audio_url=s.audio_url,
                audio_duration_sec=s.audio_duration_sec,
                video_url=s.video_url,
                merged_video_url=s.merged_video_url,
                error_message=s.error_message,
            )
            for s in step_segments_rows
        ]

        # 2) Script（全文 + segments 原始结构）
        script_resp = None
        if run.script_id:
            s = (await db.execute(select(Script).where(Script.id == run.script_id))).scalar_one_or_none()
            if s:
                # SQLite/SQLAlchemy JSON 字段可能是 dict/list 或 None
                segments_payload = s.segments if isinstance(s.segments, list) else []
                script_resp = SnapshotScriptResponse(id=s.id, content=s.content or "", segments=segments_payload)

        # 3) Keyframes/Videos（从现有表取，按 script_id）
        keyframes_resp: list[SnapshotKeyframeResponse] = []
        videos_resp: list[SnapshotVideoSegmentResponse] = []
        if run.script_id:
            kfs = (
                await db.execute(select(Keyframe).where(Keyframe.script_id == run.script_id).order_by(Keyframe.segment_id.asc()))
            ).scalars().all()
            keyframes_resp = [
                SnapshotKeyframeResponse(
                    id=k.id,
                    segment_id=k.segment_id,
                    image_url=k.image_url,
                    status=k.status.value if hasattr(k.status, "value") else str(k.status),
                    error_message=getattr(k, "error_message", None),
                )
                for k in kfs
            ]

            vids = (
                await db.execute(select(VideoSegment).where(VideoSegment.script_id == run.script_id).order_by(VideoSegment.segment_index.asc()))
            ).scalars().all()
            videos_resp = [
                SnapshotVideoSegmentResponse(
                    id=v.id,
                    segment_index=v.segment_index,
                    first_frame_url=v.first_frame_url,
                    video_url=v.video_url,
                    status=v.status.value if hasattr(v.status, "value") else str(v.status),
                    duration=getattr(v, "duration", None),
                    error_message=getattr(v, "error_message", None),
                )
                for v in vids
            ]

        snapshot = StepRunSnapshotResponse(
            run=run_resp,
            script=script_resp,
            step_segments=step_segments,
            keyframes=keyframes_resp,
            videos=videos_resp,
        )
        return {"code": 200, "message": "success", "data": snapshot.model_dump()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Get step run snapshot failed", run_id=run_id, error=str(e), exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="获取任务快照失败")


@router.get("/runs/{run_id}/events")
async def stream_step_run_events(
    run_id: int,
    after_id: int = 0,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    # 权限检查
    result = await db.execute(select(StepRun).where(StepRun.id == run_id))
    run = result.scalar_one_or_none()
    if not run or run.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在或无权限")

    async def event_generator():
        last_id = after_id
        while True:
            try:
                async with async_session_maker() as session:
                    result = await session.execute(
                        select(StepRunEvent)
                        .where(StepRunEvent.run_id == run_id)
                        .where(StepRunEvent.id > last_id)
                        .order_by(StepRunEvent.id.asc())
                        .limit(50)
                    )
                    events = result.scalars().all()
                if events:
                    for ev in events:
                        last_id = ev.id
                        payload = StepRunEventResponse(
                            id=ev.id,
                            level=ev.level,
                            event_type=ev.event_type,
                            message=ev.message,
                            data=ev.data,
                            created_at=ev.created_at.isoformat() if ev.created_at else None,
                        ).model_dump()
                        yield f"event: message\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                else:
                    # heartbeat
                    yield "event: ping\ndata: {}\n\n"
                await asyncio.sleep(1)
            except Exception as e:
                logger.error("SSE stream error", run_id=run_id, error=str(e))
                yield f"event: error\ndata: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(2)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/runs/{run_id}/command")
async def post_step_run_command(
    run_id: int,
    request: StepRunCommandRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(select(StepRun).where(StepRun.id == run_id))
        run = result.scalar_one_or_none()
        if not run or run.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在或无权限")

        svc = StepGenerateService(db)
        await svc._append_event(
            run_id=run_id,
            level="info",
            event_type="user_command",
            message=request.message,
        )

        msg = (request.message or "").strip()
        msg_lower = msg.lower()

        # 1) 导出/合成：允许失败后补救（例如视频段都完成但 run 在 wait_videos 超时）
        export_keywords = ["导出", "合成", "成片", "拼接", "输出"]
        if any(k in msg for k in export_keywords):
            await svc._append_event(
                run_id=run_id,
                level="info",
                event_type="command_parsed",
                message="已解析指令：仅导出拼接成片（export_only）",
                data={"scope": "export_only"},
            )
            await svc.start_export_only(run_id=run_id)
            return {"code": 200, "message": "success", "data": {"run_id": run_id}}

        # 2) 重试：仅在 FAILED/CANCELLED 时允许（重新跑整条流水线）
        retry_keywords = ["重试", "重新运行", "重新开始", "retry"]
        if any(k in msg for k in retry_keywords):
            if str(run.status.value if hasattr(run.status, "value") else run.status).lower() not in ("failed", "cancelled"):
                await svc._append_event(
                    run_id=run_id,
                    level="warning",
                    event_type="command_ignored",
                    message="当前任务仍在运行或已完成；重试仅在失败/取消后可用",
                )
            else:
                run.status = StepRunStatus.PENDING
                run.current_step = 0
                run.error_message = None
                run.final_video_url = None
                await db.commit()
                await svc._append_event(
                    run_id=run_id,
                    level="info",
                    event_type="retry_started",
                    message="已开始重试（将重新执行一步生成流水线）",
                )
                await svc.start_run_background(run.id)
            return {"code": 200, "message": "success", "data": {"run_id": run_id}}

        # 3) “第10s…”：video_only 重生成（失败/完成后都允许）
        t = StepGenerateService.parse_regenerate_time_seconds(request.message)
        if t is not None:
            await svc._append_event(
                run_id=run_id,
                level="info",
                event_type="command_parsed",
                message="已解析重生成指令：将按时间点定位片段并进行 video_only 重生成",
                data={"time_sec": t, "scope": "video_only"},
            )
            await svc.start_regenerate_video_only(run_id=run_id, time_sec=t)
        else:
            await svc._append_event(
                run_id=run_id,
                level="warning",
                event_type="command_ignored",
                message="暂不支持的指令（支持：重试 / 导出成片 / 第Xs重生成）",
            )

        return {"code": 200, "message": "success", "data": {"run_id": run_id}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Post command failed", run_id=run_id, error=str(e), exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="指令处理失败")

