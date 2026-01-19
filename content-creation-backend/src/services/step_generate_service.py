"""
一步生成 Agent 服务（后端编排）

当前阶段目标：
- 创建 run 后异步执行主流程，并写入 step_run_events 供 SSE 展示
- 复用现有 ScriptService / VideoService / TTSService 能力（后续再逐步强化“音频驱动时长”等策略）
"""

from __future__ import annotations

import asyncio
import re
from typing import Optional

import structlog
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.database import async_session_maker
from src.models.tables.project import Project, ProjectStatus
from src.models.tables.script import Script
from src.models.tables.video_segment import VideoSegment, VideoStatus
from src.models.tables.step_run import StepRun, StepRunStatus
from src.models.tables.step_run_event import StepRunEvent
from src.models.tables.step_segment import StepSegment
from src.models.tables.user import User
from src.models.schemas.script import GenerateScriptRequest
from src.services.script_service import ScriptService
from src.services.video_service import VideoService, DOUBAO_SEEDANCE_1_5_PRO_MODEL_ID
from src.services.keyframe_service import KeyframeService
from src.models.tables.keyframe import Keyframe, KeyframeStatus
logger = structlog.get_logger(__name__)


class StepGenerateService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _append_event(
        self,
        *,
        run_id: int,
        level: str,
        event_type: str,
        message: str,
        data: Optional[dict] = None,
    ) -> None:
        ev = StepRunEvent(
            run_id=run_id,
            level=level,
            event_type=event_type,
            message=message,
            data=data,
        )
        self.db.add(ev)
        await self.db.commit()

    async def create_run_with_project_and_script(
        self,
        *,
        user: User,
        title: Optional[str],
        inspiration: str,
        total_duration_sec: int,
        segment_duration_sec: int,
        aspect_ratio: Optional[str],
        style: str,
        enable_storyboard: bool,
        enable_seedream_group: bool,
        video_mode: str,
        decision_model_primary: str,
        decision_model_fallback: str,
        decision_thinking_level: str,
    ) -> StepRun:
        # 1) 创建项目（独立页面/独立记录）
        project_name = (title or inspiration.strip())[:10] + "..." if len((title or inspiration.strip())) > 10 else (title or inspiration.strip() or "一步生成")
        project = Project(
            name=f"一步生成-{project_name}",
            description=inspiration[:500],
            status=ProjectStatus.DRAFT,
            user_id=user.id,
            conversation_content=inspiration,
            aspect_ratio=aspect_ratio,
            generation_mode="one_step",
        )
        self.db.add(project)
        await self.db.commit()
        await self.db.refresh(project)

        # 2) 创建脚本占位（后续由 agent 写入真实内容）
        script = Script(
            project_id=project.id,
            content="生成中…",
            style=style,
            total_duration=total_duration_sec,
            segment_duration=segment_duration_sec,
            segments=None,
        )
        self.db.add(script)
        await self.db.commit()
        await self.db.refresh(script)

        # 3) 创建 run
        run = StepRun(
            user_id=user.id,
            project_id=project.id,
            script_id=script.id,
            title=title,
            inspiration=inspiration,
            total_duration_sec=total_duration_sec,
            segment_duration_sec=segment_duration_sec,
            aspect_ratio=aspect_ratio,
            enable_storyboard=bool(enable_storyboard),
            enable_seedream_group=bool(enable_seedream_group),
            video_mode=(video_mode or "auto"),
            decision_model_primary=decision_model_primary,
            decision_model_fallback=decision_model_fallback,
            decision_thinking_level=decision_thinking_level,
            status=StepRunStatus.PENDING,
            current_step=0,
        )
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)

        await self._append_event(
            run_id=run.id,
            level="info",
            event_type="run_created",
            message="已创建一步生成任务",
            data={"project_id": project.id, "script_id": script.id},
        )
        return run

    async def start_run_background(self, run_id: int) -> None:
        # 复用项目里的模式：用 asyncio.create_task 跑后台流水线
        asyncio.create_task(self._run_pipeline(run_id))

    async def start_export_only(self, *, run_id: int) -> None:
        """补救动作：当分段视频已生成但 run 未导出成片时，触发仅导出拼接（不重跑前置步骤）。"""
        asyncio.create_task(self._export_only(run_id=run_id))

    async def _export_only(self, *, run_id: int) -> None:
        async with async_session_maker() as db:
            svc = StepGenerateService(db)
            try:
                run = (await db.execute(select(StepRun).where(StepRun.id == run_id))).scalar_one_or_none()
                if not run:
                    return

                await svc._append_event(
                    run_id=run_id,
                    level="info",
                    event_type="export_start",
                    message="开始仅导出拼接成片（export_only）…",
                )

                if not run.script_id:
                    raise Exception("run 缺少 script_id，无法导出")

                vs_rows = (
                    await db.execute(select(VideoSegment).where(VideoSegment.script_id == run.script_id))
                ).scalars().all()
                if not vs_rows:
                    raise Exception("未找到任何视频段，无法导出")

                def _norm_status(x) -> str:
                    raw = x.value if hasattr(x, "value") else x
                    s = str(raw).split(".")[-1].strip().lower()
                    return s

                if any(_norm_status(v.status) == "failed" for v in vs_rows):
                    raise Exception("存在失败的视频段，无法导出")
                if not all(_norm_status(v.status) == "completed" for v in vs_rows):
                    raise Exception("仍有视频段未完成，无法导出")

                video_service = VideoService(db)
                export_result = await video_service.export_videos(
                    script_id=run.script_id,
                    export_type="concatenated",
                )
                final_url = str(export_result.get("download_url") or "")
                if not final_url:
                    raise Exception("导出未返回 download_url")

                run.final_video_url = final_url
                run.status = StepRunStatus.COMPLETED
                run.current_step = max(int(run.current_step or 0), 7)
                run.error_message = None
                await db.commit()

                await svc._append_event(
                    run_id=run_id,
                    level="info",
                    event_type="export_done",
                    message="导出拼接完成（export_only）",
                    data={"final_video_url": final_url},
                )
            except Exception as e:
                logger.error("Export only failed", run_id=run_id, error=str(e), exc_info=True)
                try:
                    await svc._append_event(
                        run_id=run_id,
                        level="error",
                        event_type="export_failed",
                        message="导出拼接失败（export_only）",
                        data={"error": str(e)},
                    )
                except Exception:
                    pass

    async def _run_pipeline(self, run_id: int) -> None:
        async with async_session_maker() as db:
            svc = StepGenerateService(db)
            try:
                result = await db.execute(select(StepRun).where(StepRun.id == run_id))
                run = result.scalar_one()

                run.status = StepRunStatus.RUNNING
                run.current_step = 1
                await db.commit()

                await svc._append_event(
                    run_id=run_id,
                    level="info",
                    event_type="step_start",
                    message="Step1: 开始生成分段口播文案/视频描述",
                )

                # Step1-4：复用现有 ScriptService 的脚本生成能力（含口播文案+视频描述字段）
                script_service = ScriptService(db)
                try:
                    generate_req = GenerateScriptRequest(
                        inspiration=run.inspiration,
                        style="默认",
                        totalDuration=int(run.total_duration_sec),
                        segmentDuration=int(run.segment_duration_sec),
                        projectId=run.project_id,
                        generationMode="one_step",
                        referenceImageUrls=None,
                        enableSearch=False,
                    )
                    gen = await script_service.generate_script(
                        generate_req, model=run.decision_model_primary
                    )
                except Exception as e:
                    await svc._append_event(
                        run_id=run_id,
                        level="warning",
                        event_type="model_fallback",
                        message="主模型生成脚本失败，切换回退模型",
                        data={"primary": run.decision_model_primary, "fallback": run.decision_model_fallback, "error": str(e)},
                    )
                    generate_req = GenerateScriptRequest(
                        inspiration=run.inspiration,
                        style="默认",
                        totalDuration=int(run.total_duration_sec),
                        segmentDuration=int(run.segment_duration_sec),
                        projectId=run.project_id,
                        generationMode="one_step",
                        referenceImageUrls=None,
                        enableSearch=False,
                    )
                    gen = await script_service.generate_script(
                        generate_req, model=run.decision_model_fallback
                    )

                # 写回 Script
                script = (await db.execute(select(Script).where(Script.id == run.script_id))).scalar_one()
                # 说明：
                # - 后续视频/关键帧生成会解析 script.content（文本），若文本里残留“多余段落”，会导致生成段数 > 预期。
                # - 因此这里用 segments_json 重新生成“规范脚本文本”，确保 content 与 segments 一致。
                def _build_normalized_script_content(segments: list) -> str:
                    blocks = []
                    for seg in segments:
                        seg_id = str(seg.get("id") or "")
                        ts_raw = seg.get("time_start")
                        if ts_raw is None:
                            ts_raw = seg.get("timeStart")
                        te_raw = seg.get("time_end")
                        if te_raw is None:
                            te_raw = seg.get("timeEnd")
                        try:
                            start = int(float(ts_raw or 0))
                        except Exception:
                            start = 0
                        try:
                            end = int(float(te_raw or 0))
                        except Exception:
                            end = start + int(run.segment_duration_sec or 4)
                        keyframe_desc = (seg.get("keyframe_desc") or seg.get("keyframeDesc") or "").strip()
                        video_desc = (seg.get("video_desc") or seg.get("videoDesc") or "").strip()
                        voice_desc = (seg.get("voice_desc") or seg.get("voiceDesc") or "").strip()
                        narration = (seg.get("narration") or seg.get("content") or "").strip()
                        blocks.append(
                            "\n".join(
                                [
                                    f"({start}-{end}s)",
                                    f"关键帧：{keyframe_desc}" if keyframe_desc else "关键帧：",
                                    f"视频：{video_desc}" if video_desc else "视频：",
                                    f"音色：{voice_desc}" if voice_desc else "音色：",
                                    f"口播文案：{narration}" if narration else "口播文案：",
                                ]
                            )
                        )
                    # 保留原文前缀（如果有），但以规范 blocks 为主体，确保可解析
                    return "\n\n".join(blocks).strip()

                script.style = gen.get("style") or script.style
                script.total_duration = gen.get("total_duration") or script.total_duration
                script.segment_duration = gen.get("segment_duration") or script.segment_duration
                # ⚠️ 关键：Script.segments 是 JSON 字段，必须写入可序列化结构（list[dict]）
                raw_segments = gen.get("segments") or []
                segments_json = []
                for seg in raw_segments:
                    if hasattr(seg, "model_dump"):
                        segments_json.append(seg.model_dump())
                    elif isinstance(seg, dict):
                        segments_json.append(seg)
                    else:
                        # 兜底：某些对象可能可被 dict() 转换
                        try:
                            segments_json.append(dict(seg))
                        except Exception:
                            # 最后兜底：强制转字符串，避免整条流水线崩溃
                            segments_json.append({"raw": str(seg)})
                script.segments = segments_json
                script.content = _build_normalized_script_content(segments_json) or (gen.get("content") or script.content)
                await db.commit()

                # 生成 StepSegment（为后续“按时间点重生成”做索引）
                try:
                    await db.execute(delete(StepSegment).where(StepSegment.run_id == run_id))
                    await db.commit()
                except Exception:
                    pass

                raw_segments = segments_json or []
                for idx, seg in enumerate(raw_segments):
                    # seg 可能是 pydantic 对象或 dict
                    if hasattr(seg, "model_dump"):
                        seg_dict = seg.model_dump()
                    else:
                        seg_dict = dict(seg)

                    # 注意：time_start=0.0 是合法值，不能用 `or` 否则会被错误当成 None
                    ts_raw = seg_dict.get("time_start")
                    if ts_raw is None:
                        ts_raw = seg_dict.get("timeStart")
                    te_raw = seg_dict.get("time_end")
                    if te_raw is None:
                        te_raw = seg_dict.get("timeEnd")
                    time_start = float(ts_raw) if ts_raw is not None else 0.0
                    time_end = float(te_raw) if te_raw is not None else float((idx + 1) * int(run.segment_duration_sec))

                    step_seg = StepSegment(
                        run_id=run_id,
                        segment_index=idx,
                        segment_id=str(seg_dict.get("id") or f"segment_{idx}"),
                        start_ms=int(time_start * 1000),
                        end_ms=int(time_end * 1000),
                        narration=seg_dict.get("narration"),
                        video_desc=seg_dict.get("video_desc") or seg_dict.get("videoDesc"),
                        voice_desc=seg_dict.get("voice_desc") or seg_dict.get("voiceDesc"),
                    )
                    db.add(step_seg)
                await db.commit()

                await svc._append_event(
                    run_id=run_id,
                    level="info",
                    event_type="step_done",
                    message="Step1-4: 已生成口播文案与视频描述",
                    data={"segment_count": len(segments_json or [])},
                )

                # Step4.5：智能分镜（可选）- 生成分镜首帧（用于 I2V）
                # 规则：
                # - video_mode=auto：若 enable_storyboard=True 则走 i2v，否则走 t2v
                # - video_mode=i2v：强制生成分镜并走 i2v（若失败则降级 t2v）
                # - video_mode=t2v：强制走纯文生视频（不生成关键帧）
                run = (await db.execute(select(StepRun).where(StepRun.id == run_id))).scalar_one()
                want_storyboard = bool(getattr(run, "enable_storyboard", True)) and (run.video_mode in ("auto", "i2v"))
                storyboard_ok = False
                if want_storyboard:
                    await svc._append_event(
                        run_id=run_id,
                        level="info",
                        event_type="storyboard_start",
                        message="开始生成智能分镜首帧（Seedream 组图）",
                    )
                    try:
                        kf_svc = KeyframeService(db)
                        await kf_svc.generate_storyboard_keyframes_seedream_group(
                            script_id=run.script_id or 0,
                            aspect_ratio=run.aspect_ratio or "16:9",
                        )
                        storyboard_ok = True
                        # 统计缺图段落（Seedream 组图可能小于 max_images）
                        kf_rows = (
                            await db.execute(
                                select(Keyframe)
                                .where(Keyframe.script_id == int(run.script_id or 0))
                            )
                        ).scalars().all()
                        missing_storyboard_segments = sorted(
                            [kf.segment_id for kf in kf_rows if getattr(kf, "status", None) == KeyframeStatus.FAILED]
                        )

                        await svc._append_event(
                            run_id=run_id,
                            level="info",
                            event_type="storyboard_done",
                            message="智能分镜首帧已生成（将用于图生视频；缺图段落会自动降级为T2V）",
                            data={
                                "total_segments": len(kf_rows),
                                "generated_images": len([kf for kf in kf_rows if kf.image_url]),
                                "missing_storyboard_segments": missing_storyboard_segments,
                            },
                        )
                    except Exception as e:
                        storyboard_ok = False
                        err_msg = f"{type(e).__name__}: {repr(e)}"
                        await svc._append_event(
                            run_id=run_id,
                            level="warning",
                            event_type="storyboard_failed",
                            message="智能分镜生成失败，将回退为纯文生视频",
                            data={"error": err_msg},
                        )

                # Step5-7：启动视频生成（内部会异步生成音频与视频，最终可导出拼接视频）
                run.current_step = 5
                await db.commit()

                await svc._append_event(
                    run_id=run_id,
                    level="info",
                    event_type="step_start",
                    message="Step5-7: 开始生成视频与配音，并准备拼接导出",
                )

                video_service = VideoService(db)
                video_mode = (run.video_mode or "auto").lower()
                # 按段混用策略（同一 run 内可混合）：
                # - 先生成/获取分镜首帧（storyboard_ok），得到 first_frame_by_segment_id
                # - 再按启发式规则挑选需要 I2V 的段落；其余走 T2V（纯文本）
                first_frame_by_segment_id = {}
                if storyboard_ok:
                    kfs = (
                        await db.execute(
                            select(Keyframe)
                            .where(Keyframe.script_id == int(run.script_id or 0))
                            .where(Keyframe.status == KeyframeStatus.COMPLETED)
                        )
                    ).scalars().all()
                    first_frame_by_segment_id = {kf.segment_id: kf.image_url for kf in kfs if kf.image_url}

                def _should_use_i2v(seg: StepSegment) -> bool:
                    # 强制模式
                    if video_mode == "i2v":
                        return True
                    if video_mode == "t2v":
                        return False
                    # auto：没有分镜就不走 i2v
                    if not storyboard_ok:
                        return False
                    # 启发式：遇到“文字/图表/UI/信息图/字幕”等，更适合纯文生（避免首帧限制画面）
                    text = (
                        (seg.video_desc or "")
                        + "\n"
                        + (seg.narration or "")
                        + "\n"
                        + (seg.voice_desc or "")
                    ).lower()
                    t2v_keywords = [
                        "字幕",
                        "文字",
                        "标题",
                        "图表",
                        "信息图",
                        "ppt",
                        "ui",
                        "界面",
                        "数据可视化",
                        "流程图",
                        "表格",
                    ]
                    if any(k in text for k in t2v_keywords):
                        return False
                    return True

                step_rows = (
                    await db.execute(select(StepSegment).where(StepSegment.run_id == run_id).order_by(StepSegment.segment_index.asc()))
                ).scalars().all()
                # 规则兜底：没有参考图（首帧 URL）的一律走 T2V
                candidate_i2v = {s.segment_id for s in step_rows if _should_use_i2v(s)}
                if first_frame_by_segment_id:
                    i2v_segment_ids = {sid for sid in candidate_i2v if first_frame_by_segment_id.get(sid)}
                else:
                    i2v_segment_ids = set()
                missing_storyboard_segments = sorted(
                    [s.segment_id for s in step_rows if storyboard_ok and not first_frame_by_segment_id.get(s.segment_id)]
                )
                await svc._append_event(
                    run_id=run_id,
                    level="info",
                    event_type="video_mode",
                    message=f"视频生成模式：混用（I2V {len(i2v_segment_ids)} 段 / T2V {max(0, len(step_rows)-len(i2v_segment_ids))} 段）",
                    data={
                        "video_mode": video_mode,
                        "i2v_segments": sorted(list(i2v_segment_ids)),
                        "missing_storyboard_segments": missing_storyboard_segments,
                    },
                )

                video_segments = await video_service.generate_videos_mixed_first_frame(
                    script_id=int(run.script_id or 0),
                    model=DOUBAO_SEEDANCE_1_5_PRO_MODEL_ID,
                    aspect_ratio=run.aspect_ratio or "16:9",
                    duration=float(run.segment_duration_sec),
                    first_frame_by_segment_id=first_frame_by_segment_id,
                    i2v_segment_ids=i2v_segment_ids,
                )

                # 绑定 StepSegment -> VideoSegment（按 segment_index 对齐）
                try:
                    seg_map = {vs.segment_index: vs for vs in video_segments}
                    step_rows = (
                        await db.execute(select(StepSegment).where(StepSegment.run_id == run_id))
                    ).scalars().all()
                    for s in step_rows:
                        vs = seg_map.get(s.segment_index)
                        if vs:
                            s.video_segment_id = vs.id
                    await db.commit()
                except Exception:
                    pass

                # 为了最小闭环：这里不阻塞等待全部生成完成；前端可通过现有 videos/script/{id} 轮询
                await svc._append_event(
                    run_id=run_id,
                    level="info",
                    event_type="videos_started",
                    message="视频生成任务已启动（后台生成中）",
                )

                # 等待视频生成完成后自动导出拼接（MVP：轮询）
                await svc._append_event(
                    run_id=run_id,
                    level="info",
                    event_type="wait_videos",
                    message="等待所有视频段生成完成…",
                )

                timeout_sec = 60 * 30
                poll_sec = 2
                start_ts = asyncio.get_event_loop().time()

                def _norm_status(x) -> str:
                    raw = x.value if hasattr(x, "value") else x
                    s = str(raw)
                    # 兼容：可能出现 "VideoStatus.COMPLETED" / "COMPLETED" / "completed"
                    s = s.split(".")[-1].strip().lower()
                    return s

                while True:
                    if asyncio.get_event_loop().time() - start_ts > timeout_sec:
                        raise Exception("等待视频生成超时")
                    await asyncio.sleep(poll_sec)
                    vs_rows = (
                        await db.execute(select(VideoSegment).where(VideoSegment.script_id == run.script_id))
                    ).scalars().all()
                    if not vs_rows:
                        continue
                    if any(_norm_status(v.status) == "failed" for v in vs_rows):
                        raise Exception("存在视频段生成失败")
                    if all(_norm_status(v.status) == "completed" for v in vs_rows):
                        break

                await svc._append_event(
                    run_id=run_id,
                    level="info",
                    event_type="videos_done",
                    message="所有视频段已完成，开始拼接导出…",
                )

                run.current_step = 7
                await db.commit()

                export_result = await video_service.export_videos(
                    script_id=run.script_id,
                    export_type="concatenated",
                )
                final_url = str(export_result.get("download_url") or "")

                run.final_video_url = final_url
                run.status = StepRunStatus.COMPLETED
                await db.commit()

                await svc._append_event(
                    run_id=run_id,
                    level="info",
                    event_type="run_completed",
                    message="一步生成完成",
                    data={"final_video_url": final_url},
                )

            except Exception as e:
                logger.error("StepGenerate pipeline failed", run_id=run_id, error=str(e), exc_info=True)
                try:
                    result = await db.execute(select(StepRun).where(StepRun.id == run_id))
                    run = result.scalar_one_or_none()
                    if run:
                        run.status = StepRunStatus.FAILED
                        run.error_message = str(e)
                        await db.commit()
                except Exception:
                    pass
                try:
                    await svc._append_event(
                        run_id=run_id,
                        level="error",
                        event_type="run_failed",
                        message="一步生成失败",
                        data={"error": str(e)},
                    )
                except Exception:
                    pass

    async def start_regenerate_video_only(self, *, run_id: int, time_sec: float) -> None:
        """完成后对话式干预：按时间点定位段落，仅重生成视频画面并重新导出拼接。"""
        asyncio.create_task(self._regenerate_video_only(run_id=run_id, time_sec=time_sec))

    async def _regenerate_video_only(self, *, run_id: int, time_sec: float) -> None:
        async with async_session_maker() as db:
            svc = StepGenerateService(db)
            try:
                run = (await db.execute(select(StepRun).where(StepRun.id == run_id))).scalar_one_or_none()
                if not run:
                    return

                await svc._append_event(
                    run_id=run_id,
                    level="info",
                    event_type="regen_start",
                    message="开始按时间点重生成视频（video_only）",
                    data={"time_sec": time_sec},
                )

                # 允许：完成后干预；或失败后补救（例如 run 卡在 wait_videos 但视频段已完成）
                if run.status not in (StepRunStatus.COMPLETED, StepRunStatus.FAILED):
                    await svc._append_event(
                        run_id=run_id,
                        level="warning",
                        event_type="regen_rejected",
                        message="当前任务进行中，暂不支持干预（可在失败或完成后使用）",
                    )
                    return

                t_ms = int(max(0.0, float(time_sec)) * 1000)
                seg = (
                    await db.execute(
                        select(StepSegment)
                        .where(StepSegment.run_id == run_id)
                        .where(StepSegment.start_ms.isnot(None))
                        .where(StepSegment.end_ms.isnot(None))
                    )
                ).scalars().all()

                target: Optional[StepSegment] = None
                for s in seg:
                    if s.start_ms is None or s.end_ms is None:
                        continue
                    if s.start_ms <= t_ms < s.end_ms:
                        target = s
                        break

                if not target or not target.video_segment_id:
                    await svc._append_event(
                        run_id=run_id,
                        level="warning",
                        event_type="regen_not_found",
                        message="未能定位到对应时间段的视频片段",
                        data={"time_sec": time_sec},
                    )
                    return

                video_service = VideoService(db)
                await svc._append_event(
                    run_id=run_id,
                    level="info",
                    event_type="regen_target",
                    message="已定位到目标片段，开始重生成该段视频",
                    data={"segment_index": target.segment_index, "video_segment_id": target.video_segment_id},
                )

                await video_service.regenerate_video_segment(
                    video_segment_id=int(target.video_segment_id),
                    model=None,
                )

                # 等待该段完成
                timeout_sec = 60 * 20
                poll_sec = 2
                start_ts = asyncio.get_event_loop().time()
                while True:
                    if asyncio.get_event_loop().time() - start_ts > timeout_sec:
                        raise Exception("等待重生成超时")
                    await asyncio.sleep(poll_sec)
                    vs = (
                        await db.execute(select(VideoSegment).where(VideoSegment.id == int(target.video_segment_id)))
                    ).scalar_one_or_none()
                    if not vs:
                        continue
                    if _norm_status(vs.status) == "failed":
                        raise Exception(vs.error_message or "重生成失败")
                    if _norm_status(vs.status) == "completed":
                        break

                await svc._append_event(
                    run_id=run_id,
                    level="info",
                    event_type="regen_done",
                    message="目标片段重生成完成，开始重新拼接导出…",
                )

                export_result = await video_service.export_videos(
                    script_id=run.script_id,
                    export_type="concatenated",
                )
                final_url = str(export_result.get("download_url") or "")

                run.final_video_url = final_url
                await db.commit()

                await svc._append_event(
                    run_id=run_id,
                    level="info",
                    event_type="regen_export_done",
                    message="重生成已完成并重新导出拼接成片",
                    data={"final_video_url": final_url},
                )

            except Exception as e:
                logger.error("Regenerate video_only failed", run_id=run_id, error=str(e), exc_info=True)
                try:
                    await svc._append_event(
                        run_id=run_id,
                        level="error",
                        event_type="regen_failed",
                        message="重生成失败",
                        data={"error": str(e)},
                    )
                except Exception:
                    pass

    @staticmethod
    def parse_regenerate_time_seconds(message: str) -> Optional[float]:
        """
        解析“第10s视频重新生成 / 10秒重新生成 / 10s重做”等简单指令。
        返回秒数（float）或 None。
        """
        text = (message or "").strip()
        m = re.search(r"第?\s*(\d+(?:\.\d+)?)\s*(?:s|秒)", text, re.IGNORECASE)
        if not m:
            return None
        try:
            return float(m.group(1))
        except Exception:
            return None

