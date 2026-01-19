"""
关键帧生成服务
处理关键帧的生成、更新、上传等操作
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
import structlog

from src.models.tables.keyframe import Keyframe, KeyframeStatus
from src.models.tables.script import Script
from src.models.database import async_session_maker
from src.services.image_generation_service import image_generation_service
from src.services.volc_ark_image_service import volc_ark_image_service
from src.services.oss_service import oss_service
from src.services.upload_limiter import upload_limiter
from src.utils.script_parser import (
    parse_script,
    extract_prompt_for_segment,
    ScriptSegment
)
from src.utils.exceptions import NotFoundError, ValidationError

logger = structlog.get_logger(__name__)

# 设置为2小时，避免误杀排队任务，同时保留清理长期异常任务的能力
STALE_KEYFRAME_TIMEOUT = timedelta(hours=2)


class KeyframeService:
    """关键帧生成服务类."""

    def __init__(self, db: AsyncSession):
        """初始化关键帧服务.

        Args:
            db: 数据库会话
        """
        self.db = db

    async def generate_keyframes(
        self,
        script_id: int,
        model: str,
        aspect_ratio: str,
        quality: Optional[str],
        only_first_frame: bool = False,
        reference_image_urls: Optional[List[str]] = None
    ) -> List[Keyframe]:
        """批量生成关键帧（异步后台任务）.

        Args:
            script_id: 脚本ID
            model: 图片生成模型
            aspect_ratio: 图像比例
            quality: 清晰度
            only_first_frame: 是否只生成第一段关键帧（segment_0）用于确认
            reference_image_urls: 参考图URL列表，用于第一段关键帧（segment_0）生成

        Returns:
            关键帧列表

        Raises:
            NotFoundError: 脚本不存在
            ValidationError: 参数验证失败
        """
        # 清除之前的取消标志（开始新任务）
        from src.utils.redis_client import TaskCancellationManager
        try:
            await TaskCancellationManager.clear_cancellation_flag(script_id)
            logger.info('Cleared cancellation flag for new keyframe generation', script_id=script_id)
        except Exception as e:
            logger.warning('Failed to clear cancellation flag', error=str(e))
        
        # 获取脚本
        result = await self.db.execute(
            select(Script).where(Script.id == script_id)
        )
        script = result.scalar_one_or_none()

        if not script:
            raise NotFoundError(f'脚本不存在: {script_id}')

        if not script.content:
            raise ValidationError('脚本内容为空')

        # 图片模型白名单（已移除的旧模型将被拒绝）
        supported_models = {
            'nano-banana-pro',
            'sora-image',
            'doubao-seedream-4-5-251128',
            'jimeng_t2i_v40',
        }
        if model not in supported_models:
            raise ValidationError(f'不支持的图片模型: {model}')

        # 解析脚本段落（全局不再包含第0帧）
        segments = parse_script(script.content)

        if not segments:
            raise ValidationError('脚本中没有找到有效段落')

        # 删除该脚本的所有旧关键帧
        await self.db.execute(
            delete(Keyframe).where(Keyframe.script_id == script_id)
        )
        await self.db.commit()
        
        logger.info(
            'Old keyframes deleted',
            script_id=script_id
        )

        # 创建关键帧记录（状态为 generating/pending）
        # 注意：创建顺序非常重要，必须按照 segment_0 -> segment_1 -> ... 创建，
        # 以确保串行生成时“上一张关键帧”作为参考图的顺序正确。
        keyframes: List[Keyframe] = []

        if not segments:
            raise ValidationError('脚本中没有有效的段落')

        # 按顺序创建每段的关键帧：segment_0 先 generating，其余 pending
        for idx, segment in enumerate(segments):
            keyframe = Keyframe(
                script_id=script_id,
                segment_id=segment.segment_id,
                # 统一使用关键帧描述作为提示词（若缺失则回退到解析出的content）
                prompt=segment.keyframe_desc or segment.content,
                status=KeyframeStatus.GENERATING if idx == 0 else KeyframeStatus.PENDING,
            )
            self.db.add(keyframe)
            keyframes.append(keyframe)

        await self.db.commit()

        # 保存关键帧ID列表，用于后台任务（顺序即 segment_0 -> segment_1 -> ...）
        keyframe_ids = [kf.id for kf in keyframes]

        # 分步生成仍保留“首帧确认”：
        # - only_first_frame=True：先只生成 segment_0（第一个关键帧）供确认；
        # - only_first_frame=False：一次性生成全部 segment_0..N。
        ids_to_generate = keyframe_ids if not only_first_frame else keyframe_ids[:1]
        task = asyncio.create_task(
            self._generate_keyframes_background(
                ids_to_generate,
                segments,
                model,
                aspect_ratio,
                quality,
                reference_image_urls=reference_image_urls,
            )
        )
        # 添加错误回调，确保任务异常能被记录
        task.add_done_callback(
            lambda t: logger.error(
                'Background generation task failed',
                error=str(t.exception()) if t.exception() else 'Unknown error',
                script_id=script_id,
                total_keyframes=len(keyframes),
                exc_info=True
            ) if t.exception() else logger.info(
                'Background generation task completed successfully',
                script_id=script_id,
                total_keyframes=len(keyframes)
            )
        )
        logger.info(
            'Keyframes generation task created',
            script_id=script_id,
            total_keyframes=len(keyframes),
            only_first_frame=bool(only_first_frame),
            scheduled_count=len(ids_to_generate),
        )

        return keyframes

    async def generate_storyboard_keyframes_seedream_group(
        self,
        *,
        script_id: int,
        aspect_ratio: str,
        reference_image_urls: Optional[List[str]] = None,
        model: str = "doubao-seedream-4-5-251128",
    ) -> List[Keyframe]:
        """智能分镜：使用 Seedream 4.5 文生组图，一次生成 N 张分镜首帧，并写入 Keyframe 表（COMPLETED）。

        目标：
        - “不同故事情节的镜头”：用脚本每段的 keyframe_desc/video_desc 作为分镜条目
        - “多图一致性”：使用 Seedream 的 sequential_image_generation=auto 一次性出图
        - “作为首帧生成视频”：后续 VideoService 会以 keyframe.image_url 作为 first_frame_url

        注意：
        - 组图 API 仅能输入一个 prompt，因此我们把 N 段分镜要求拼成一个“强格式 prompt”，让模型按序生成。
        - 返回图片张数可能小于 max_images（模型自判）；这里若不足 N，会用“最后一张”补齐以保证每段都有首帧（MVP 策略）。
        """
        # 获取脚本
        result = await self.db.execute(select(Script).where(Script.id == script_id))
        script = result.scalar_one_or_none()
        if not script or not script.content:
            raise ValidationError(f"脚本不存在或内容为空: {script_id}")

        segments = parse_script(script.content)
        if not segments:
            raise ValidationError("脚本中没有找到有效段落")

        # 删除旧关键帧
        await self.db.execute(delete(Keyframe).where(Keyframe.script_id == script_id))
        await self.db.commit()

        # Seedream 推荐尺寸映射（2K）
        size_map = {
            "16:9": "2560x1440",
            "9:16": "1440x2560",
            "1:1": "2048x2048",
        }
        size = size_map.get(aspect_ratio, "2560x1440")

        # 拼接“分镜 prompt”（强格式）
        lines = []
        for idx, seg in enumerate(segments):
            desc = (seg.keyframe_desc or seg.video_desc or seg.content or "").strip()
            desc = desc.replace("\n", " ").strip()
            lines.append(f"{idx+1}. {desc}")

        storyboard_prompt = (
            "你是专业分镜师。请根据下面的分镜列表生成一组连贯一致的分镜图（同一主角/同一风格/同一光影与色调），"
            "每张图对应一条分镜，按顺序输出。\n"
            "要求：写实电影感、构图明确、主体清晰、避免文字水印、不要生成多余画面。\n"
            f"分镜列表（共 {len(lines)} 张）：\n" + "\n".join(lines)
        )

        urls = await volc_ark_image_service.generate_images_group(
            model=model,
            prompt=storyboard_prompt,
            size=size,
            max_images=len(lines),
            reference_image_urls=reference_image_urls,
            watermark=False,
            # 组图较慢：按“每张图 10 分钟”给足超时（用户要求）
            timeout_sec=float(600 * max(1, len(lines))),
        )

        if not urls:
            raise ValidationError("Seedream 组图生成失败：未返回图片 URL")

        # 写入 keyframes（直接 COMPLETED）
        keyframes: List[Keyframe] = []
        for idx, seg in enumerate(segments):
            img_url = urls[idx] if idx < len(urls) else None
            kf = Keyframe(
                script_id=script_id,
                segment_id=seg.segment_id,
                prompt=seg.keyframe_desc or seg.content,
                image_url=img_url,
                status=KeyframeStatus.COMPLETED if img_url else KeyframeStatus.FAILED,
                error_message=None if img_url else "Seedream 组图未返回该序号图片，已降级为 T2V",
            )
            self.db.add(kf)
            keyframes.append(kf)

        await self.db.commit()
        return keyframes

    async def _generate_keyframes_background(
        self,
        keyframe_ids: List[int],
        segments: List[ScriptSegment],
        model: str,
        aspect_ratio: str,
        quality: Optional[str],
        start_from_index: int = 0,
        reference_image_urls: Optional[List[str]] = None
    ) -> None:
        """后台任务：串行生成关键帧图片，每帧参考前5张（最多）提高一致性.

        Args:
            keyframe_ids: 关键帧ID列表
            segments: 脚本段落列表
            model: 图片生成模型
            aspect_ratio: 图像比例
            quality: 清晰度
            start_from_index: 从哪个索引开始生成(默认0,从头开始)
            reference_image_urls: 参考图URL列表，用于第一段关键帧（segment_0）生成
            
        Note:
            参考图逻辑：每一帧参考前 N 张已生成关键帧（不足 N 张则全部使用）
            - segment_0：可使用用户上传的参考图（reference_image_urls）
            - segment_1..：参考最近 N 张已生成关键帧（segment_0 起）
        """
        # 获取 script_id（从第一个关键帧获取）
        script_id = None
        if keyframe_ids:
            try:
                async with async_session_maker() as db:
                    result = await db.execute(
                        select(Keyframe).where(Keyframe.id == keyframe_ids[0])
                    )
                    first_kf = result.scalar_one_or_none()
                    if first_kf:
                        script_id = first_kf.script_id
            except Exception as e:
                logger.warning('Failed to get script_id from keyframe', error=str(e))
        
        logger.info(
            'Background generation task started',
            keyframe_ids=keyframe_ids,
            script_id=script_id,
            model=model,
            aspect_ratio=aspect_ratio,
            quality=quality,
            start_from_index=start_from_index
        )
        try:
            # 创建段落映射
            segment_map = {seg.segment_id: seg for seg in segments}

            # 维护已生成关键帧的URL历史记录
            generated_urls_history: List[str] = []
            
            # 根据模型确定最大参考图数量
            # 只有 nano-banana-pro 支持14张，其他模型保持5张
            max_references = 14 if model == "nano-banana-pro" else 5
            
            # 如果从中间开始，需要先加载之前已生成的关键帧作为参考
            if start_from_index > 0:
                # 计算需要加载的起始索引
                load_start_index = max(0, start_from_index - max_references)
                load_keyframe_ids = keyframe_ids[load_start_index:start_from_index]
                
                async with async_session_maker() as db:
                    result = await db.execute(
                        select(Keyframe).where(Keyframe.id.in_(load_keyframe_ids))
                    )
                    previous_keyframes = list(result.scalars().all())
                    
                    # 按照ID顺序排序，确保顺序正确
                    previous_keyframes.sort(key=lambda kf: load_keyframe_ids.index(kf.id))
                    
                    # 提取已生成的图片URL
                    for kf in previous_keyframes:
                        if kf.image_url:
                            generated_urls_history.append(kf.image_url)
                    
                    logger.info(
                        'Loaded previous keyframes for reference',
                        start_from_index=start_from_index,
                        loaded_count=len(generated_urls_history),
                        history=generated_urls_history
                    )

            # 导入Redis取消管理器
            from src.utils.redis_client import TaskCancellationManager
            
            # 串行生成关键帧，每一帧参考前N张（最多）
            for i, keyframe_id in enumerate(keyframe_ids):
                # 跳过start_from_index之前的帧
                if i < start_from_index:
                    continue
                
                # 【检查点1】检查Redis取消标志（快速检查）
                if script_id:
                    try:
                        is_cancelled = await TaskCancellationManager.check_cancellation_flag(script_id)
                        if is_cancelled:
                            logger.info(
                                'Task cancelled via Redis flag, stopping keyframe generation',
                                script_id=script_id,
                                current_index=i + 1,
                                total=len(keyframe_ids)
                            )
                            break  # 停止整个生成循环
                    except Exception as e:
                        logger.warning('Failed to check Redis cancellation flag', error=str(e))
                    
                    # 更新任务心跳（表示任务还在运行）
                    try:
                        await TaskCancellationManager.set_task_heartbeat(script_id, 'keyframe')
                    except Exception as e:
                        logger.warning('Failed to set task heartbeat', error=str(e))
                
                # 【检查点2】更新当前关键帧状态为GENERATING（在更新前检查数据库状态）
                try:
                    async with async_session_maker() as db:
                        result = await db.execute(
                            select(Keyframe).where(Keyframe.id == keyframe_id)
                        )
                        current_kf = result.scalar_one_or_none()
                        
                        if not current_kf:
                            logger.warning('Keyframe not found', keyframe_id=keyframe_id)
                            continue
                        
                        # 检查是否已被用户取消（状态为 failed 且错误信息包含"用户取消"）
                        if current_kf.status == KeyframeStatus.FAILED:
                            if current_kf.error_message and '用户取消' in current_kf.error_message:
                                logger.info(
                                    'Keyframe generation cancelled by user (DB status), skipping',
                                    keyframe_id=keyframe_id,
                                    current_index=i + 1,
                                    total=len(keyframe_ids)
                                )
                                continue  # 跳过这个关键帧，继续下一个
                        
                        # 如果没有被取消，更新状态为 GENERATING
                        current_kf.status = KeyframeStatus.GENERATING
                        await db.commit()
                except Exception as e:
                    logger.error(
                        'Failed to update keyframe status to GENERATING',
                        keyframe_id=keyframe_id,
                        error=str(e)
                    )
                
                # 构建参考图列表：前N张已生成的关键帧（如果不足N张则全部使用）
                reference_urls: List[str] = []
                
                # 对于第一段关键帧（segment_0），使用用户上传的参考图（如果有）
                if i == 0 and reference_image_urls:
                    reference_urls = reference_image_urls[:max_references]
                    logger.info(
                        'Using user-provided reference images for segment_0',
                        keyframe_id=keyframe_id,
                        reference_count=len(reference_urls)
                    )
                # 对于其他帧，使用之前生成的关键帧作为参考
                elif i > 0 and generated_urls_history:
                    # 取最近N张作为参考（如果不足N张则全部使用）
                    reference_urls = generated_urls_history[-max_references:]
                    
                logger.info(
                    'Generating keyframe sequentially',
                    current=i + 1,
                    total=len(keyframe_ids),
                    keyframe_id=keyframe_id,
                    reference_count=len(reference_urls),
                    max_references=max_references
                )
                
                # 生成当前关键帧，传入参考图列表
                result_url = await self._generate_single_keyframe_image_with_session(
                    keyframe_id, segment_map, model, aspect_ratio, quality, 
                    reference_urls if reference_urls else None
                )
                
                # 如果生成成功，将URL加入历史记录供后续帧使用
                if result_url:
                    generated_urls_history.append(result_url)
                    # 保持历史记录最多N张，移除最旧的
                    if len(generated_urls_history) > max_references:
                        generated_urls_history.pop(0)
                    
                    logger.info(
                        'Keyframe generated, added to reference history',
                        keyframe_id=keyframe_id,
                        result_url=result_url,
                        history_size=len(generated_urls_history)
                    )
                else:
                    # 任意一帧失败：停止生成后续帧（按需求：避免出现“中间失败但后面成功”的不一致）
                    logger.error(
                        'Keyframe generation failed, stopping all subsequent generation',
                        keyframe_id=keyframe_id,
                        failed_index=i,
                        total=len(keyframe_ids),
                    )

                    # 将所有后续帧标记为失败
                    async with async_session_maker() as db:
                        for remaining_id in keyframe_ids[i + 1:]:
                            try:
                                result = await db.execute(
                                    select(Keyframe).where(Keyframe.id == remaining_id)
                                )
                                remaining_kf = result.scalar_one_or_none()
                                if not remaining_kf:
                                    continue
                                if remaining_kf.status == KeyframeStatus.PENDING:
                                    remaining_kf.status = KeyframeStatus.FAILED
                                    remaining_kf.error_message = (
                                        '前序关键帧生成失败，已取消后续生成'
                                    )
                            except Exception as e:
                                logger.error(
                                    'Failed to mark remaining keyframe as failed',
                                    error=str(e),
                                    remaining_id=remaining_id,
                                )
                        await db.commit()

                    break  # 停止生成循环
                    
        except Exception as e:
            logger.error(
                'Error in background keyframe generation',
                error=str(e),
                exc_info=True
            )

    async def _upload_keyframe_to_oss_background(self, keyframe_id: int, image_url: str) -> None:
        """后台任务：下载图片并上传到OSS，然后更新数据库."""
        # 为后台任务创建独立的数据库会话
        async with async_session_maker() as db:
            try:
                # 1. 下载图片（带重试机制）
                import httpx
                from io import BytesIO
                
                max_retries = 2  # 每个模型最多尝试2次（失败后重试1次）
                image_data = None
                last_error = None
                
                async with httpx.AsyncClient(timeout=30.0) as client:
                    for attempt in range(max_retries):
                        try:
                            image_response = await client.get(image_url)
                            image_response.raise_for_status()
                            image_data = image_response.content
                            break
                        except Exception as e:
                            last_error = e
                            retry_count = attempt + 1
                            if retry_count < max_retries:
                                wait_time = 2 * retry_count
                                logger.warning(
                                    "Background download failed, retrying",
                                    attempt=retry_count,
                                    max_retries=max_retries,
                                    wait_time=wait_time,
                                    error=str(e),
                                    keyframe_id=keyframe_id
                                )
                                await asyncio.sleep(wait_time)
                            else:
                                logger.error(
                                    "Background download failed after retries",
                                    error=str(e),
                                    keyframe_id=keyframe_id
                                )

                if image_data is None:
                    raise Exception(f"无法下载生成的图片 (重试{max_retries}次后失败): {str(last_error)}")

                # 2. 上传到OSS
                filename = f'keyframe_{keyframe_id}.jpg'
                file_stream = BytesIO(image_data)
                
                # 使用 upload_file 而不是 upload_from_url，因为我们已经下载了数据
                upload_result = oss_service.upload_file(
                    file_data=file_stream,
                    filename=filename,
                    category='keyframes',
                    content_type='image/jpeg'
                )
                
                # 3. 更新数据库
                result = await db.execute(select(Keyframe).where(Keyframe.id == keyframe_id))
                keyframe = result.scalar_one_or_none()
                if keyframe:
                    keyframe.image_url = upload_result['url']
                    await db.commit()
                    logger.info(
                        "Keyframe OSS upload completed and DB updated", 
                        keyframe_id=keyframe_id, 
                        oss_url=upload_result['url']
                    )
                    
            except Exception as e:
                logger.error(
                    "Background OSS upload failed", 
                    keyframe_id=keyframe_id, 
                    error=str(e),
                    exc_info=True
                )

    def _get_fallback_models(self, model: str) -> List[str]:
        """获取模型降级列表（过滤掉不可用的 GRSAI 模型）.
        
        Args:
            model: 当前模型
            
        Returns:
            模型列表（包含当前模型和降级模型，已过滤不可用模型）
        """
        from src.services.model_status_service import model_status_service
        
        # 关键帧生成模型降级链: nano-banana-pro -> sora-image -> jimeng_t2i_v40
        fallback_chain = {
            'nano-banana-pro': [
                'nano-banana-pro',
                'sora-image',
                'doubao-seedream-4-5-251128',
                'jimeng_t2i_v40',
            ],
            'sora-image': ['sora-image', 'jimeng_t2i_v40'],
            'doubao-seedream-4-5-251128': ['doubao-seedream-4-5-251128', 'jimeng_t2i_v40'],
            'jimeng_t2i_v40': ['jimeng_t2i_v40'],
        }
        
        models = fallback_chain.get(model, [model])
        
        # 过滤掉不可用的 GRSAI 模型
        filtered_models = []
        for m in models:
            # 如果是 GRSAI 模型，检查可用性
            if m in model_status_service.grsai_models.get("image", []):
                if model_status_service.is_model_available(m):
                    filtered_models.append(m)
                else:
                    logger.info(
                        "Skipping unavailable GRSAI model in fallback chain",
                        model=m,
                        original_model=model
                    )
            else:
                # 非 GRSAI 模型（如 jimeng），直接包含
                filtered_models.append(m)
        
        # 如果所有模型都被过滤掉了，至少保留原始模型（让它尝试并记录详细错误）
        if not filtered_models:
            logger.warning(
                "All models filtered out, keeping original model",
                model=model
            )
            filtered_models = [model]
        
        return filtered_models

    async def _generate_single_keyframe_image_with_session(
        self,
        keyframe_id: int,
        segment_map: dict,
        model: str,
        aspect_ratio: str,
        quality: Optional[str],
        reference_image_urls: Optional[List[str]] = None
    ) -> Optional[str]:
        """生成单个关键帧图片（使用独立的数据库会话）.

        Args:
            keyframe_id: 关键帧ID
            segment_map: 段落映射
            model: 图片生成模型
            aspect_ratio: 图像比例
            quality: 清晰度
            reference_image_urls: 参考图片URL列表（可选，最多包含前5张关键帧）
            
        Returns:
            生成的图片URL，失败时返回None
        """
        # 为每个任务创建独立的数据库会话
        async with async_session_maker() as db:
            try:
                # 查询关键帧对象
                result = await db.execute(
                    select(Keyframe).where(Keyframe.id == keyframe_id)
                )
                keyframe = result.scalar_one_or_none()
                
                if not keyframe:
                    logger.error(
                        'Keyframe not found',
                        keyframe_id=keyframe_id
                    )
                    return None

                # 判断是否为旧格式的第一帧（兼容旧数据）
                is_old_first_frame = keyframe.segment_id.endswith('_first_frame')

                # 生成提示词
                # 注意：所有关键帧的prompt在创建时就已经正确设置了
                # segment_X_first_frame -> 使用第0帧的内容
                # segment_0 -> 使用segment_0的内容
                # 因此这里直接使用已保存的prompt即可，不需要重新提取
                
                if keyframe.prompt:
                    # 如果关键帧已有prompt，直接使用（这是最常见的情况）
                    prompt = keyframe.prompt
                elif is_old_first_frame:
                    # 兼容旧数据：如果关键帧没有prompt，尝试从segment提取
                    base_segment_id = keyframe.segment_id.replace('_first_frame', '')
                    segment = segment_map.get(base_segment_id)
                    if segment:
                        prompt = extract_prompt_for_segment(segment, is_old_first_frame)
                    else:
                        prompt = ''
                        logger.warning(
                            'No prompt found for old format keyframe',
                            keyframe_id=keyframe_id,
                            segment_id=keyframe.segment_id
                        )
                else:
                    # 兜底：使用空prompt（这种情况不应该发生）
                    prompt = ''
                    logger.warning(
                        'No prompt found for keyframe',
                        keyframe_id=keyframe_id,
                        segment_id=keyframe.segment_id
                    )

                # 调用图片生成API（传入参考图URL列表以提高一致性）
                # 使用模型降级机制 + 重试机制
                fallback_models = self._get_fallback_models(model)
                image_url = None
                last_error = None
                used_model = model
                max_retries = 2  # 每个模型最多尝试2次（失败后重试1次）

                # 记录参考图（仅记录数量与前2个URL前缀，便于排查“是否真的用了参考图/用了哪个模型”）
                try:
                    ref_preview = []
                    if reference_image_urls:
                        for u in reference_image_urls[:2]:
                            ref_preview.append(str(u)[:80])
                    logger.info(
                        'Keyframe reference images prepared',
                        keyframe_id=keyframe_id,
                        segment_id=keyframe.segment_id,
                        reference_count=len(reference_image_urls) if reference_image_urls else 0,
                        reference_preview=ref_preview,
                    )
                except Exception:
                    pass
                
                for current_model in fallback_models:
                    model_succeeded = False
                    
                    for attempt in range(max_retries):
                        try:
                            retry_count = attempt + 1
                            logger.info(
                                'Calling image generation API',
                                keyframe_id=keyframe_id,
                                segment_id=keyframe.segment_id,
                                model=current_model,
                                attempt=retry_count,
                                max_retries=max_retries,
                                reference_count=len(reference_image_urls) if reference_image_urls else 0,
                                prompt_preview=prompt[:100] if prompt else ''
                            )
                            
                            result = await image_generation_service.generate_image(
                                prompt=prompt,
                                model=current_model,
                                aspect_ratio=aspect_ratio,
                                quality=quality,
                                reference_image_urls=reference_image_urls  # 传入参考图URL列表
                            )
                            image_url = result.get('url')
                            
                            if image_url:
                                used_model = current_model
                                if current_model != model:
                                    logger.info(
                                        'Model fallback successful',
                                        keyframe_id=keyframe_id,
                                        original_model=model,
                                        used_model=current_model
                                    )
                                model_succeeded = True
                                break  # 成功，跳出重试循环
                                
                        except Exception as e:
                            error_msg = str(e).lower()
                            last_error = e

                            # 检查是否是模型维护错误（立即切换模型，不重试）
                            if 'maintenance' in error_msg or 'model maintenance' in error_msg:
                                logger.warning(
                                    'Model under maintenance, trying fallback model',
                                    keyframe_id=keyframe_id,
                                    failed_model=current_model,
                                    error=str(e)
                                )
                                # 模型维护错误，不重试当前模型，直接尝试下一个模型
                                break
                            else:
                                # 其他错误（包括内容审查错误）重试当前模型
                                if retry_count < max_retries:
                                    # 内容审查/安全拦截：静默重试，不向前端写“正在重试”提示
                                    is_moderation = any(
                                        k in error_msg
                                        for k in [
                                            'safety',
                                            'moderation',
                                            'blocked',
                                            'prohibited',
                                            '内容被审查',
                                            '审查',
                                            '拦截',
                                            'gemini',
                                        ]
                                    )
                                    logger.warning(
                                        'Image generation failed, retrying',
                                        keyframe_id=keyframe_id,
                                        model=current_model,
                                        attempt=retry_count,
                                        max_retries=max_retries,
                                        error=str(e)
                                    )
                                    # 更新重试状态
                                    if not is_moderation:
                                        try:
                                            result = await db.execute(
                                                select(Keyframe).where(Keyframe.id == keyframe_id)
                                            )
                                            kf_for_update = result.scalar_one_or_none()
                                            if kf_for_update:
                                                kf_for_update.error_message = (
                                                    f"生成失败，正在重试 ({retry_count}/{max_retries})..."
                                                )
                                                await db.commit()
                                        except Exception as db_e:
                                            logger.error('Failed to update retry status', error=str(db_e))
                                    
                                    await asyncio.sleep(2 ** retry_count)  # 指数退避
                                else:
                                    logger.error(
                                        'Image generation failed after retries, trying next model',
                                        keyframe_id=keyframe_id,
                                        model=current_model,
                                        error=str(e)
                                    )
                                    # 重试失败，跳出重试循环，尝试下一个模型
                                    break
                    
                    if model_succeeded:
                        break  # 成功，跳出模型降级循环

                if not image_url:
                    raise Exception(f'图片生成失败（所有模型均不可用，每个模型已尝试{max_retries}次）: {str(last_error)}')

                # 启动后台任务上传到OSS（不等待，使用并发限制）
                # 这样可以立即返回第三方URL供下一帧参考，并让前端尽快显示
                asyncio.create_task(
                    upload_limiter.upload_image(
                        self._upload_keyframe_to_oss_background,
                        keyframe_id,
                        image_url
                    )
                )

                # 重新查询关键帧以更新状态（使用当前会话）
                result = await db.execute(
                    select(Keyframe).where(Keyframe.id == keyframe_id)
                )
                keyframe_to_update = result.scalar_one_or_none()
                
                if keyframe_to_update:
                    # 先保存第三方URL，状态设为COMPLETED
                    keyframe_to_update.image_url = image_url
                    keyframe_to_update.prompt = prompt
                    keyframe_to_update.status = KeyframeStatus.COMPLETED
                    keyframe_to_update.error_message = None
                    await db.commit()

                    logger.info(
                        'Keyframe image generated successfully (using 3rd party URL)',
                        keyframe_id=keyframe_id,
                        segment_id=keyframe_to_update.segment_id,
                        image_url=image_url,
                        used_model=used_model,
                        reference_count=len(reference_image_urls) if reference_image_urls else 0,
                    )
                    
                    # 返回生成的图片URL供下一帧参考
                    return image_url
                else:
                    logger.error(
                        'Keyframe not found when updating',
                        keyframe_id=keyframe_id
                    )
                    return None

            except Exception as e:
                # 失败即停止，更新状态为failed
                logger.error(
                    'Failed to generate keyframe image',
                    keyframe_id=keyframe_id,
                    error=str(e),
                    exc_info=True
                )

                try:
                    # 重新查询关键帧以更新状态
                    result = await db.execute(
                        select(Keyframe).where(Keyframe.id == keyframe_id)
                    )
                    keyframe_to_update = result.scalar_one_or_none()
                    
                    if keyframe_to_update:
                        keyframe_to_update.status = KeyframeStatus.FAILED
                        keyframe_to_update.error_message = str(e)
                        await db.commit()
                except Exception as commit_error:
                    logger.error(
                        'Failed to update keyframe status',
                        keyframe_id=keyframe_id,
                        error=str(commit_error),
                        exc_info=True
                    )
                
                return None

    async def regenerate_keyframe(
        self,
        keyframe_id: int,
        model: Optional[str] = None,
        aspect_ratio: Optional[str] = None,
        quality: Optional[str] = None
    ) -> Keyframe:
        """重新生成单个关键帧.

        Args:
            keyframe_id: 关键帧ID
            model: 图片生成模型（可选，使用项目默认配置）
            aspect_ratio: 图像比例（可选）
            quality: 清晰度（可选）

        Returns:
            更新后的关键帧

        Raises:
            NotFoundError: 关键帧不存在
        """
        result = await self.db.execute(
            select(Keyframe).where(Keyframe.id == keyframe_id)
        )
        keyframe = result.scalar_one_or_none()

        if not keyframe:
            raise NotFoundError(f'关键帧不存在: {keyframe_id}')

        # 获取脚本以获取默认配置
        script_result = await self.db.execute(
            select(Script).where(Script.id == keyframe.script_id)
        )
        script = script_result.scalar_one_or_none()

        # 使用提供的参数或默认配置
        if not model and script:
            # 从项目获取默认模型配置（需要扩展Script或Project模型）
            model = 'jimeng_t2i_v40'  # 默认值：火山即梦4.0

        if not aspect_ratio:
            aspect_ratio = 'auto'

        if not quality:
            quality = '720p'

        # 更新状态为generating
        keyframe.status = KeyframeStatus.GENERATING
        keyframe.error_message = None
        await self.db.commit()
        
        # 刷新keyframe对象以确保属性已加载,避免会话关闭后访问失败
        await self.db.refresh(keyframe)

        # 保存关键帧ID和参数，用于后台任务（在提交后获取）
        saved_keyframe_id = keyframe.id
        saved_model = model
        saved_aspect_ratio = aspect_ratio
        saved_quality = quality

        # 启动后台任务重新生成（使用 ensure_future 确保任务正确启动）
        # 注意：必须在数据库提交后创建任务，避免会话问题
        try:
            task = asyncio.ensure_future(
                self._regenerate_keyframe_background(
                    saved_keyframe_id, saved_model, saved_aspect_ratio, saved_quality
                )
            )
            # 添加错误回调，确保任务异常能被记录
            task.add_done_callback(
                lambda t: logger.error(
                    'Background regenerate task failed',
                    error=str(t.exception()) if t.exception() else 'Unknown error',
                    keyframe_id=saved_keyframe_id
                ) if t.exception() else None
            )
        except Exception as e:
            logger.error(
                'Failed to start background regenerate task',
                error=str(e),
                keyframe_id=saved_keyframe_id,
                exc_info=True
            )
            # 如果任务启动失败，更新状态为失败
            keyframe.status = KeyframeStatus.FAILED
            keyframe.error_message = f'启动后台任务失败: {str(e)}'
            await self.db.commit()
            # 再次刷新以确保最新状态
            await self.db.refresh(keyframe)

        return keyframe

    async def _regenerate_keyframe_background(
        self,
        keyframe_id: int,
        model: str,
        aspect_ratio: str,
        quality: str
    ) -> None:
        """后台任务：重新生成关键帧图片(使用前一帧作为参考).

        Args:
            keyframe_id: 关键帧ID
            model: 图片生成模型
            aspect_ratio: 图像比例
            quality: 清晰度
        """
        # 创建新的数据库会话用于后台任务
        async with async_session_maker() as db:
            try:
                # 重新查询关键帧对象（使用新的会话）
                result = await db.execute(
                    select(Keyframe).where(Keyframe.id == keyframe_id)
                )
                keyframe = result.scalar_one_or_none()

                if not keyframe:
                    logger.error(
                        'Keyframe not found for regeneration',
                        keyframe_id=keyframe_id
                    )
                    return

                prompt = keyframe.prompt or ''

                # 获取同一脚本的所有关键帧,找到前一帧作为参考图
                script_id = keyframe.script_id
                all_keyframes_result = await db.execute(
                    select(Keyframe)
                    .where(Keyframe.script_id == script_id)
                    .order_by(Keyframe.created_at)
                )
                all_keyframes = list(all_keyframes_result.scalars().all())
                
                # 自定义排序(与get_keyframes_by_script_id相同)
                import re
                def sort_key(kf: Keyframe) -> tuple:
                    segment_id = kf.segment_id
                    if '_first_frame' in segment_id:
                        return (0, 0)
                    match = re.search(r'segment_(\d+)', segment_id)
                    if match:
                        return (1, int(match.group(1)))
                    return (2, 0)
                
                all_keyframes.sort(key=sort_key)
                
                # 构建参考图列表：第0帧 + 前一帧
                reference_urls: List[str] = []
                current_index = -1
                
                # 找到当前关键帧的索引
                for i, kf in enumerate(all_keyframes):
                    if kf.id == keyframe_id:
                        current_index = i
                        break
                
                # 对于非第0帧，添加参考图
                if current_index > 0:
                    # 添加第0帧作为参考
                    first_frame = all_keyframes[0]
                    if first_frame.image_url:
                        reference_urls.append(first_frame.image_url)
                        logger.info(
                            'Using first frame as reference for regeneration',
                            current_keyframe_id=keyframe_id,
                            first_keyframe_id=first_frame.id,
                            first_frame_url=first_frame.image_url
                        )
                    
                    # 添加前一帧作为参考
                    prev_kf = all_keyframes[current_index - 1]
                    if prev_kf.image_url:
                        reference_urls.append(prev_kf.image_url)
                        logger.info(
                            'Using previous keyframe as reference for regeneration',
                            current_keyframe_id=keyframe_id,
                            current_segment_id=keyframe.segment_id,
                            reference_keyframe_id=prev_kf.id,
                            reference_segment_id=prev_kf.segment_id,
                            reference_url=prev_kf.image_url
                        )

                # 调用图片生成API(传入参考图列表)
                # 使用模型降级机制
                fallback_models = self._get_fallback_models(model)
                image_url = None
                last_error = None
                used_model = model

                for current_model in fallback_models:
                    try:
                        logger.info(
                            'Regenerating keyframe with model',
                            keyframe_id=keyframe_id,
                            model=current_model
                        )
                        
                        result = await image_generation_service.generate_image(
                            prompt=prompt,
                            model=current_model,
                            aspect_ratio=aspect_ratio,
                            quality=quality,
                            reference_image_urls=reference_urls if reference_urls else None
                        )
                        image_url = result.get('url')
                        
                        if image_url:
                            used_model = current_model
                            if current_model != model:
                                logger.info(
                                    'Model fallback successful for regeneration',
                                    keyframe_id=keyframe_id,
                                    original_model=model,
                                    used_model=current_model
                                )
                            break
                            
                    except Exception as e:
                        error_msg = str(e).lower()
                        last_error = e
                        
                        # 检查是否是模型维护错误
                        if 'maintenance' in error_msg or 'model maintenance' in error_msg:
                            logger.warning(
                                'Model under maintenance during regeneration, trying fallback',
                                keyframe_id=keyframe_id,
                                failed_model=current_model,
                                error=str(e)
                            )
                            # 继续尝试下一个模型
                            continue
                        else:
                            # 其他错误，不降级，直接抛出
                            logger.error(
                                'Keyframe regeneration failed with non-maintenance error',
                                keyframe_id=keyframe_id,
                                model=current_model,
                                error=str(e)
                            )
                            raise
                
                if not image_url:
                    raise Exception(f'图片重新生成失败（所有模型均不可用）: {str(last_error)}')

                # 上传到OSS
                filename = f'keyframe_{keyframe.id}.jpg'
                upload_result = await oss_service.upload_from_url(
                    url=image_url,
                    filename=filename,
                    category='keyframes'
                )

                # 更新关键帧记录（使用新的数据库会话）
                keyframe.image_url = upload_result['url']
                keyframe.status = KeyframeStatus.COMPLETED
                keyframe.error_message = None

                await db.commit()

                logger.info(
                    'Keyframe regenerated successfully',
                    keyframe_id=keyframe.id,
                    image_url=upload_result['url']
                )

            except Exception as e:
                logger.error(
                    'Failed to regenerate keyframe',
                    keyframe_id=keyframe_id,
                    error=str(e),
                    exc_info=True
                )

                try:
                    # 重新查询关键帧以更新状态
                    result = await db.execute(
                        select(Keyframe).where(Keyframe.id == keyframe_id)
                    )
                    keyframe_to_update = result.scalar_one_or_none()
                    
                    if keyframe_to_update:
                        keyframe_to_update.status = KeyframeStatus.FAILED
                        keyframe_to_update.error_message = str(e)
                        await db.commit()
                except Exception as commit_error:
                    logger.error(
                        'Failed to update keyframe status',
                        keyframe_id=keyframe_id,
                        error=str(commit_error),
                        exc_info=True
                    )

    async def update_keyframe_prompt(
        self, keyframe_id: int, prompt: str
    ) -> Keyframe:
        """更新关键帧提示词.

        Args:
            keyframe_id: 关键帧ID
            prompt: 新的提示词

        Returns:
            更新后的关键帧

        Raises:
            NotFoundError: 关键帧不存在
        """
        result = await self.db.execute(
            select(Keyframe).where(Keyframe.id == keyframe_id)
        )
        keyframe = result.scalar_one_or_none()

        if not keyframe:
            raise NotFoundError(f'关键帧不存在: {keyframe_id}')

        keyframe.prompt = prompt
        await self.db.commit()

        # 刷新keyframe对象以确保属性已加载,避免会话关闭后访问失败
        await self.db.refresh(keyframe)

        logger.info(
            'Keyframe prompt updated',
            keyframe_id=keyframe_id,
            prompt=prompt[:50]  # 只记录前50个字符
        )

        return keyframe

    async def upload_keyframe_image(
        self, keyframe_id: int, file_data: bytes, filename: str
    ) -> Keyframe:
        """上传本地图片替换关键帧.

        Args:
            keyframe_id: 关键帧ID
            file_data: 文件数据
            filename: 文件名

        Returns:
            更新后的关键帧

        Raises:
            NotFoundError: 关键帧不存在
        """
        from io import BytesIO

        result = await self.db.execute(
            select(Keyframe).where(Keyframe.id == keyframe_id)
        )
        keyframe = result.scalar_one_or_none()

        if not keyframe:
            raise NotFoundError(f'关键帧不存在: {keyframe_id}')

        # 上传到OSS
        file_stream = BytesIO(file_data)
        upload_result = oss_service.upload_file(
            file_data=file_stream,
            filename=filename,
            category='keyframes',
            content_type='image/jpeg'
        )

        # 更新关键帧记录
        keyframe.image_url = upload_result['url']
        keyframe.status = KeyframeStatus.COMPLETED
        keyframe.error_message = None

        await self.db.commit()
        
        # 刷新keyframe对象以确保属性已加载,避免会话关闭后访问失败
        await self.db.refresh(keyframe)

        logger.info(
            'Keyframe image uploaded',
            keyframe_id=keyframe_id,
            image_url=upload_result['url']
        )

        return keyframe

    async def get_keyframes_by_script_id(
        self, script_id: int
    ) -> List[Keyframe]:
        """获取脚本的所有关键帧.

        Args:
            script_id: 脚本ID

        Returns:
            关键帧列表（按 segment 顺序；兼容历史 _first_frame，会排在 segment_0 附近）
        """
        result = await self.db.execute(
            select(Keyframe)
            .where(Keyframe.script_id == script_id)
            .order_by(Keyframe.created_at)
        )
        keyframes = list(result.scalars().all())

        await self._refresh_stale_keyframes(keyframes)

        # 自定义排序：按 segment 数字排序；兼容历史 _first_frame（视为 segment_0 的“旧首帧”）
        def sort_key(kf: Keyframe) -> tuple:
            segment_id = kf.segment_id
            if '_first_frame' in segment_id:
                return (0, 0)
            # 其他帧按segment数字排序
            # 提取segment_id中的数字,如segment_0 -> 0, segment_1 -> 1
            import re
            match = re.search(r'segment_(\d+)', segment_id)
            if match:
                return (1, int(match.group(1)))
            # 未匹配的放最后
            return (2, 0)
        
        keyframes.sort(key=sort_key)

        return keyframes

    async def _refresh_stale_keyframes(self, keyframes: List[Keyframe]) -> None:
        """将长时间未更新的关键帧标记为失败，避免持续轮询."""
        if not keyframes:
            return

        now = datetime.now(timezone.utc)
        has_updates = False

        for keyframe in keyframes:
            if keyframe.status != KeyframeStatus.GENERATING or not keyframe.updated_at:
                continue

            updated_at = keyframe.updated_at
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)

            if now - updated_at > STALE_KEYFRAME_TIMEOUT:
                keyframe.status = KeyframeStatus.FAILED
                keyframe.error_message = '生成超时，请重新生成关键帧'
                has_updates = True
                logger.warning(
                    'Keyframe generation timed out',
                    keyframe_id=keyframe.id,
                    script_id=keyframe.script_id,
                    segment_id=keyframe.segment_id,
                    last_updated=updated_at.isoformat()
                )

        if has_updates:
            await self.db.commit()

    async def continue_generate_remaining_keyframes(
        self,
        script_id: int,
        model: str,
        aspect_ratio: str,
        quality: Optional[str]
    ) -> List[Keyframe]:
        """继续生成剩余的关键帧（兼容接口）.

        Args:
            script_id: 脚本ID
            model: 图片生成模型
            aspect_ratio: 图像比例
            quality: 清晰度

        Returns:
            所有关键帧列表

        Raises:
            NotFoundError: 脚本不存在
            ValidationError: 没有找到关键帧记录
        """
        # 获取脚本
        result = await self.db.execute(
            select(Script).where(Script.id == script_id)
        )
        script = result.scalar_one_or_none()

        if not script:
            raise NotFoundError(f'脚本不存在: {script_id}')

        # 获取所有关键帧
        keyframes_result = await self.db.execute(
            select(Keyframe)
            .where(Keyframe.script_id == script_id)
            .order_by(Keyframe.id)
        )
        keyframes = list(keyframes_result.scalars().all())

        if not keyframes:
            raise ValidationError('没有找到关键帧记录')

        # 全局移除“第0帧确认”流程后，这个接口用于“继续/补生成”：
        # 只要存在 PENDING 的关键帧，就从最早的一个开始继续生成。
        remaining_keyframes = [kf for kf in keyframes if kf.status == KeyframeStatus.PENDING]

        if not remaining_keyframes:
            logger.info('No remaining keyframes to generate', script_id=script_id)
            return keyframes

        # 保持剩余关键帧状态为PENDING，由后台任务逐个更新为GENERATING
        # for kf in remaining_keyframes:
        #     kf.status = KeyframeStatus.GENERATING
        # await self.db.commit()
        
        # 刷新所有keyframe对象以确保属性已加载,避免会话关闭后访问失败
        for kf in keyframes:
            await self.db.refresh(kf)

        # 解析脚本段落
        segments = parse_script(script.content)
        
        # 启动后台任务生成剩余关键帧
        all_keyframe_ids = [kf.id for kf in keyframes]
        # 从第一个 pending 的位置开始续跑
        start_from_index = min(all_keyframe_ids.index(kf.id) for kf in remaining_keyframes)
        asyncio.create_task(
            self._generate_keyframes_background(
                all_keyframe_ids, segments, model, aspect_ratio, quality,
                start_from_index=start_from_index
            )
        )

        logger.info(
            'Remaining keyframes generation started',
            script_id=script_id,
            remaining_count=len(remaining_keyframes)
        )

        return keyframes

    async def get_keyframe_by_id(self, keyframe_id: int) -> Optional[Keyframe]:
        """根据ID获取关键帧.

        Args:
            keyframe_id: 关键帧ID

        Returns:
            关键帧对象，如果不存在返回None
        """
        result = await self.db.execute(
            select(Keyframe).where(Keyframe.id == keyframe_id)
        )
        return result.scalar_one_or_none()

