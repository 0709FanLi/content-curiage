"""
视频生成服务
处理视频的生成、更新、导出等操作
"""

import asyncio
import time
import httpx
import structlog
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from io import BytesIO
import zipfile
import os
from datetime import datetime, timedelta

from src.models.tables.video_segment import VideoSegment, VideoStatus, AudioStatus
from src.models.tables.keyframe import Keyframe, KeyframeStatus
from src.models.tables.script import Script
from src.models.database import async_session_maker
from src.config.settings import settings
from src.services.oss_service import oss_service
from src.services.upload_limiter import upload_limiter
from src.utils.exceptions import NotFoundError, ValidationError
from src.utils.script_parser import ScriptSegment, parse_script
from src.models.schemas.video import VideoSegmentResponse

logger = structlog.get_logger(__name__)

def _get_max_concurrent_video_generations() -> int:
    """从环境变量读取视频生成并发上限。

    说明：
    - 需求：同时最多生成 N 个视频，其他任务在队列中等待。
    - N 从 .env / 环境变量读取，避免硬编码。
    """
    raw = (os.getenv("MAX_CONCURRENT_VIDEO_GENERATIONS", "") or "").strip()
    if not raw:
        return 3
    try:
        value = int(raw)
    except ValueError:
        return 3
    return max(1, value)


# 全局并发控制：同一进程内最多并发生成 N 个视频；其余任务自动等待（排队）
_VIDEO_GENERATION_SEMAPHORE = asyncio.Semaphore(
    _get_max_concurrent_video_generations()
)

JIMENG_VIDEO_MODEL_ID = 'jimeng_i2v_first_v30_1080'
DOUBAO_SEEDANCE_1_5_PRO_MODEL_ID = 'doubao-seedance-1-5-pro-251215'


class VeoQuotaExhaustedError(Exception):
    """Veo API配额耗尽异常."""
    pass


class VideoService:
    """视频生成服务类."""

    def __init__(self, db: AsyncSession):
        """初始化视频服务.

        Args:
            db: 数据库会话
        """
        self.db = db
        self.base_url = settings.image_generation_base_url
        self.api_key = settings.grsai_key

    @staticmethod
    def _is_first_frame_reference_model(model: str) -> bool:
        """判断是否为“仅首帧参考”的视频模型。

        需求：豆包与即梦均为首帧参考模型，视频分段应以“本段关键帧”作为首帧参考，
        不再使用历史“第0帧”（segment_0_first_frame）或上一段关键帧作为下一段首帧。
        """
        if not model:
            return False
        return (
            model.startswith('jimeng')
            or model == DOUBAO_SEEDANCE_1_5_PRO_MODEL_ID
            or model.startswith('doubao-seedance-1-5-pro')
        )

    def _get_video_fallback_models(self, model: str, has_first_frame: bool) -> List[str]:
        """获取视频生成模型降级列表（过滤掉不可用的 GRSAI 模型）.
        
        Args:
            model: 当前模型
            has_first_frame: 是否有首帧（用于判断是否可以降级到即梦）
            
        Returns:
            模型列表（包含当前模型和降级模型，已过滤不可用模型）
        """
        from src.services.model_status_service import model_status_service
        
        if not has_first_frame:
            # 如果没有首帧，不能降级
            return [model]

        jimeng_enabled = bool(getattr(settings, 'enable_jimeng_video', False))
        
        # 推荐/降级链（按优先级）：
        # veo3.1-fast-ref（参考图） -> sora-2 -> doubao -> jimeng（可选）
        #
        # 兼容历史数据：若遇到旧的 veo3.1-fast（首尾帧模式）字段，
        # 视为 veo3.1-fast-ref 的入口，避免旧数据直接失败。
        if model in {'veo3.1-fast-ref', 'veo3.1-fast'}:
            chain = ['veo3.1-fast-ref', 'sora-2']
            chain.append(DOUBAO_SEEDANCE_1_5_PRO_MODEL_ID)
            if jimeng_enabled:
                chain.append(JIMENG_VIDEO_MODEL_ID)
        # sora-2-ref 已废弃，映射到 sora-2
        elif model == 'sora-2-ref':
            chain = ['sora-2']
            chain.append(DOUBAO_SEEDANCE_1_5_PRO_MODEL_ID)
            if jimeng_enabled:
                chain.append(JIMENG_VIDEO_MODEL_ID)
        # sora-2 开始的降级链
        elif model == 'sora-2':
            chain = ['sora-2']
            chain.append(DOUBAO_SEEDANCE_1_5_PRO_MODEL_ID)
            if jimeng_enabled:
                chain.append(JIMENG_VIDEO_MODEL_ID)
        # Doubao Seedance 模型可降级到即梦（可选）
        elif model == DOUBAO_SEEDANCE_1_5_PRO_MODEL_ID or model.startswith('doubao-seedance-1-5-pro'):
            chain = [model]
            if jimeng_enabled:
                chain.append(JIMENG_VIDEO_MODEL_ID)
        # 即梦模型不降级
        elif model.startswith('jimeng'):
            chain = [model]
        # 其他veo模型（veo3-fast, veo3-pro等）的降级链
        elif model.startswith('veo'):
            chain = [model]
            chain.append(DOUBAO_SEEDANCE_1_5_PRO_MODEL_ID)
            if jimeng_enabled:
                chain.append(JIMENG_VIDEO_MODEL_ID)
        # 默认返回当前模型
        else:
            chain = [model]
        
        # 过滤掉不可用的 GRSAI 模型
        filtered_models = []
        for m in chain:
            # 如果是 GRSAI 视频模型，检查可用性
            check_id = m
            # 衍生模型共享主模型状态
            if check_id == 'veo3.1-fast-ref':
                check_id = 'veo3.1-fast'
            if check_id in model_status_service.grsai_models.get("video", []):
                if model_status_service.is_model_available(check_id):
                    filtered_models.append(m)
                else:
                    logger.info(
                        "Skipping unavailable GRSAI video model in fallback chain",
                        model=m,
                        original_model=model
                    )
            else:
                # 非 GRSAI 模型（如 jimeng），直接包含
                filtered_models.append(m)
        
        # 如果所有模型都被过滤掉了，至少保留原始模型（让它尝试并记录详细错误）
        if not filtered_models:
            logger.warning(
                "All video models filtered out, keeping original model",
                model=model
            )
            filtered_models = [model]
        
        return filtered_models

    def _determine_aspect_ratio(self, model: str, prompt: str) -> str:
        """根据模型和内容确定合适的视频比例.

        对于 Veo 模型（包含 veo3.1-fast-ref 参考图模式）：
        - 根据prompt内容判断场景类型
        - 横向场景（风景、群景等）使用16:9
        - 竖向场景（人物特写等）使用9:16

        Args:
            model: 模型名称
            prompt: 提示词

        Returns:
            视频比例字符串
        """
        if model not in ["veo3.1-fast-ref"]:
            return "16:9"  # 其他模型默认16:9

        # 定义竖向场景关键词（优先级高）
        portrait_keywords = [
            'person', 'people', 'man', 'woman', 'boy', 'girl', 'child', 'baby',
            'face', 'portrait', 'selfie', 'photographer', 'model', 'actor', 'singer',
            'dancer', 'chef', 'doctor', 'teacher', 'student', 'worker', 'artist',
            'painter', 'musician', 'athlete', 'soldier', 'police', 'firefighter',
            'character', 'hero', 'villain', 'superhero', 'standing', 'alone',
            'single', 'individual', 'one person', 'close-up', 'close up'
        ]

        # 定义横向场景关键词
        landscape_keywords = [
            'landscape', 'scenery', 'scene', 'view', 'mountain', 'sea', 'ocean', 'sky',
            'sunset', 'sunrise', 'forest', 'field', 'road', 'cityscape', 'street',
            'crowd', 'group', 'team', 'sports', 'game', 'battle', 'war', 'army',
            'car', 'vehicle', 'train', 'plane', 'ship', 'boat', 'traffic', 'road',
            'building', 'house', 'home', 'apartment', 'office', 'school', 'hospital',
            'church', 'temple', 'bridge', 'tower', 'castle', 'palace', 'museum',
            'park', 'garden', 'farm', 'factory', 'warehouse', 'airport', 'station',
            'wide', 'panorama', 'panoramic', 'overview', 'aerial', 'birds eye'
        ]

        prompt_lower = prompt.lower()

        # 计算关键词匹配度
        portrait_score = sum(1 for keyword in portrait_keywords if keyword in prompt_lower)
        landscape_score = sum(1 for keyword in landscape_keywords if keyword in prompt_lower)

        # 根据关键词匹配度决定比例
        # 竖向优先级更高（人物特写等）
        if portrait_score > landscape_score:
            return "9:16"  # 竖向
        elif landscape_score > 0:
            return "16:9"  # 横向
        else:
            return "16:9"  # 默认

    @staticmethod
    def _ffprobe_video_file(input_file: str) -> Dict[str, Any]:
        """用 ffprobe 探测本地视频文件信息（含音频流/真实时长/VFR 判断）.

        Args:
            input_file: 本地视频文件路径

        Returns:
            包含以下字段的字典：
            - fps: float
            - total_frames: int
            - width: int
            - height: int
            - has_audio: bool
            - duration_sec: float
            - trimmed_duration_sec: float
            - is_vfr: bool（可变帧率）

        Raises:
            Exception: ffprobe 执行失败或无法解析视频流
        """
        import json
        import subprocess

        probe_cmd = [
            'ffprobe',
            '-v', 'error',
            '-count_frames',
            '-show_entries',
            'stream=codec_type,nb_read_frames,r_frame_rate,avg_frame_rate,width,height:format=duration',
            '-of', 'json',
            input_file,
        ]

        probe_result = subprocess.run(
            probe_cmd,
            capture_output=True,
            text=True,
            check=True,
        )

        probe_data = json.loads(probe_result.stdout)
        streams = probe_data.get('streams') or []
        video_stream = next(
            (s for s in streams if s.get('codec_type') == 'video'),
            None,
        )
        if not video_stream:
            raise Exception(f'无法从 ffprobe 结果中找到视频流: {input_file}')

        has_audio = any(s.get('codec_type') == 'audio' for s in streams)

        def parse_fps(fps_str: str) -> float:
            try:
                num_str, den_str = str(fps_str).split('/')
                num = float(num_str)
                den = float(den_str)
                if den == 0:
                    return 0.0
                return num / den
            except Exception:
                return 0.0

        fps_r = parse_fps(video_stream.get('r_frame_rate', '0/1'))
        fps_avg = parse_fps(video_stream.get('avg_frame_rate', '0/1'))
        fps = fps_r or fps_avg or 24.0

        is_vfr = False
        if fps_r and fps_avg and abs(fps_r - fps_avg) > 0.01:
            is_vfr = True

        try:
            total_frames = int(video_stream.get('nb_read_frames', 0))
        except (ValueError, TypeError):
            total_frames = int(fps * 5) + 1

        try:
            duration_sec = float(
                (probe_data.get('format') or {}).get('duration') or 0.0
            )
        except (ValueError, TypeError):
            duration_sec = 0.0

        trimmed_duration_sec = max(
            0.0,
            (total_frames - 1) / fps if total_frames > 1 else duration_sec,
        )

        return {
            'fps': float(fps),
            'total_frames': int(total_frames),
            'width': int(video_stream.get('width', 1280)),
            'height': int(video_stream.get('height', 720)),
            'has_audio': bool(has_audio),
            'duration_sec': float(duration_sec),
            'trimmed_duration_sec': float(trimmed_duration_sec),
            'is_vfr': bool(is_vfr),
        }

    async def generate_videos(
        self,
        script_id: int,
        model: str = "veo3.1-fast-ref",
        aspect_ratio: str = "16:9",
        duration: float = 4.0
    ) -> List[VideoSegment]:
        """批量生成视频（异步后台任务）.

        根据脚本的关键帧生成 N 段视频：
        - 全局移除第0帧后：首段关键帧为 segment_0
        - 每段视频至少使用“本段关键帧”作为首帧参考（first_frame_url = segment_i）
        - 对于需要过渡引导的模型，可额外传入下一段关键帧作为 last_frame_url（segment_{i+1}）

        Args:
            script_id: 脚本ID
            model: 视频生成模型 (默认 veo3.1-fast-ref)
            aspect_ratio: 视频比例
            duration: 视频时长（秒，默认6s）

        Returns:
            视频片段列表

        Raises:
            NotFoundError: 脚本不存在
            ValidationError: 参数验证失败
        """
        if model.startswith('jimeng') and not bool(getattr(settings, 'enable_jimeng_video', False)):
            raise ValidationError('即梦视频模型已被禁用（仅用于对比测试），如需启用请打开配置开关')

        # 获取脚本
        result = await self.db.execute(
            select(Script).where(Script.id == script_id)
        )
        script = result.scalar_one_or_none()

        if not script:
            raise NotFoundError(f'脚本不存在: {script_id}')

        if not script.content:
            raise ValidationError('脚本内容为空')

        # 解析脚本段落，用于获取视频描述(video_desc)
        segments = parse_script(script.content)
        segment_map = {seg.segment_id: seg for seg in segments}

        # 删除该脚本的所有旧视频片段
        await self.db.execute(
            delete(VideoSegment).where(VideoSegment.script_id == script_id)
        )
        await self.db.commit()
        
        logger.info(
            'Old video segments deleted',
            script_id=script_id
        )

        # 获取脚本的所有关键帧，按segment_id排序
        keyframes_result = await self.db.execute(
            select(Keyframe)
            .where(Keyframe.script_id == script_id)
            .where(Keyframe.status == KeyframeStatus.COMPLETED)
            .order_by(Keyframe.segment_id)
        )
        keyframes = list(keyframes_result.scalars().all())

        if not keyframes:
            raise ValidationError('脚本没有已完成的关键帧')

        # 按segment_id分类关键帧
        keyframe_map: Dict[str, Keyframe] = {kf.segment_id: kf for kf in keyframes}

        # 兼容历史数据：
        # - 旧项目可能只有 segment_0_first_frame 而缺少 segment_0
        #   此时将其视为 segment_0 的替代（用于首段确认帧/首段视频首帧）
        if "segment_0" not in keyframe_map and "segment_0_first_frame" in keyframe_map:
            keyframe_map["segment_0"] = keyframe_map["segment_0_first_frame"]

        # 提取普通段落（不包含_first_frame和_last_frame）
        normal_segments = [
            kf for kf in keyframes
            if not kf.segment_id.endswith('_first_frame')
            and not kf.segment_id.endswith('_last_frame')
        ]

        if not normal_segments:
            raise ValidationError('脚本没有有效的段落关键帧')

        # 构建视频片段配置
        video_configs = []
        segment_index = 0

        # 方案 A：首帧参考模型（豆包/即梦）
        # - 每段视频以“本段关键帧”作为首帧参考：segment_0 用 segment_0，segment_1 用 segment_1 ...
        # - 不再使用第0帧（segment_0_first_frame）
        if self._is_first_frame_reference_model(model):
            for i in range(len(normal_segments)):
                segment_kf = normal_segments[i]
                script_segment = segment_map.get(segment_kf.segment_id)

                fallback_prompt = ''
                if script_segment and script_segment.video_desc:
                    fallback_prompt = script_segment.video_desc
                elif segment_kf.prompt:
                    fallback_prompt = segment_kf.prompt

                prompt_text = self._build_video_prompt_from_video_desc(
                    script_segment, fallback_prompt
                )

                video_configs.append({
                    'segment_index': segment_index,
                    'first_frame_url': segment_kf.image_url,
                    'last_frame_url': None,
                    'prompt': prompt_text,
                    'aspect_ratio': self._determine_aspect_ratio(model, prompt_text),
                })
                segment_index += 1
        else:
            # 方案 B：其他模型（可能支持首尾帧/多参考图等）。
            # 全局移除第0帧后：首段使用 segment_0 作为首帧参考；不再依赖 segment_0_first_frame。
            for i in range(len(normal_segments)):
                current_segment = normal_segments[i]
                next_segment = normal_segments[i + 1] if i + 1 < len(normal_segments) else None

                # 获取对应的脚本段落以获取 video_desc（当前段）
                script_segment = segment_map.get(current_segment.segment_id)

                fallback_prompt = ""
                if script_segment and script_segment.video_desc:
                    fallback_prompt = script_segment.video_desc
                elif current_segment.prompt:
                    fallback_prompt = current_segment.prompt

                prompt_text = self._build_video_prompt_from_video_desc(
                    script_segment, fallback_prompt
                )

                video_configs.append(
                    {
                        "segment_index": segment_index,
                        "first_frame_url": current_segment.image_url,
                        # 若存在下一段关键帧，则作为过渡引导（可选）；最后一段为 None
                        "last_frame_url": next_segment.image_url if next_segment else None,
                        "prompt": prompt_text,
                        "aspect_ratio": self._determine_aspect_ratio(model, prompt_text),
                    }
                )
                segment_index += 1

        # 创建视频片段记录
        video_segments: List[VideoSegment] = []
        # 用于前端展示“排队中”：优先将前 N 个标记为 generating，其余标记为 pending
        # 注意：实际执行仍受全局 semaphore 控制；这里仅用于更准确的状态展示。
        display_concurrency = _get_max_concurrent_video_generations()
        if model.startswith('jimeng'):
            display_concurrency = 1

        # 时长策略：
        # - 前 N-1 段固定使用 base_duration
        # - 最后一段按总时长扣减计算：total - base_duration*(N-1)
        #   若不足 4 秒则按 4 秒（豆包支持 4-12s 精准控时长）
        try:
            base_duration = float(duration)
        except Exception:
            base_duration = 4.0
        base_duration = max(4.0, min(12.0, base_duration))

        target_total_duration = None
        try:
            if getattr(script, "total_duration", None) is not None:
                target_total_duration = float(script.total_duration)
        except Exception:
            target_total_duration = None

        total_segments = len(video_configs)
        if target_total_duration is None or target_total_duration <= 0:
            target_total_duration = base_duration * max(1, total_segments)

        last_raw = float(target_total_duration) - base_duration * max(0, total_segments - 1)
        last_segment_duration = max(4.0, min(12.0, last_raw))

        for idx, config in enumerate(video_configs):
            # 对于 veo3.1-fast-ref 模型，使用智能确定的 aspect_ratio；其他模型使用传入的 aspect_ratio
            final_aspect_ratio = config.get('aspect_ratio', aspect_ratio) if model in ["veo3.1-fast-ref"] else aspect_ratio

            # 默认时长：前 N-1 段 = base_duration，最后一段 = last_segment_duration
            seg_duration = base_duration if idx < total_segments - 1 else last_segment_duration

            # 规则：最后一段必须固定使用豆包模型（以确保 4-12s 时长可控）
            seg_model = model
            first_frame_url = config['first_frame_url']
            last_frame_url = config['last_frame_url']
            if idx == total_segments - 1:
                seg_model = DOUBAO_SEEDANCE_1_5_PRO_MODEL_ID
                # 豆包为首帧参考：用“本段关键帧”作为首帧参考，避免沿用首尾帧/过渡段结构
                first_frame_url = last_frame_url or first_frame_url
                last_frame_url = None
            
            video_segment = VideoSegment(
                script_id=script_id,
                segment_index=config['segment_index'],
                first_frame_url=first_frame_url,
                last_frame_url=last_frame_url,
                prompt=config['prompt'],
                model=seg_model,
                aspect_ratio=final_aspect_ratio,
                duration=seg_duration,
                status=(
                    VideoStatus.GENERATING
                    if len(video_segments) < display_concurrency
                    else VideoStatus.PENDING
                ),
            )
            self.db.add(video_segment)
            video_segments.append(video_segment)

        await self.db.commit()

        # 保存视频片段ID列表，用于后台任务
        video_segment_ids = [vs.id for vs in video_segments]

        # 启动后台任务异步生成视频
        asyncio.create_task(
            self._generate_videos_background(video_segment_ids)
        )

        logger.info(
            'Videos generation started',
            script_id=script_id,
            total_segments=len(video_segments),
            model=model
        )

        return video_segments

    async def generate_videos_text_only(
        self,
        script_id: int,
        model: str = DOUBAO_SEEDANCE_1_5_PRO_MODEL_ID,
        aspect_ratio: str = "16:9",
        duration: float = 4.0,
    ) -> List[VideoSegment]:
        """纯文生视频（T2V）批量生成：不依赖关键帧。

        适用于：
        - one_step 关闭智能分镜时
        - 或 agent 判断某些段落无需首帧/参考图

        说明：
        - first_frame_url/last_frame_url 为空时，Ark/部分模型会按纯文本生成（真正的 T2V）
        - 仍复用现有的后台生成与并发控制逻辑
        """
        if model.startswith('jimeng') and not bool(getattr(settings, 'enable_jimeng_video', False)):
            raise ValidationError('即梦视频模型已被禁用（仅用于对比测试），如需启用请打开配置开关')

        result = await self.db.execute(select(Script).where(Script.id == script_id))
        script = result.scalar_one_or_none()
        if not script or not script.content:
            raise ValidationError(f'脚本不存在或内容为空: {script_id}')

        segments = parse_script(script.content)
        if not segments:
            raise ValidationError('脚本中没有找到有效段落')

        segment_map = {seg.segment_id: seg for seg in segments}

        await self.db.execute(delete(VideoSegment).where(VideoSegment.script_id == script_id))
        await self.db.commit()

        video_configs = []
        for idx, seg in enumerate(segments):
            prompt_text = self._build_video_prompt_from_video_desc(seg, (seg.video_desc or seg.content or '').strip())
            video_configs.append(
                {
                    "segment_index": idx,
                    "first_frame_url": None,
                    "last_frame_url": None,
                    "prompt": prompt_text,
                    "aspect_ratio": self._determine_aspect_ratio(model, prompt_text),
                }
            )

        video_segments: List[VideoSegment] = []
        display_concurrency = _get_max_concurrent_video_generations()
        if model.startswith('jimeng'):
            display_concurrency = 1

        try:
            base_duration = float(duration)
        except Exception:
            base_duration = 4.0
        base_duration = max(4.0, min(12.0, base_duration))

        target_total_duration = None
        try:
            if getattr(script, "total_duration", None) is not None:
                target_total_duration = float(script.total_duration)
        except Exception:
            target_total_duration = None
        if target_total_duration is None or target_total_duration <= 0:
            target_total_duration = base_duration * max(1, len(video_configs))

        last_raw = float(target_total_duration) - base_duration * max(0, len(video_configs) - 1)
        last_segment_duration = max(4.0, min(12.0, last_raw))

        for idx, config in enumerate(video_configs):
            final_aspect_ratio = config.get('aspect_ratio', aspect_ratio) if model in ["veo3.1-fast-ref"] else aspect_ratio
            seg_duration = base_duration if idx < len(video_configs) - 1 else last_segment_duration

            seg_model = model
            # 规则：最后一段固定使用豆包模型（以确保 4-12s 时长可控）
            if idx == len(video_configs) - 1:
                seg_model = DOUBAO_SEEDANCE_1_5_PRO_MODEL_ID

            video_segment = VideoSegment(
                script_id=script_id,
                segment_index=config['segment_index'],
                first_frame_url=None,
                last_frame_url=None,
                prompt=config['prompt'],
                model=seg_model,
                aspect_ratio=final_aspect_ratio,
                duration=seg_duration,
                status=(
                    VideoStatus.GENERATING
                    if len(video_segments) < display_concurrency
                    else VideoStatus.PENDING
                ),
            )
            self.db.add(video_segment)
            video_segments.append(video_segment)

        await self.db.commit()
        video_segment_ids = [vs.id for vs in video_segments]
        asyncio.create_task(self._generate_videos_background(video_segment_ids))
        return video_segments

    async def generate_videos_mixed_first_frame(
        self,
        *,
        script_id: int,
        model: str = DOUBAO_SEEDANCE_1_5_PRO_MODEL_ID,
        aspect_ratio: str = "16:9",
        duration: float = 4.0,
        first_frame_by_segment_id: Optional[Dict[str, str]] = None,
        i2v_segment_ids: Optional[set] = None,
    ) -> List[VideoSegment]:
        """按段混用 I2V/T2V：对指定 segment_id 使用首帧参考，其余纯文本（T2V）。

        - i2v_segment_ids 中的段落：若存在对应 first_frame url，则 I2V；否则降级为 T2V
        - 非 i2v 段落：first_frame_url=None，走纯文本生成
        """
        if model.startswith('jimeng') and not bool(getattr(settings, 'enable_jimeng_video', False)):
            raise ValidationError('即梦视频模型已被禁用（仅用于对比测试），如需启用请打开配置开关')

        result = await self.db.execute(select(Script).where(Script.id == script_id))
        script = result.scalar_one_or_none()
        if not script or not script.content:
            raise ValidationError(f'脚本不存在或内容为空: {script_id}')

        segments = parse_script(script.content)
        if not segments:
            raise ValidationError('脚本中没有找到有效段落')

        await self.db.execute(delete(VideoSegment).where(VideoSegment.script_id == script_id))
        await self.db.commit()

        first_frame_by_segment_id = first_frame_by_segment_id or {}
        i2v_segment_ids = i2v_segment_ids or set()

        video_configs = []
        for idx, seg in enumerate(segments):
            prompt_text = self._build_video_prompt_from_video_desc(seg, (seg.video_desc or seg.content or '').strip())
            ff = None
            if seg.segment_id in i2v_segment_ids:
                ff = first_frame_by_segment_id.get(seg.segment_id) or None
            video_configs.append(
                {
                    "segment_index": idx,
                    "segment_id": seg.segment_id,
                    "first_frame_url": ff,
                    "last_frame_url": None,
                    "prompt": prompt_text,
                    "aspect_ratio": self._determine_aspect_ratio(model, prompt_text),
                }
            )

        video_segments: List[VideoSegment] = []
        display_concurrency = _get_max_concurrent_video_generations()
        if model.startswith('jimeng'):
            display_concurrency = 1

        try:
            base_duration = float(duration)
        except Exception:
            base_duration = 4.0
        base_duration = max(4.0, min(12.0, base_duration))

        target_total_duration = None
        try:
            if getattr(script, "total_duration", None) is not None:
                target_total_duration = float(script.total_duration)
        except Exception:
            target_total_duration = None
        if target_total_duration is None or target_total_duration <= 0:
            target_total_duration = base_duration * max(1, len(video_configs))

        last_raw = float(target_total_duration) - base_duration * max(0, len(video_configs) - 1)
        last_segment_duration = max(4.0, min(12.0, last_raw))

        for idx, config in enumerate(video_configs):
            final_aspect_ratio = config.get('aspect_ratio', aspect_ratio) if model in ["veo3.1-fast-ref"] else aspect_ratio
            seg_duration = base_duration if idx < len(video_configs) - 1 else last_segment_duration

            seg_model = model
            if idx == len(video_configs) - 1:
                seg_model = DOUBAO_SEEDANCE_1_5_PRO_MODEL_ID

            video_segment = VideoSegment(
                script_id=script_id,
                segment_index=config['segment_index'],
                first_frame_url=config.get("first_frame_url"),
                last_frame_url=None,
                prompt=config['prompt'],
                model=seg_model,
                aspect_ratio=final_aspect_ratio,
                duration=seg_duration,
                status=(
                    VideoStatus.GENERATING
                    if len(video_segments) < display_concurrency
                    else VideoStatus.PENDING
                ),
            )
            self.db.add(video_segment)
            video_segments.append(video_segment)

        await self.db.commit()
        video_segment_ids = [vs.id for vs in video_segments]
        asyncio.create_task(self._generate_videos_background(video_segment_ids))
        return video_segments

    @staticmethod
    def _build_video_prompt_from_video_desc(
        script_segment: Optional[ScriptSegment], fallback_prompt: str
    ) -> str:
        """构建视频生成提示词：优先使用“视频描述(video_desc)”，其次回退到旧提示词.

        Args:
            script_segment: 脚本段落（可能为空）
            fallback_prompt: 旧逻辑下的提示词（video_desc / keyframe.prompt 等）

        Returns:
            提示词文本
        """
        if script_segment is None:
            return (fallback_prompt or '').strip()

        video_desc = (script_segment.video_desc or '').strip()
        if video_desc:
            return video_desc
        return (fallback_prompt or '').strip()

    @staticmethod
    def _build_video_prompt_from_narration(
        script_segment: Optional[ScriptSegment], fallback_prompt: str
    ) -> str:
        """兼容旧接口：历史上该方法名表示“从口播构建视频提示词”。

        目前已切回“视频描述(video_desc)”作为视频生成提示词来源，因此该方法
        仅作为别名，避免外部引用报错。
        """
        return VideoService._build_video_prompt_from_video_desc(
            script_segment, fallback_prompt
        )

    async def _generate_videos_background(
        self, video_segment_ids: List[int]
    ) -> None:
        """后台任务：异步生成视频.

        根据模型类型决定生成策略:
        - 即梦模型(jimeng): 串行生成(并发限制=1)
        - 其他模型: 并发生成

        Args:
            video_segment_ids: 视频片段ID列表
        """
        try:
            from src.utils.redis_client import TaskCancellationManager
            
            # 获取script_id（从第一个视频片段）
            script_id = None
            if video_segment_ids:
                async with async_session_maker() as db:
                    result = await db.execute(
                        select(VideoSegment).where(VideoSegment.id == video_segment_ids[0])
                    )
                    first_segment = result.scalar_one_or_none()
                    if first_segment:
                        script_id = first_segment.script_id
            
            # 检查第一个视频片段的模型类型
            is_jimeng_model = False
            if video_segment_ids:
                async with async_session_maker() as db:
                    result = await db.execute(
                        select(VideoSegment).where(VideoSegment.id == video_segment_ids[0])
                    )
                    first_segment = result.scalar_one_or_none()
                    if first_segment and first_segment.model.startswith('jimeng'):
                        is_jimeng_model = True
                        logger.info(
                            'JiMeng model detected, using serial generation',
                            model=first_segment.model,
                            total_segments=len(video_segment_ids)
                        )

            if is_jimeng_model:
                # 即梦模型: 串行生成(一个接一个)
                for i, video_segment_id in enumerate(video_segment_ids):
                    # 【检查点】检查Redis取消标志
                    if script_id:
                        try:
                            is_cancelled = await TaskCancellationManager.check_cancellation_flag(script_id)
                            if is_cancelled:
                                logger.info(
                                    'Task cancelled via Redis flag, stopping video generation',
                                    script_id=script_id,
                                    current=i + 1,
                                    total=len(video_segment_ids)
                                )
                                break  # 停止生成循环
                        except Exception as e:
                            logger.warning('Failed to check Redis cancellation flag', error=str(e))
                        
                        # 更新任务心跳
                        try:
                            await TaskCancellationManager.set_task_heartbeat(script_id, 'video')
                        except Exception as e:
                            logger.warning('Failed to set task heartbeat', error=str(e))
                    
                    logger.info(
                        'Generating video segment serially',
                        current=i + 1,
                        total=len(video_segment_ids),
                        video_segment_id=video_segment_id
                    )
                    async with _VIDEO_GENERATION_SEMAPHORE:
                        # 标记为 generating（用于前端展示排队 -> 运行中）
                        async with async_session_maker() as db:
                            try:
                                result = await db.execute(
                                    select(VideoSegment).where(VideoSegment.id == video_segment_id)
                                )
                                vs = result.scalar_one_or_none()
                                if vs and vs.status == VideoStatus.PENDING:
                                    vs.status = VideoStatus.GENERATING
                                    await db.commit()
                            except Exception:
                                pass
                        await self._generate_single_video_with_session(
                            video_segment_id
                        )
            else:
                # 其他模型: 并发生成
                logger.info(
                    'Using parallel generation',
                    total_segments=len(video_segment_ids)
                )
                tasks = []
                for video_segment_id in video_segment_ids:
                    async def _run_with_limit(vs_id: int) -> None:
                        async with _VIDEO_GENERATION_SEMAPHORE:
                            # 标记为 generating（用于前端展示排队 -> 运行中）
                            async with async_session_maker() as db:
                                try:
                                    result = await db.execute(
                                        select(VideoSegment).where(VideoSegment.id == vs_id)
                                    )
                                    vs = result.scalar_one_or_none()
                                    if vs and vs.status == VideoStatus.PENDING:
                                        vs.status = VideoStatus.GENERATING
                                        await db.commit()
                                except Exception:
                                    pass
                            await self._generate_single_video_with_session(vs_id)

                    task = _run_with_limit(video_segment_id)
                    tasks.append(task)

                # 等待所有任务完成
                await asyncio.gather(*tasks, return_exceptions=True)
                
        except Exception as e:
            logger.error(
                'Error in background video generation',
                error=str(e),
                exc_info=True
            )

    async def _generate_single_video_with_session(
        self, video_segment_id: int
    ) -> None:
        """生成单个视频片段（使用独立的数据库会话）.

        Args:
            video_segment_id: 视频片段ID
        """
        async with async_session_maker() as db:
            try:
                # 查询视频片段对象
                result = await db.execute(
                    select(VideoSegment).where(VideoSegment.id == video_segment_id)
                )
                video_segment = result.scalar_one_or_none()

                if not video_segment:
                    logger.error(
                        'Video segment not found',
                        video_segment_id=video_segment_id
                    )
                    return

                # 规则：最后一个视频段必须固定使用豆包模型（唯一支持 4-12s 精准控时长）
                # - 强制把该段 model 设为豆包
                # - 禁用降级到其他模型（否则总时长不可控）
                is_last_segment = False
                try:
                    max_idx_result = await db.execute(
                        select(func.max(VideoSegment.segment_index)).where(
                            VideoSegment.script_id == video_segment.script_id
                        )
                    )
                    max_idx = max_idx_result.scalar_one_or_none()
                    if max_idx is not None and int(video_segment.segment_index) == int(max_idx):
                        is_last_segment = True
                except Exception:
                    is_last_segment = False

                if is_last_segment:
                    if video_segment.model != DOUBAO_SEEDANCE_1_5_PRO_MODEL_ID:
                        video_segment.model = DOUBAO_SEEDANCE_1_5_PRO_MODEL_ID
                        await db.commit()
                
                # 检查是否已被用户取消（状态为 failed 且错误信息包含"用户取消"）
                if video_segment.status == 'failed':
                    if video_segment.error_message and '用户取消' in video_segment.error_message:
                        logger.info(
                            'Video generation cancelled by user, skipping',
                            video_segment_id=video_segment_id
                        )
                        return  # 跳过这个视频片段

                # 查询该脚本的所有关键帧（用于构建参考图）
                keyframes_result = await db.execute(
                    select(Keyframe)
                    .where(Keyframe.script_id == video_segment.script_id)
                    .where(Keyframe.status == KeyframeStatus.COMPLETED)
                    .order_by(Keyframe.segment_id)
                )
                all_keyframes = list(keyframes_result.scalars().all())

                # 调用视频生成API（获取第三方URL）
                # 使用模型降级机制 + 重试机制
                has_first_frame = bool(video_segment.first_frame_url)
                fallback_models = (
                    [DOUBAO_SEEDANCE_1_5_PRO_MODEL_ID]
                    if is_last_segment
                    else self._get_video_fallback_models(video_segment.model, has_first_frame)
                )
                third_party_video_url = None
                last_error = None
                used_model = video_segment.model
                max_retries = 2  # 每个模型最多尝试2次（失败后重试1次）
                
                for current_model in fallback_models:
                    model_succeeded = False
                    
                    for attempt in range(max_retries):
                        try:
                            retry_count = attempt + 1
                            logger.info(
                                'Calling video generation API',
                                video_segment_id=video_segment_id,
                                model=current_model,
                                attempt=retry_count,
                                max_retries=max_retries,
                                has_first_frame=has_first_frame
                            )
                            
                            # 对“首帧参考模型”（豆包/即梦），参考图始终取“本段关键帧”：
                            # - 新生成的段：first_frame_url 已是本段关键帧
                            # - 从其他模型降级到豆包/即梦：last_frame_url 通常就是本段关键帧（segment_i）
                            effective_first_frame_url = video_segment.first_frame_url
                            effective_last_frame_url = video_segment.last_frame_url
                            if self._is_first_frame_reference_model(current_model):
                                effective_first_frame_url = (
                                    video_segment.last_frame_url
                                    or video_segment.first_frame_url
                            )
                                effective_last_frame_url = None
                            
                            third_party_video_url = await self._call_video_generation_api(
                                model=current_model,
                                prompt=video_segment.prompt,
                                first_frame_url=effective_first_frame_url,
                                last_frame_url=effective_last_frame_url,
                                aspect_ratio=video_segment.aspect_ratio,
                                duration=video_segment.duration,
                                all_keyframes=all_keyframes
                            )
                            
                            if third_party_video_url:
                                used_model = current_model
                                if current_model != video_segment.model:
                                    logger.info(
                                        'Video model fallback successful',
                                        video_segment_id=video_segment_id,
                                        original_model=video_segment.model,
                                        used_model=current_model
                                    )
                                model_succeeded = True
                                break  # 成功，跳出重试循环
                                
                        except Exception as e:
                            error_msg = str(e).lower()
                            last_error = e
                            
                            # 检查是否是内容审查错误（应该立即切换模型，不重试）
                            if ('safety' in error_msg or '审查' in error_msg or 'blocked' in error_msg or 
                                'moderation' in error_msg or 'violate' in error_msg or 'policies' in error_msg):
                                logger.warning(
                                    'Video content blocked by safety filter, switching model immediately',
                                    video_segment_id=video_segment_id,
                                    failed_model=current_model,
                                    error=str(e)
                                )
                                # 内容审查错误，不重试当前模型，直接尝试下一个模型
                                break
                            # 检查是否是模型维护错误
                            elif 'maintenance' in error_msg or 'model maintenance' in error_msg:
                                logger.warning(
                                    'Video model under maintenance, trying fallback model',
                                    video_segment_id=video_segment_id,
                                    failed_model=current_model,
                                    error=str(e)
                                )
                                # 模型维护错误，不重试当前模型，直接尝试下一个模型
                                break
                            else:
                                # 其他错误，重试当前模型
                                if retry_count < max_retries:
                                    logger.warning(
                                        'Video generation failed, retrying',
                                        video_segment_id=video_segment_id,
                                        model=current_model,
                                        attempt=retry_count,
                                        max_retries=max_retries,
                                        error=str(e)
                                    )
                                    # 重试中：不把技术错误写入 error_message（避免前端展示“失败/重试”告警）
                                    
                                    await asyncio.sleep(5 * retry_count)  # 视频生成等待时间长一点
                                else:
                                    logger.error(
                                        'Video generation failed after retries, trying next model',
                                        video_segment_id=video_segment_id,
                                        model=current_model,
                                        error=str(e)
                                    )
                                    # 重试失败，跳出重试循环，尝试下一个模型
                                    break
                    
                    if model_succeeded:
                        break  # 成功，跳出模型降级循环
                
                if not third_party_video_url:
                    raise Exception(f'视频生成失败（所有模型均不可用，每个模型已尝试{max_retries}次）: {str(last_error)}')

                logger.info(
                    'Video generated from API',
                    video_segment_id=video_segment_id,
                    third_party_url=third_party_video_url
                )

                # 上传到 OSS（同步等待）
                final_video_url = third_party_video_url
                try:
                    # 使用信号量控制上传并发
                    oss_url = await upload_limiter.upload_video(
                        self._upload_video_to_oss,
                        video_segment_id,
                        third_party_video_url
                    )
                    final_video_url = oss_url
                    logger.info(
                        'Video uploaded to OSS successfully',
                        video_segment_id=video_segment_id,
                        oss_url=oss_url
                    )
                except Exception as upload_error:
                    logger.error(
                        'Failed to upload video to OSS, falling back to 3rd party URL',
                        video_segment_id=video_segment_id,
                        error=str(upload_error)
                    )
                    # 上传失败，降级使用第三方URL

                # 更新视频片段记录
                video_segment.video_url = final_video_url
                video_segment.status = VideoStatus.COMPLETED
                video_segment.error_message = None

                await db.commit()

                logger.info(
                    'Video segment completed successfully',
                    video_segment_id=video_segment_id,
                    video_url=final_video_url
                )

                # 触发音频生成流水线（异步，不阻塞视频生成）
                # 一步生成/对话式重生成场景：若音频已存在且完成，默认不重做音频（video_only）。
                try:
                    has_audio = bool(getattr(video_segment, "audio_url", None))
                    audio_done = getattr(video_segment, "audio_status", None) == AudioStatus.COMPLETED
                except Exception:
                    has_audio = False
                    audio_done = False

                if not (has_audio and audio_done):
                    asyncio.create_task(
                        self._generate_audio_for_video_segment(video_segment_id)
                    )
                else:
                    logger.info(
                        "Skip audio generation for video segment (audio already completed)",
                        video_segment_id=video_segment_id,
                    )

            except Exception as e:
                logger.error(
                    'Failed to generate video',
                    video_segment_id=video_segment_id,
                    error=str(e),
                    exc_info=True
                )

                try:
                    # 重新查询视频片段以更新状态
                    result = await db.execute(
                        select(VideoSegment).where(VideoSegment.id == video_segment_id)
                    )
                    video_segment_to_update = result.scalar_one_or_none()

                    if video_segment_to_update:
                        video_segment_to_update.status = VideoStatus.FAILED
                        # 将网络/TLS 等不稳定错误对外表现为“维护中”，避免暴露技术细节
                        err_text = str(e or '')
                        low = err_text.lower()
                        if (
                            'tls' in low
                            or 'ssl' in low
                            or '_ssl.c' in low
                            or 'eof' in low
                            or 'connection has been closed' in low
                            or 'connection reset' in low
                        ):
                            video_segment_to_update.error_message = '模型维护中'
                        else:
                            video_segment_to_update.error_message = err_text
                        await db.commit()
                except Exception as commit_error:
                    logger.error(
                        'Failed to update video segment status',
                        video_segment_id=video_segment_id,
                        error=str(commit_error),
                        exc_info=True
                    )

    async def _generate_audio_for_video_segment(self, video_segment_id: int) -> None:
        """视频段完成后：探测真实时长→调用TTS→写回audio_url等字段。

        注意：该任务不应影响视频状态；失败只更新 audio_* 字段。
        """
        from src.services.tts_service import get_tts_service
        import tempfile
        import httpx

        async with async_session_maker() as db:
            try:
                result = await db.execute(
                    select(VideoSegment).where(VideoSegment.id == video_segment_id)
                )
                video_segment = result.scalar_one_or_none()
                if not video_segment:
                    return

                if not video_segment.video_url or video_segment.status != VideoStatus.COMPLETED:
                    return

                # 标记音频生成中
                video_segment.audio_status = AudioStatus.GENERATING
                video_segment.audio_error_message = None
                await db.commit()

                # 取该段 narration
                script_result = await db.execute(
                    select(Script).where(Script.id == video_segment.script_id)
                )
                script = script_result.scalar_one_or_none()
                narration_text = ""
                if script and script.content:
                    try:
                        segments = parse_script(script.content)
                        normal_segments = [s for s in segments if not s.is_frame_0]
                        if 0 <= int(video_segment.segment_index) < len(normal_segments):
                            narration_text = str(normal_segments[int(video_segment.segment_index)].narration or "").strip()
                    except Exception as e:
                        logger.warning(
                            "Failed to parse script for narration (tts pipeline)",
                            script_id=video_segment.script_id,
                            error=str(e),
                        )

                if not narration_text:
                    video_segment.audio_status = AudioStatus.FAILED
                    video_segment.audio_error_message = "口播文案为空，跳过配音生成"
                    await db.commit()
                    return

                # 下载视频到临时文件并 ffprobe 读取真实时长
                duration_sec = 0.0
                with tempfile.TemporaryDirectory() as tmp_dir:
                    video_path = os.path.join(tmp_dir, f"vs_{video_segment_id}.mp4")
                    async with httpx.AsyncClient(timeout=60.0) as client:
                        resp = await client.get(video_segment.video_url)
                        resp.raise_for_status()
                        with open(video_path, "wb") as f:
                            f.write(resp.content)

                    probe_info = self._ffprobe_video_file(video_path)
                    duration_sec = float(probe_info.get("duration_sec") or 0.0)

                if duration_sec <= 0:
                    # 兜底使用数据库 duration
                    duration_sec = float(video_segment.duration or 0.0)

                video_segment.audio_duration_sec = float(duration_sec)
                await db.commit()

                tts_service = get_tts_service()
                tts_result = await tts_service.synthesize_qwen3_tts_flash(
                    text=narration_text,
                    target_duration_sec=duration_sec,
                )

                video_segment.audio_url = str(tts_result.get("url") or "")
                video_segment.audio_status = AudioStatus.COMPLETED
                video_segment.audio_error_message = None
                await db.commit()

                logger.info(
                    "Video segment audio generated",
                    video_segment_id=video_segment_id,
                    duration_sec=duration_sec,
                    audio_url=video_segment.audio_url,
                )

            except Exception as e:
                # tenacity 的 RetryError 包裹会掩盖真实错误，这里提取底层异常用于日志/落库
                root_error = str(e)
                try:
                    from tenacity import RetryError  # type: ignore

                    if isinstance(e, RetryError):
                        last_exc = e.last_attempt.exception()  # type: ignore[attr-defined]
                        if last_exc:
                            root_error = str(last_exc)
                except Exception:
                    pass

                logger.error(
                    "Failed to generate audio for video segment",
                    video_segment_id=video_segment_id,
                    error=root_error,
                    exc_info=True,
                )
                try:
                    result = await db.execute(
                        select(VideoSegment).where(VideoSegment.id == video_segment_id)
                    )
                    vs_update = result.scalar_one_or_none()
                    if vs_update:
                        vs_update.audio_status = AudioStatus.FAILED
                        vs_update.audio_error_message = root_error
                        await db.commit()
                except Exception as commit_error:
                    logger.error(
                        "Failed to update audio status",
                        video_segment_id=video_segment_id,
                        error=str(commit_error),
                        exc_info=True,
                    )

    async def _upload_video_to_oss(self, video_segment_id: int, video_url: str) -> str:
        """上传视频到OSS并返回URL.

        Args:
            video_segment_id: 视频片段ID
            video_url: 原视频URL

        Returns:
            OSS URL

        Raises:
            Exception: 上传失败
        """
        try:
            filename = (
                f"video_segment_{video_segment_id}_"
                f"{datetime.now().strftime('%Y%m%d%H%M%S')}.mp4"
            )

            oss_upload_result = None
            max_retries = 3
            last_error: Optional[Exception] = None

            for attempt in range(max_retries):
                try:
                    oss_upload_result = await oss_service.upload_from_url(
                        url=video_url,
                        filename=filename,
                        category="videos",
                    )
                    break
                except Exception as exc:
                    last_error = exc
                    retry_count = attempt + 1
                    if retry_count < max_retries:
                        wait_time = 5 * retry_count
                        logger.warning(
                            "Video upload to OSS failed, retrying",
                            attempt=retry_count,
                            error=str(exc),
                            video_segment_id=video_segment_id,
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(
                            "Video upload to OSS failed after retries",
                            error=str(exc),
                            video_segment_id=video_segment_id,
                        )

            if not oss_upload_result:
                raise Exception(
                    "Failed to upload video to OSS after "
                    f"{max_retries} retries: {str(last_error)}"
                )

            return str(oss_upload_result["url"])
        except Exception as exc:
            logger.error(
                "OSS video upload failed",
                video_segment_id=video_segment_id,
                error=str(exc),
                exc_info=True,
            )
            raise

    async def _call_video_generation_api(
        self,
        model: str,
        prompt: str,
        first_frame_url: Optional[str],
        last_frame_url: Optional[str],
        aspect_ratio: str,
        duration: float,
        all_keyframes: Optional[List[Keyframe]] = None
    ) -> str:
        """调用第三方视频生成API.

        Args:
            model: 模型名称
            prompt: 提示词
            first_frame_url: 首帧URL
            last_frame_url: 尾帧URL
            aspect_ratio: 视频比例
            duration: 时长
            all_keyframes: 所有关键帧列表（用于构建参考图）

        Returns:
            生成的视频URL

        Raises:
            Exception: API调用失败
        """
        # 判断使用哪个API（不同模型使用不同鉴权方式）
        if model == DOUBAO_SEEDANCE_1_5_PRO_MODEL_ID or model.startswith('doubao-seedance-1-5-pro'):
            return await self._call_doubao_seedance_ark_api(
                model=model,
                prompt=prompt,
                first_frame_url=first_frame_url,
                last_frame_url=last_frame_url,
                aspect_ratio=aspect_ratio,
                duration=duration,
            )
        elif model.startswith('sora'):
            if not self.api_key:
                raise Exception('GRSAI API密钥未配置')
            # sora-2-ref 使用首帧作为参考图
            ref_url = first_frame_url if model == 'sora-2-ref' else last_frame_url
            return await self._call_sora_api(
                model, prompt, ref_url, aspect_ratio, duration
            )
        elif model.startswith('veo'):
            if not self.api_key:
                raise Exception('GRSAI API密钥未配置')
            return await self._call_veo_api(
                model, prompt, first_frame_url, last_frame_url, aspect_ratio, all_keyframes
            )
        elif model.startswith('jimeng'):
            return await self._call_jimeng_api(
                model, prompt, first_frame_url, last_frame_url, duration
            )
        else:
            raise Exception(f'不支持的模型: {model}')

    async def _call_doubao_seedance_ark_api(
        self,
        *,
        model: str,
        prompt: str,
        first_frame_url: Optional[str],
        last_frame_url: Optional[str],
        aspect_ratio: str,
        duration: float,
    ) -> str:
        """调用火山方舟 Seedance（Doubao）视频生成 API。

        说明：
        - 使用 Ark API Key（Authorization: Bearer）
        - 默认生成无声视频（generate_audio=false）
        - 参数通过文本命令注入（--ratio / --dur），详见火山文档
        - --dur 与前端传入的 duration 对齐（取整 + 范围兜底）
        """
        from src.services.volc_ark_video_service import volc_ark_video_service

        # 按你的要求：以“参考图（首帧）图生视频”方式生成（仅传 1 张参考图）
        reference_image_url = first_frame_url or last_frame_url

        # 与前端传入 duration 对齐：Ark 的 --dur 通常需要整数秒，这里取整并限制范围
        # 兜底范围：4-12 秒（当前仅豆包模型支持 4-12s 精准控时长）
        try:
            target_duration = int(round(float(duration)))
        except Exception:
            target_duration = 10
        target_duration = max(4, min(12, target_duration))

        prompt_with_params = f"{prompt} --ratio {aspect_ratio} --dur {target_duration}"

        return await volc_ark_video_service.generate_video(
            model=model,
            prompt=prompt_with_params,
            first_frame_url=reference_image_url,
            last_frame_url=None,
            generate_audio=False,
        )

    async def _call_sora_api(
        self,
        model: str,
        prompt: str,
        reference_url: Optional[str],
        aspect_ratio: str,
        duration: float
    ) -> str:
        """调用Sora API生成视频.

        Args:
            model: 模型名称
            prompt: 提示词
            reference_url: 参考图片URL
            aspect_ratio: 视频比例
            duration: 时长

        Returns:
            视频URL
        """
        url = f'{self.base_url}/v1/video/sora-video'
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }

        # 映射模型名称
        api_model = "sora-2" if model == "sora-2-ref" else model

        payload = {
            'model': api_model,
            'prompt': prompt,
            'aspectRatio': aspect_ratio,
            'duration': int(duration),
            'size': 'small',
            'shutProgress': True,
            'webHook': '-1'  # 使用轮询方式
        }

        if reference_url:
            payload['url'] = reference_url

        async with httpx.AsyncClient(timeout=600.0) as client:
            # 提交任务
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()

            if result.get('code') != 0:
                raise Exception(f"Sora API错误: {result.get('msg')}")

            task_id = result['data']['id']

            # 轮询获取结果
            result_url = f'{self.base_url}/v1/draw/result'
            max_attempts = 120  # 最多轮询120次（10分钟）
            attempt = 0

            while attempt < max_attempts:
                await asyncio.sleep(5)  # 每5秒轮询一次

                result_response = await client.post(
                    result_url,
                    json={'id': task_id},
                    headers=headers
                )
                result_response.raise_for_status()
                result_data = result_response.json()

                if result_data.get('code') != 0:
                    raise Exception(f"获取结果失败: {result_data.get('msg')}")

                data = result_data['data']
                status = data.get('status')

                logger.info(
                    'Sora API polling',
                    task_id=task_id,
                    status=status,
                    progress=data.get('progress'),
                    attempt=attempt
                )

                if status == 'succeeded':
                    results = data.get('results', [])
                    if results and results[0].get('url'):
                        return results[0]['url']
                    raise Exception('视频生成成功但未返回URL')
                elif status == 'failed':
                    error = data.get('error', '未知错误')
                    raise Exception(f'视频生成失败: {error}')

                attempt += 1

            raise Exception('视频生成超时')

    @retry(
        retry=retry_if_exception_type(VeoQuotaExhaustedError),
        stop=stop_after_attempt(10),
        wait=wait_exponential(multiplier=2, min=5, max=60),
        before_sleep=lambda retry_state: logger.warning(
            "Veo quota exhausted, retrying...",
            attempt=retry_state.attempt_number,
            next_wait=retry_state.next_action.sleep
        )
    )
    async def _submit_veo_task(
        self,
        client: httpx.AsyncClient,
        url: str,
        payload: Dict[str, Any],
        headers: Dict[str, str]
    ) -> Dict[str, Any]:
        """提交Veo任务（带重试机制）."""
        try:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()

            if result.get('code') != 0:
                msg = str(result.get('msg', ''))
                # 检查是否为配额不足或限流错误
                # error code 429: Resource has been exhausted
                # reason: PUBLIC_ERROR_USER_REQUESTS_THROTTLED
                if (
                    '429' in msg or 
                    'RESOURCE_EXHAUSTED' in msg or 
                    'throttled' in msg.lower() or
                    'quota' in msg.lower()
                ):
                    raise VeoQuotaExhaustedError(f"Veo配额耗尽/限流: {msg}")
                
                # 其他错误直接抛出
                raise Exception(f"Veo API错误: {msg}")
            
            return result
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                 raise VeoQuotaExhaustedError(f"HTTP 429 Too Many Requests: {e.response.text}")
            raise

    async def _call_veo_api(
        self,
        model: str,
        prompt: str,
        first_frame_url: Optional[str],
        last_frame_url: Optional[str],
        aspect_ratio: str,
        all_keyframes: Optional[List[Keyframe]] = None
    ) -> str:
        """调用Veo API生成视频.

        对于veo3.1-fast-ref模型，使用参考图模式（urls）。
        参考图顺序：[前2个关键帧, 前1个关键帧, 当前关键帧]

        Args:
            model: 模型名称
            prompt: 提示词（需要是英文）
            first_frame_url: 首帧URL
            last_frame_url: 尾帧URL
            aspect_ratio: 视频比例
            all_keyframes: 所有关键帧列表（用于构建参考图）

        Returns:
            视频URL
        """
        url = f'{self.base_url}/v1/video/veo'
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }

        # 映射模型名称
        api_model = "veo3.1-fast" if model == "veo3.1-fast-ref" else model

        payload = {
            'model': api_model,
            'prompt': prompt,
            'aspectRatio': aspect_ratio,
            'shutProgress': True,
            'webHook': '-1'  # 使用轮询方式
        }

        # veo3.1-fast-ref 使用参考图模式
        if model == 'veo3.1-fast-ref' and all_keyframes:
            # 使用 first_frame_url 作为当前帧（因为它是视频生成的起点）
            reference_urls = self._build_prev_reference_urls(
                first_frame_url, all_keyframes
            )
            if reference_urls:
                payload['urls'] = reference_urls
                logger.info(
                    'Using reference images for veo3.1-fast-ref',
                    reference_count=len(reference_urls),
                    urls=reference_urls
                )
            else:
                logger.warning(
                    'Failed to build reference URLs for veo3.1-fast-ref, using firstFrameUrl',
                    first_frame_url=first_frame_url
                )
                if first_frame_url:
                    payload['firstFrameUrl'] = first_frame_url
        
        # 旧的 veo3.1-fast 逻辑 (保留或根据需要移除，这里保留以防兼容)
        elif model == 'veo3.1-fast' and all_keyframes:
            reference_urls = self._build_reference_urls(
                first_frame_url, last_frame_url, all_keyframes
            )
            if reference_urls:
                payload['urls'] = reference_urls
                logger.info(
                    'Using reference images for veo3.1-fast',
                    reference_count=len(reference_urls),
                    urls=reference_urls
                )
            else:
                # 如果无法构建参考图，降级使用首尾帧
                logger.warning(
                    'Failed to build reference URLs, fallback to first/last frame',
                    first_frame_url=first_frame_url,
                    last_frame_url=last_frame_url
                )
                if first_frame_url:
                    payload['firstFrameUrl'] = first_frame_url
                if last_frame_url:
                    payload['lastFrameUrl'] = last_frame_url
        else:
            # 其他Veo模型使用首尾帧模式
            if first_frame_url:
                payload['firstFrameUrl'] = first_frame_url
            if last_frame_url:
                payload['lastFrameUrl'] = last_frame_url

        async with httpx.AsyncClient(timeout=600.0) as client:
            # 提交任务（带重试）
            result = await self._submit_veo_task(client, url, payload, headers)

            task_id = result['data']['id']

            # 轮询获取结果
            result_url = f'{self.base_url}/v1/draw/result'
            max_attempts = 120  # 最多轮询120次（10分钟）
            attempt = 0

            while attempt < max_attempts:
                await asyncio.sleep(5)  # 每5秒轮询一次

                result_response = await client.post(
                    result_url,
                    json={'id': task_id},
                    headers=headers
                )
                result_response.raise_for_status()
                result_data = result_response.json()

                if result_data.get('code') != 0:
                    raise Exception(f"获取结果失败: {result_data.get('msg')}")

                data = result_data['data']
                status = data.get('status')

                if status == 'succeeded':
                    video_url = data.get('url')
                    if video_url:
                        return video_url
                    raise Exception('视频生成成功但未返回URL')
                elif status == 'failed':
                    error = data.get('error', '未知错误')
                    raise Exception(f'视频生成失败: {error}')

                attempt += 1

            raise Exception('视频生成超时')

    def _build_prev_reference_urls(
        self,
        current_frame_url: Optional[str],
        all_keyframes: List[Keyframe]
    ) -> List[str]:
        """构建前序参考图URL列表（用于veo3.1-fast-ref）.

        逻辑：
        1. 找到 current_frame_url 对应的关键帧位置
        2. 获取该位置及前两个位置的关键帧
        3. 返回顺序：[前2个, 前1个, 当前]

        Args:
            current_frame_url: 当前关键帧URL（视频生成起点）
            all_keyframes: 所有关键帧列表

        Returns:
            参考图URL列表
        """
        if not current_frame_url:
            return []

        # 过滤特殊关键帧
        normal_keyframes = [
            kf for kf in all_keyframes
            if not kf.segment_id.endswith('_first_frame')
            and not kf.segment_id.endswith('_last_frame')
        ]

        if not normal_keyframes:
            return []

        # 找到当前关键帧索引
        current_index = -1
        for i, kf in enumerate(normal_keyframes):
            if kf.image_url == current_frame_url:
                current_index = i
                break

        if current_index == -1:
            return []

        reference_urls = []
        
        # 获取前两个关键帧（如果有）
        start_idx = max(0, current_index - 2)
        # 获取 [start_idx, current_index] 范围内的帧（包括当前帧）
        selected_keyframes = normal_keyframes[start_idx : current_index + 1]
        
        reference_urls = [kf.image_url for kf in selected_keyframes]

        return reference_urls

    def _build_reference_urls(
        self,
        first_frame_url: Optional[str],
        last_frame_url: Optional[str],
        all_keyframes: List[Keyframe]
    ) -> List[str]:
        """构建参考图URL列表（用于veo3.1-fast）.

        逻辑：
        1. 当前关键帧 = last_frame_url对应的关键帧
        2. 上一个关键帧 = 当前关键帧的前一个
        3. 下一个关键帧 = 当前关键帧的后一个

        返回顺序：[上一个, 当前, 下一个]
        最多3张图片

        Args:
            first_frame_url: 视频段落的起始帧URL（用于降级）
            last_frame_url: 视频段落的结束帧URL（当前关键帧）
            all_keyframes: 所有关键帧列表（已按segment_id排序）

        Returns:
            参考图URL列表，顺序为[上一个, 当前, 下一个]
        """
        reference_urls = []

        # 过滤掉first_frame和last_frame特殊关键帧
        normal_keyframes = [
            kf for kf in all_keyframes
            if not kf.segment_id.endswith('_first_frame')
            and not kf.segment_id.endswith('_last_frame')
        ]

        if not normal_keyframes:
            logger.warning('No normal keyframes found')
            return []

        # 找到当前关键帧（last_frame_url对应的关键帧）
        current_index = -1
        for i, kf in enumerate(normal_keyframes):
            if kf.image_url == last_frame_url:
                current_index = i
                break

        if current_index == -1:
            # 如果找不到，降级返回空（使用首尾帧模式）
            logger.warning(
                'Cannot find current keyframe by last_frame_url',
                last_frame_url=last_frame_url,
                available_urls=[kf.image_url for kf in normal_keyframes[:3]]
            )
            return []

        current_kf = normal_keyframes[current_index]

        # 获取上一个关键帧
        prev_kf = normal_keyframes[current_index - 1] if current_index > 0 else None

        # 获取下一个关键帧
        next_kf = (
            normal_keyframes[current_index + 1]
            if current_index < len(normal_keyframes) - 1
            else None
        )

        # 构建参考图列表：[上一个, 当前, 下一个]
        if prev_kf:
            reference_urls.append(prev_kf.image_url)

        reference_urls.append(current_kf.image_url)

        if next_kf:
            reference_urls.append(next_kf.image_url)

        logger.info(
            'Built reference URLs for veo3.1-fast',
            current_segment=current_kf.segment_id,
            current_index=current_index,
            prev_segment=prev_kf.segment_id if prev_kf else None,
            next_segment=next_kf.segment_id if next_kf else None,
            reference_count=len(reference_urls)
        )

        return reference_urls[:3]  # 最多3张

    async def get_video_segments_by_script(
        self, script_id: int
    ) -> List[VideoSegmentResponse]:
        """获取脚本的所有视频片段.

        Args:
            script_id: 脚本ID

        Returns:
            视频片段列表（含narration）
        """
        # 获取视频片段
        result = await self.db.execute(
            select(VideoSegment)
            .where(VideoSegment.script_id == script_id)
            .order_by(VideoSegment.segment_index)
        )
        video_segments = list(result.scalars().all())
        
        # 获取 Script 以提取 narration
        script_result = await self.db.execute(
            select(Script).where(Script.id == script_id)
        )
        script = script_result.scalar_one_or_none()
        
        narration_map = {}
        video_desc_map = {}
        if script and script.content:
            try:
                segments = parse_script(script.content)
                # 建立 index -> narration 映射
                # 过滤掉第0帧
                normal_segments = [s for s in segments if not s.is_frame_0]
                for i, seg in enumerate(normal_segments):
                    if seg.narration:
                        narration_map[i] = seg.narration
                    if seg.video_desc:
                        video_desc_map[i] = seg.video_desc
            except Exception as e:
                logger.warning(
                    'Failed to parse script for narration',
                    script_id=script_id,
                    error=str(e)
                )
        
        responses = []
        for vs in video_segments:
            # 创建 Response 对象
            resp = VideoSegmentResponse.model_validate(vs)
            # 填充 narration
            if vs.segment_index in narration_map:
                resp.narration = narration_map[vs.segment_index]
            # 若数据库里 prompt 为空，则优先用脚本里的“视频”字段补齐，用于前端展示“视频描述”
            if (not getattr(resp, "prompt", None)) and (vs.segment_index in video_desc_map):
                resp.prompt = video_desc_map[vs.segment_index]
            responses.append(resp)
            
        return responses

    async def _call_jimeng_api(
        self,
        model: str,
        prompt: str,
        first_frame_url: Optional[str],
        last_frame_url: Optional[str],
        duration: float
    ) -> str:
        """调用火山即梦视频生成API.

        Args:
            model: 模型名称
            prompt: 提示词
            first_frame_url: 首帧URL
            last_frame_url: 兼容参数：旧首尾帧模式尾帧URL（当前首帧接口会忽略）
            duration: 视频时长

        Returns:
            视频URL

        Raises:
            Exception: API调用失败
        """
        from src.services.volc_jimeng_service import volc_jimeng_service

        if not first_frame_url:
            raise Exception('即梦视频生成需要首帧URL')

        logger.info(
            'Calling JiMeng video API',
            model=model,
            first_frame_url=first_frame_url,
            duration=duration,
            prompt_length=len(prompt)
        )

        video_url = await volc_jimeng_service.generate_video(
            prompt=prompt,
            first_frame_url=first_frame_url,
            last_frame_url=last_frame_url,
            duration=duration,
            model=model
        )

        logger.info(
            'JiMeng video API call completed',
            video_url=video_url
        )

        return video_url

    async def regenerate_video_segment(
        self,
        video_segment_id: int,
        model: Optional[str] = None
    ) -> VideoSegment:
        """重新生成单个视频片段.

        Args:
            video_segment_id: 视频片段ID
            model: 模型（可选，使用原模型）

        Returns:
            更新后的视频片段

        Raises:
            NotFoundError: 视频片段不存在
        """
        result = await self.db.execute(
            select(VideoSegment).where(VideoSegment.id == video_segment_id)
        )
        video_segment = result.scalar_one_or_none()

        if not video_segment:
            raise NotFoundError(f'视频片段不存在: {video_segment_id}')

        # 使用新模型或原模型
        if model:
            video_segment.model = model

        if str(video_segment.model or '').startswith('jimeng') and not bool(
            getattr(settings, 'enable_jimeng_video', False)
        ):
            raise ValidationError('即梦视频模型已被禁用（仅用于对比测试），如需启用请打开配置开关')

        # 更新状态为generating
        video_segment.status = VideoStatus.GENERATING
        video_segment.error_message = None
        video_segment.video_url = None

        await self.db.commit()

        # 启动后台任务重新生成
        asyncio.create_task(
            self._generate_single_video_with_session(video_segment_id)
        )

        return video_segment

    @staticmethod
    def _build_concat_filter_complex(
        video_infos: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """构建 FFmpeg filter_complex 用于拼接（含可选音频）.

        Args:
            video_infos: 每个输入视频的探测信息（按顺序），至少包含：
                - fps: float
                - total_frames: int
                - width: int
                - height: int
                - has_audio: bool
                - duration_sec: float
                - trimmed_duration_sec: float（对前 N-1 个视频去掉末帧后的时长）

        Returns:
            包含 filter_complex/has_audio/target_fps 的字典。
        """
        if not video_infos:
            raise ValueError('video_infos 不能为空')

        target_fps = float(video_infos[0]['fps'])
        target_width = int(video_infos[0]['width'])
        target_height = int(video_infos[0]['height'])

        has_audio = any(bool(info.get('has_audio')) for info in video_infos)

        filter_parts: List[str] = []
        concat_inputs: List[str] = []

        for idx, video_info in enumerate(video_infos):
            # 构建视频过滤器链：统一格式 + 去重复帧（前 N-1 段）+ 重置时间戳
            video_chain = f"[{idx}:v]"

            if (
                int(video_info['width']) != target_width
                or int(video_info['height']) != target_height
            ):
                video_chain += (
                    f"scale={target_width}:{target_height}:flags=lanczos,"
                )

            if abs(float(video_info['fps']) - target_fps) > 0.01:
                video_chain += f"fps={target_fps},"

            if idx < len(video_infos) - 1:
                total_frames = int(video_info.get('total_frames', 0))
                if total_frames > 1:
                    video_chain += f"trim=end_frame={total_frames - 1},"

            video_chain += "setpts=PTS-STARTPTS"
            filter_parts.append(f"{video_chain}[v{idx}]")

            if has_audio:
                # 音频：有则统一格式并按需裁剪；无则用静音补齐，保证 concat 不失败
                duration_key = (
                    'trimmed_duration_sec'
                    if idx < len(video_infos) - 1
                    else 'duration_sec'
                )
                duration_sec = float(video_info.get(duration_key) or 0.0)

                if duration_sec <= 0:
                    # 最后兜底：用帧数/帧率估算时长
                    fps = max(1e-6, float(video_info.get('fps') or target_fps))
                    frames = max(0, int(video_info.get('total_frames') or 0))
                    duration_sec = frames / fps

                duration_literal = f"{max(0.0, duration_sec):.6f}"

                if bool(video_info.get('has_audio')):
                    audio_chain = (
                        f"[{idx}:a]"
                        "aformat=sample_fmts=fltp:sample_rates=44100:"
                        "channel_layouts=stereo,"
                        f"atrim=duration={duration_literal},"
                        "asetpts=PTS-STARTPTS"
                    )
                else:
                    audio_chain = (
                        "anullsrc=r=44100:cl=stereo,"
                        f"atrim=duration={duration_literal},"
                        "asetpts=PTS-STARTPTS"
                    )

                filter_parts.append(f"{audio_chain}[a{idx}]")

            # concat 输入顺序：纯视频时只放视频；带音频时按 v,a 成对放
            concat_inputs.append(f"[v{idx}]")
            if has_audio:
                concat_inputs.append(f"[a{idx}]")

        if has_audio:
            filter_parts.append(
                f'{"".join(concat_inputs)}'
                f"concat=n={len(video_infos)}:v=1:a=1[outv][outa]"
            )
        else:
            filter_parts.append(
                f'{"".join(concat_inputs)}'
                f"concat=n={len(video_infos)}:v=1:a=0[outv]"
            )

        return {
            'filter_complex': ';'.join(filter_parts),
            'has_audio': has_audio,
            'target_fps': target_fps,
        }

    @staticmethod
    def _build_ffmpeg_concat_cmd(
        input_files: List[str],
        video_infos: List[Dict[str, Any]],
        output_path: str,
    ) -> Dict[str, Any]:
        """构建用于拼接导出的 FFmpeg 命令（不执行）.

        Args:
            input_files: 输入视频文件路径列表（按顺序）
            video_infos: 与 input_files 对应的探测信息
            output_path: 输出文件路径

        Returns:
            包含 ffmpeg_cmd/filter_complex/has_audio 的字典。
        """
        if len(input_files) != len(video_infos):
            raise ValueError('input_files 与 video_infos 长度不一致')

        build_result = VideoService._build_concat_filter_complex(video_infos)
        filter_complex = str(build_result['filter_complex'])
        has_audio = bool(build_result['has_audio'])
        target_fps = float(build_result['target_fps'])

        ffmpeg_cmd: List[str] = ['ffmpeg', '-y']
        for input_file in input_files:
            ffmpeg_cmd.extend(['-i', input_file])

        ffmpeg_cmd.extend(['-filter_complex', filter_complex, '-map', '[outv]'])
        if has_audio:
            ffmpeg_cmd.extend(['-map', '[outa]', '-shortest'])

        ffmpeg_cmd.extend(
            [
                '-c:v',
                'libx264',
                '-preset',
                'medium',
                '-crf',
                '20',
                '-profile:v',
                'high',
                '-level',
                '4.0',
                '-pix_fmt',
                'yuv420p',
                '-movflags',
                '+faststart',
                '-r',
                str(int(target_fps)),
            ]
        )

        if has_audio:
            ffmpeg_cmd.extend(
                [
                    '-c:a',
                    'aac',
                    '-b:a',
                    '192k',
                    '-ac',
                    '2',
                    '-ar',
                    '44100',
                ]
            )

        ffmpeg_cmd.append(output_path)

        return {
            'ffmpeg_cmd': ffmpeg_cmd,
            'filter_complex': filter_complex,
            'has_audio': has_audio,
            'target_fps': target_fps,
        }

    async def concat_videos_with_trim(
        self,
        video_segments: List[VideoSegment]
    ) -> bytes:
        """拼接多个视频片段并自动去除重复帧.
        
        核心逻辑：
        - 对于前 N-1 个视频，去掉最后一帧（避免与下一个视频的首帧重复）
        - 最后一个视频保持完整
        - 使用 FFmpeg 的 filter_complex 实现
        
        Args:
            video_segments: 视频片段列表（按顺序）
            
        Returns:
            拼接后的视频数据（bytes）
            
        Raises:
            Exception: FFmpeg 处理失败或未安装
        """
        import subprocess
        import tempfile
        import shutil
        
        # 检查 FFmpeg 是否已安装
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            subprocess.run(['ffprobe', '-version'], capture_output=True, check=True)
        except FileNotFoundError:
            raise Exception(
                'FFmpeg 未安装。请安装 FFmpeg:\n'
                'Mac: brew install ffmpeg\n'
                'Ubuntu: sudo apt-get install ffmpeg\n'
                'Windows: 从 https://ffmpeg.org/download.html 下载'
            )
        except subprocess.CalledProcessError as e:
            raise Exception(f'FFmpeg 检查失败: {str(e)}')
        
        if not video_segments:
            raise ValueError('没有视频片段可拼接')
        
        if len(video_segments) == 1:
            # 只有一个视频，直接下载返回
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(video_segments[0].video_url)
                response.raise_for_status()
                return response.content
        
        temp_dir = None
        try:
            # 创建临时目录
            temp_dir = tempfile.mkdtemp()
            input_files = []
            
            # 下载所有视频到临时文件
            async with httpx.AsyncClient(timeout=60.0) as client:
                for idx, segment in enumerate(video_segments):
                    if not segment.video_url:
                        raise ValueError(f'视频片段 {idx} 缺少 video_url')
                    
                    response = await client.get(segment.video_url)
                    response.raise_for_status()
                    
                    input_path = os.path.join(temp_dir, f'input_{idx}.mp4')
                    with open(input_path, 'wb') as f:
                        f.write(response.content)
                    input_files.append(input_path)
                    
                    logger.info(
                        'Downloaded video segment for concat',
                        segment_id=segment.id,
                        index=idx
                    )
            
            # 检测每个视频的信息（同时检测是否含音频）
            import json
            video_infos = []
            
            for idx, input_file in enumerate(input_files):
                probe_info = self._ffprobe_video_file(input_file)
                video_infos.append(probe_info)
                
                logger.info(
                    'Video info detected',
                    index=idx,
                    fps=probe_info['fps'],
                    total_frames=probe_info['total_frames'],
                    has_audio=bool(probe_info.get('has_audio')),
                    duration_sec=probe_info.get('duration_sec'),
                    is_vfr=bool(probe_info.get('is_vfr')),
                    resolution=f"{probe_info['width']}x{probe_info['height']}",
                )

            # 构建 FFmpeg 命令（策略：统一格式 + 去重复帧 +（可选）保留音频）
            output_path = os.path.join(temp_dir, 'output.mp4')

            build_cmd_result = self._build_ffmpeg_concat_cmd(
                input_files=input_files,
                video_infos=video_infos,
                output_path=output_path,
            )
            ffmpeg_cmd = build_cmd_result['ffmpeg_cmd']
            filter_complex = build_cmd_result['filter_complex']
            has_audio = bool(build_cmd_result['has_audio'])
            
            logger.info(
                'Running FFmpeg concat command',
                num_segments=len(input_files),
                has_audio=has_audio,
                filter_complex=filter_complex
            )
            
            # 执行 FFmpeg 命令
            result = subprocess.run(
                ffmpeg_cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            if result.returncode != 0:
                logger.error(
                    'FFmpeg concat failed',
                    returncode=result.returncode,
                    stderr=result.stderr
                )
                raise Exception(f'视频拼接失败: {result.stderr}')
            
            # 读取输出文件
            with open(output_path, 'rb') as f:
                concatenated_data = f.read()
            
            logger.info(
                'Video concatenation successful',
                num_segments=len(input_files),
                output_size_mb=len(concatenated_data) / (1024 * 1024)
            )
            
            return concatenated_data
            
        except subprocess.CalledProcessError as e:
            logger.error(
                'FFmpeg command error',
                error=str(e),
                stderr=e.stderr if hasattr(e, 'stderr') else None
            )
            raise Exception(f'FFmpeg 处理失败: {str(e)}')
        except Exception as e:
            logger.error(
                'Video concatenation error',
                error=str(e),
                error_type=type(e).__name__
            )
            raise
        finally:
            # 清理临时文件
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                    logger.info('Temp directory cleaned', temp_dir=temp_dir)
                except Exception as e:
                    logger.warning('Failed to clean temp directory', error=str(e))

    async def export_videos(self, script_id: int, export_type: str = 'separate') -> Dict[str, Any]:
        """导出脚本的所有视频.

        Args:
            script_id: 脚本ID
            export_type: 导出类型 ('separate' 或 'concatenated')

        Returns:
            包含下载URL和过期时间的字典

        Raises:
            NotFoundError: 脚本不存在或没有视频
        """
        # 获取所有已完成的视频片段
        result = await self.db.execute(
            select(VideoSegment)
            .where(VideoSegment.script_id == script_id)
            .where(VideoSegment.status == VideoStatus.COMPLETED)
            .order_by(VideoSegment.segment_index)
        )
        video_segments = list(result.scalars().all())

        if not video_segments:
            raise NotFoundError('没有已完成的视频片段可以导出')

        export_start = time.monotonic()

        logger.info(
            'Exporting videos',
            script_id=script_id,
            export_type=export_type,
            num_segments=len(video_segments)
        )

        # 若脚本曾被取消，但当前所有生成已完成，则清除取消标记，避免影响后续导出
        await self._clear_cancel_if_safe(script_id)

        # 导出阶段同样支持取消（避免“点击终止无效但提示成功”）
        await self._raise_if_cancelled(script_id)

        if export_type == 'concatenated':
            # 拼接导出前：必须确保所有段落配音已就绪，否则不允许导出
            audio_start = time.monotonic()
            await self.prepare_audio_for_export(
                script_id=script_id,
                timeout_sec=int(os.getenv('EXPORT_WAIT_AUDIO_TIMEOUT_SEC', '600')),
                poll_interval_sec=float(os.getenv('EXPORT_WAIT_AUDIO_POLL_SEC', '2')),
            )
            logger.info(
                "Export step done: prepare_audio_for_export",
                script_id=script_id,
                elapsed_sec=round(time.monotonic() - audio_start, 3),
            )

            # 拼接模式：自动合并所有视频并去除重复帧
            try:
                concat_start = time.monotonic()
                concatenated_data, segment_durations_sec = await self.concat_videos_with_trim_and_audio(
                    video_segments
                )
                logger.info(
                    "Export step done: concat_videos_with_trim_and_audio",
                    script_id=script_id,
                    num_segments=len(video_segments),
                    output_size_mb=round(len(concatenated_data) / (1024 * 1024), 3),
                    elapsed_sec=round(time.monotonic() - concat_start, 3),
                )
            except Exception as e:
                error_msg = str(e)
                if '404' in error_msg or 'Not Found' in error_msg:
                    raise ValidationError('部分视频文件已失效（404），请重新生成视频后再导出')
                raise

            # 生成并烧录字幕：必须成功，否则导出失败（避免页面上出现“无字幕成片”）
            try:
                burn_start = time.monotonic()
                burned_data = await self._burn_in_subtitles_for_concatenated_export(
                    script_id=script_id,
                    video_segments=video_segments,
                    segment_durations_sec=segment_durations_sec,
                    input_mp4_bytes=concatenated_data,
                )
                logger.info(
                    "Export step done: burn_in_subtitles",
                    script_id=script_id,
                    output_size_mb=round(len(burned_data) / (1024 * 1024), 3),
                    elapsed_sec=round(time.monotonic() - burn_start, 3),
                )
            except Exception as e:
                logger.error(
                    "Subtitle burn-in failed, abort export",
                    script_id=script_id,
                    error=str(e),
                    error_type=type(e).__name__,
                    exc_info=True,
                )
                raise ValidationError("字幕合成失败，请稍后重试")

            # 上传拼接后的视频到OSS
            upload_start = time.monotonic()
            video_buffer = BytesIO(burned_data)
            filename = f'video_concat_script_{script_id}_{datetime.now().strftime("%Y%m%d%H%M%S")}.mp4'

            upload_result = oss_service.upload_file(
                file_data=video_buffer,
                filename=filename,
                category='exports',
                content_type='video/mp4',
                force_download=True  # 强制下载而不是播放
            )
            
            logger.info(
                'Concatenated video uploaded',
                script_id=script_id,
                url=upload_result['url'],
                elapsed_sec=round(time.monotonic() - upload_start, 3),
            )

            logger.info(
                "Export completed: concatenated",
                script_id=script_id,
                total_elapsed_sec=round(time.monotonic() - export_start, 3),
            )
            
            return {
                'download_url': upload_result['url'],
                'expires_in': 3600  # 1小时
            }
        else:
            # 单独模式：打包所有视频为ZIP
            zip_start = time.monotonic()
            zip_buffer = BytesIO()
            successful_count = 0
            failed_urls = []
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                # 下载每个视频并添加到ZIP
                async with httpx.AsyncClient(timeout=60.0) as client:
                    for idx, segment in enumerate(video_segments):
                        if not segment.video_url:
                            continue

                        try:
                            # 下载视频
                            response = await client.get(segment.video_url)
                            response.raise_for_status()
                            video_data = response.content

                            # 添加到ZIP，文件名格式：segment_0.mp4
                            filename = f'segment_{segment.segment_index}.mp4'
                            zip_file.writestr(filename, video_data)
                            successful_count += 1

                            logger.info(
                                'Video added to zip',
                                segment_id=segment.id,
                                filename=filename
                            )
                        except httpx.HTTPStatusError as e:
                            if e.response.status_code == 404:
                                logger.warning(
                                    'Video URL not found (404), skipping',
                                    segment_id=segment.id,
                                    segment_index=segment.segment_index,
                                    url=segment.video_url
                                )
                                failed_urls.append(segment.segment_index)
                            else:
                                logger.error(
                                    'Failed to download video for export',
                                    segment_id=segment.id,
                                    error=str(e)
                                )
                        except Exception as e:
                            logger.error(
                                'Failed to download video for export',
                                segment_id=segment.id,
                                error=str(e)
                            )
            
            # 检查是否有成功的视频
            if successful_count == 0:
                raise ValidationError('所有视频文件均已失效，请重新生成视频后再导出')
            
            # 如果有部分失败，记录日志
            if failed_urls:
                logger.warning(
                    'Some videos failed to export',
                    total=len(video_segments),
                    successful=successful_count,
                    failed_segments=failed_urls
                )

            # 上传ZIP到OSS
            zip_buffer.seek(0)
            filename = f'videos_script_{script_id}_{datetime.now().strftime("%Y%m%d%H%M%S")}.zip'

            upload_result = oss_service.upload_file(
                file_data=zip_buffer,
                filename=filename,
                category='exports',
                content_type='application/zip'
            )

            logger.info(
                'Videos exported successfully',
                script_id=script_id,
                zip_url=upload_result['url'],
                elapsed_sec=round(time.monotonic() - zip_start, 3),
            )

            logger.info(
                "Export completed: separate",
                script_id=script_id,
                total_elapsed_sec=round(time.monotonic() - export_start, 3),
            )

            return {
                'download_url': upload_result['url'],
                'expires_in': 3600  # 1小时过期
            }

    async def _wait_for_audio_ready_before_export(
        self,
        *,
        script_id: int,
        video_segments: List[VideoSegment],
        timeout_sec: int,
        poll_interval_sec: float,
    ) -> None:
        """拼接导出前等待配音 ready.

        规则：
        - 只有当段落存在 `audio_url` 且 `audio_status==COMPLETED` 才认为 ready
        - 如果超时仍未 ready，则直接报错提示用户稍后重试导出（避免导出静音成片误导）
        """
        timeout_sec = max(1, int(timeout_sec))
        poll_interval_sec = max(0.2, float(poll_interval_sec))

        segment_ids = [s.id for s in video_segments]
        deadline = time.time() + float(timeout_sec)

        while True:
            await self._raise_if_cancelled(script_id)
            # 注意：export_videos() 可能在同一个 Session 内提前加载过 VideoSegment，
            # 这里必须强制刷新，避免 identity map 缓存导致“明明已完成但仍判定 not_ready”
            result = await self.db.execute(
                select(VideoSegment)
                .where(VideoSegment.id.in_(segment_ids))
                .order_by(VideoSegment.segment_index)
                .execution_options(populate_existing=True)
            )
            refreshed = list(result.scalars().all())

            not_ready = [
                s.segment_index
                for s in refreshed
                if not (bool(s.audio_url) and s.audio_status == AudioStatus.COMPLETED)
            ]

            if not not_ready:
                return

            if time.time() >= deadline:
                logger.warning(
                    'Audio not ready before export timeout, continue with silent fallback',
                    script_id=script_id,
                    not_ready_segment_indices=not_ready,
                    timeout_sec=timeout_sec,
                )
                return

            logger.info(
                'Waiting for audio generation before concatenated export',
                script_id=script_id,
                not_ready_segment_indices=not_ready,
            )
            await asyncio.sleep(poll_interval_sec)

    async def prepare_audio_for_export(
        self,
        *,
        script_id: int,
        timeout_sec: int,
        poll_interval_sec: float,
    ) -> None:
        """导出前强制准备配音（可听、重试一次、失败返回“模型维护中”）.

        规则：
        - 视频生成后音频允许并行生成，但导出前必须全部 ready
        - 对于 audio_status != COMPLETED 的段落：在导出前触发一次“补偿式生成”，失败则再重试一次
        - 超时/仍失败：抛出 ValidationError("模型维护中")
        """
        import time

        timeout_sec = max(1, int(timeout_sec))
        poll_interval_sec = max(0.2, float(poll_interval_sec))

        # 若脚本存在历史取消标记，但当前所有生成已完成，则清除取消标记，避免误伤音频合成步骤
        await self._clear_cancel_if_safe(script_id)

        # 取所有已完成视频段
        result = await self.db.execute(
            select(VideoSegment)
            .where(VideoSegment.script_id == script_id)
            .where(VideoSegment.status == VideoStatus.COMPLETED)
            .order_by(VideoSegment.segment_index)
        )
        segments = list(result.scalars().all())
        if not segments:
            raise ValidationError("没有可导出的已完成视频段")

        async def refresh() -> List[VideoSegment]:
            r = await self.db.execute(
                select(VideoSegment)
                .where(VideoSegment.script_id == script_id)
                .where(VideoSegment.status == VideoStatus.COMPLETED)
                .order_by(VideoSegment.segment_index)
                .execution_options(populate_existing=True)
            )
            return list(r.scalars().all())

        def not_ready(seg_list: List[VideoSegment]) -> List[VideoSegment]:
            return [
                s
                for s in seg_list
                if not (bool(getattr(s, "audio_url", None)) and s.audio_status == AudioStatus.COMPLETED)
            ]

        deadline = time.time() + float(timeout_sec)
        seg_list = await refresh()
        pending = not_ready(seg_list)

        if not pending:
            return

        # 第一次补偿式生成：对 not ready 的段落触发音频生成（并发受 limiter 控制）
        logger.info(
            "Preparing audio before export (attempt 1)",
            script_id=script_id,
            not_ready_segment_indices=[s.segment_index for s in pending],
        )
        for s in pending:
            # 串行触发（内部已有 TTS semaphore / HTTP 重试）
            await self._generate_audio_for_video_segment(s.id)

        # 等待 ready（到 deadline）
        while True:
            await self._raise_if_cancelled(script_id)
            seg_list = await refresh()
            pending = not_ready(seg_list)
            if not pending:
                return
            if time.time() >= deadline:
                break
            await asyncio.sleep(poll_interval_sec)

        # 第二次重试：只对仍未 ready 的段落再触发一次
        logger.warning(
            "Preparing audio before export (attempt 2)",
            script_id=script_id,
            not_ready_segment_indices=[s.segment_index for s in pending],
        )
        for s in pending:
            await self._generate_audio_for_video_segment(s.id)

        # 最终等待一小段（到 deadline）
        while True:
            await self._raise_if_cancelled(script_id)
            seg_list = await refresh()
            pending = not_ready(seg_list)
            if not pending:
                return
            if time.time() >= deadline:
                break
            await asyncio.sleep(poll_interval_sec)

        # 仍未就绪：按需求统一对外表现为“模型维护中”
        # 同步写回 DB，避免前端看到莫名其妙的 RetryError
        try:
            for s in pending:
                s.audio_status = AudioStatus.FAILED
                s.audio_error_message = "模型维护中"
            await self.db.commit()
        except Exception:
            pass
        raise ValidationError("模型维护中")

    async def _raise_if_cancelled(self, script_id: int) -> None:
        """若脚本已被用户取消，则中断当前耗时流程。"""
        from src.utils.redis_client import TaskCancellationManager

        # 先查 Redis（若可用）
        try:
            if await TaskCancellationManager.check_cancellation_flag(script_id):
                raise ValidationError("用户取消生成")
        except Exception:
            # Redis 不可用时降级为 DB 标记
            pass

        # DB 标记（cancelled_at）兜底
        from src.models.tables.script import Script as ScriptTable

        result = await self.db.execute(select(ScriptTable).where(ScriptTable.id == script_id))
        script = result.scalar_one_or_none()
        if script and getattr(script, "cancelled_at", None):
            raise ValidationError("用户取消生成")

    async def _clear_cancel_if_safe(self, script_id: int) -> None:
        """若脚本被标记取消，但当前不存在未完成任务，则清除 cancelled_at/Redis 标记。"""
        from src.models.tables.script import Script as ScriptTable
        from src.models.tables.keyframe import Keyframe
        from src.models.tables.video_segment import VideoSegment as VideoSegmentTable
        from src.utils.redis_client import TaskCancellationManager

        script_result = await self.db.execute(select(ScriptTable).where(ScriptTable.id == script_id))
        script = script_result.scalar_one_or_none()
        if not script or not getattr(script, "cancelled_at", None):
            return

        # 若还有未完成的关键帧/视频，则认为取消仍有效
        pending_kf = await self.db.execute(
            select(Keyframe.id)
            .where(Keyframe.script_id == script_id)
            .where(Keyframe.status.in_(["GENERATING", "PENDING"]))
            .limit(1)
        )
        if pending_kf.first():
            return

        pending_vs = await self.db.execute(
            select(VideoSegmentTable.id)
            .where(VideoSegmentTable.script_id == script_id)
            .where(VideoSegmentTable.status.in_(["GENERATING", "PENDING"]))
            .limit(1)
        )
        if pending_vs.first():
            return

        # 清除 DB 取消标记
        script.cancelled_at = None
        await self.db.commit()
        logger.info("Cleared cancelled_at for script", script_id=script_id)

        # 尝试清除 Redis 取消标记（最佳努力）
        try:
            await TaskCancellationManager.clear_cancellation_flag(script_id)
        except Exception:
            pass

    async def _burn_in_subtitles_for_concatenated_export(
        self,
        *,
        script_id: int,
        video_segments: List[VideoSegment],
        segment_durations_sec: List[float],
        input_mp4_bytes: bytes,
    ) -> bytes:
        """为拼接成片烧录 ASS 字幕并返回新 mp4 bytes.

        Args:
            script_id: 脚本ID
            video_segments: 视频段（按顺序）
            segment_durations_sec: 每段真实时长（秒），与 video_segments 顺序一致
            input_mp4_bytes: 已拼接、已替换音轨的视频 bytes
        """
        import subprocess
        import tempfile

        from src.services.subtitle_service import SubtitleService

        # 取口播文案（与音频生成流水线一致：按脚本解析 normal_segments）
        narrations: List[str] = []
        script_result = await self.db.execute(
            select(Script).where(Script.id == script_id)
        )
        script = script_result.scalar_one_or_none()
        if script and script.content:
            try:
                segments = parse_script(script.content)
                normal_segments = [s for s in segments if not s.is_frame_0]
                for vs in video_segments:
                    idx = int(vs.segment_index)
                    if 0 <= idx < len(normal_segments):
                        # 优先用口播文案；若口播为空（偶发：模型漏写/解析缺失），兜底使用正文 content，
                        # 避免出现“某些段没有字幕”的体验问题。
                        seg = normal_segments[idx]
                        text = str((seg.narration or "")).strip()
                        if not text:
                            text = str((seg.content or "")).strip()
                        narrations.append(text)
                    else:
                        narrations.append("")
            except Exception as e:
                logger.warning(
                    "Failed to parse script for subtitles, fallback to empty narrations",
                    script_id=script_id,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                narrations = ["" for _ in video_segments]
        else:
            narrations = ["" for _ in video_segments]

        subtitle_service = SubtitleService()
        empty_indices = [i for i, t in enumerate(narrations) if not str(t or "").strip()]
        if empty_indices:
            logger.warning(
                "Some segments have empty subtitle text (narration/content)",
                script_id=script_id,
                empty_segment_indices=empty_indices,
            )
        ass_text, events = subtitle_service.build_ass(
            narrations=narrations,
            segment_durations_sec=segment_durations_sec,
        )

        logger.info(
            "Subtitle ASS built for export",
            script_id=script_id,
            events_count=len(events),
            total_duration_sec=sum(segment_durations_sec),
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            in_path = os.path.join(tmp_dir, "input.mp4")
            ass_path = os.path.join(tmp_dir, "subtitles.ass")
            out_path = os.path.join(tmp_dir, "output.mp4")

            with open(in_path, "wb") as f:
                f.write(input_mp4_bytes)
            with open(ass_path, "w", encoding="utf-8") as f:
                f.write(ass_text)

            # burn-in subtitles：需要重编码视频；音频直接 copy
            # 注意：这里是 subprocess 直传参数（非 shell），不需要额外加引号；
            # 只需按 FFmpeg filtergraph 规则对路径做最小转义。
            ass_escaped = ass_path.replace("\\", "\\\\").replace(":", "\\:")
            # 指定 fontsdir，避免容器内 fontconfig 解析异常时找不到字体
            vf = f"subtitles={ass_escaped}:fontsdir=/usr/share/fonts"

            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                in_path,
                "-vf",
                vf,
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "copy",
                "-movflags",
                "+faststart",
                out_path,
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
            )
            if result.returncode != 0:
                raise Exception(
                    f"FFmpeg subtitle burn-in failed: {result.stderr}"
                )

            with open(out_path, "rb") as f:
                return f.read()

    @staticmethod
    def get_available_models() -> List[Dict[str, Any]]:
        """获取可用的视频生成模型列表（根据模型状态动态过滤）.

        Returns:
            模型信息列表（仅包含可用的模型）
        """
        from src.services.model_status_service import model_status_service
        
        # 所有可能的模型定义
        all_models = [
            {
                'id': 'sora-2',
                'name': '黑科技原理大片，适合拍物 [功效可视化/卖点证明]',
                'description': '支持多图参考，生成高质量视频',
                'supports_first_last_frame': True,
                'is_grsai': True  # 标记为 GRSAI 模型，需要检查状态
            },
            {
                'id': DOUBAO_SEEDANCE_1_5_PRO_MODEL_ID,
                'name': '豆包-影视级运动/情绪大片 [镜头语言/情绪张力]',
                'description': '火山方舟 Seedance 1.5 Pro（默认无声，电影级运动与情绪表现）',
                'supports_first_last_frame': True,
                'is_grsai': False  # Ark 模型，不走 GRSAI 状态检查
            },
            {
                'id': JIMENG_VIDEO_MODEL_ID,
                'name': '即梦-效果演变/对比模式 [Before & After/过程演示]',
                'description': '1080P高清，首帧图生视频（5/10秒），用于过程演变/对比表达',
                'supports_first_last_frame': False,
                'is_grsai': False  # 即梦不是 GRSAI 模型
            },
            # 参考图模式
            {
                'id': 'veo3.1-fast-ref',
                'name': '用户状态展示，适合拍人 [效果见证/情绪渲染]',
                'description': '使用当前帧及前2帧作为参考生成视频',
                'supports_first_last_frame': True,
                'is_grsai': True,
                # 'deprecated': True  # 恢复使用
            },
            {
                'id': 'sora-2-ref',
                'name': 'Sora 2 (参考图模式)',
                'description': '使用当前帧作为参考生成视频',
                'supports_first_last_frame': True,
                'is_grsai': True,
                'deprecated': True  # 标记为废弃
            }
            # 暂时隐藏的模型(不支持首尾帧控制):
            # {
            #     'id': 'sora-2',
            #     'name': 'Sora 2',
            #     'description': '支持单图参考，生成高质量视频',
            #     'supports_first_last_frame': False
            # },
            # {
            #     'id': 'veo3-fast',
            #     'name': 'Veo 3 Fast',
            #     'description': '快速生成，支持首尾帧控制',
            #     'supports_first_last_frame': True
            # },
            # {
            #     'id': 'veo3-pro',
            #     'name': 'Veo 3 Pro',
            #     'description': '专业级质量，支持首尾帧控制',
            #     'supports_first_last_frame': True
            # },
            # {
            #     'id': 'veo3.1-pro',
            #     'name': 'Veo 3.1 Pro',
            #     'description': '最新版本专业模式，支持首尾帧控制',
            #     'supports_first_last_frame': True
            # }
        ]
        
        # 过滤模型：
        # 1. 移除废弃的模型
        # 2. 检查 GRSAI 模型的可用性
        # 3. 检查即梦是否启用
        available_models = []
        jimeng_enabled = bool(getattr(settings, 'enable_jimeng_video', False))
        
        for model in all_models:
            # 跳过废弃的模型
            if model.get('deprecated', False):
                logger.debug(
                    "Skipping deprecated model",
                    model_id=model['id']
                )
                continue
            
            # 如果是即梦模型，检查是否启用
            if str(model['id']).startswith('jimeng') and not jimeng_enabled:
                logger.debug(
                    "Skipping jimeng model (not enabled)",
                    model_id=model['id']
                )
                continue
            
            # 如果是 GRSAI 模型，检查可用性
            if model.get('is_grsai', False):
                # 检查ID映射（某些衍生模型共享主模型状态）
                check_id = model['id']
                if check_id == 'veo3.1-fast-ref':
                    check_id = 'veo3.1-fast'
                
                if check_id in model_status_service.grsai_models.get("video", []):
                    if model_status_service.is_model_available(check_id):
                        # 模型可用，添加到列表
                        available_models.append({
                            'id': model['id'],
                            'name': model['name'],
                            'description': model['description'],
                            'supports_first_last_frame': model['supports_first_last_frame']
                        })
                        logger.debug(
                            "GRSAI video model is available",
                            model_id=model['id']
                        )
                    else:
                        # 模型不可用，跳过
                        logger.info(
                            "Skipping unavailable GRSAI video model in model list",
                            model_id=model['id']
                        )
                else:
                    # 不在 GRSAI 模型列表中，可能是新模型，默认添加
                    available_models.append({
                        'id': model['id'],
                        'name': model['name'],
                        'description': model['description'],
                        'supports_first_last_frame': model['supports_first_last_frame']
                    })
            else:
                # 非 GRSAI 模型（如即梦），直接添加
                available_models.append({
                    'id': model['id'],
                    'name': model['name'],
                    'description': model['description'],
                    'supports_first_last_frame': model['supports_first_last_frame']
                })
        
        # 如果所有模型都被过滤掉了，至少返回即梦模型（如果启用）
        if not available_models and jimeng_enabled:
            logger.warning("All video models filtered out, returning jimeng as fallback")
            available_models = [{
                'id': JIMENG_VIDEO_MODEL_ID,
                'name': '即梦-效果演变/对比模式 [Before & After/过程演示]',
                'description': '1080P高清，首帧图生视频（5/10秒），用于过程演变/对比表达',
                'supports_first_last_frame': False
            }]
        
        logger.info(
            "Returning available video models",
            total_count=len(available_models),
            model_ids=[m['id'] for m in available_models]
        )
        
        # 确保默认模型顺序稳定（前端会默认选第一个）
        preferred_order = ['veo3.1-fast-ref', 'sora-2', DOUBAO_SEEDANCE_1_5_PRO_MODEL_ID, JIMENG_VIDEO_MODEL_ID]
        order_index = {model_id: i for i, model_id in enumerate(preferred_order)}
        available_models.sort(key=lambda m: order_index.get(m['id'], 999))
        
        return available_models

    async def concat_videos_with_trim_and_audio(
        self,
        video_segments: List[VideoSegment],
    ) -> tuple[bytes, List[float]]:
        """拼接视频并为每段替换音轨（concatenated 导出专用）.

        策略：
        - 每段视频：下载到本地临时文件
        - 若存在 `audio_url` 且 `audio_status==COMPLETED`：下载配音 wav；否则使用静音
        - 使用 ffmpeg 为每段生成“无原音轨、仅包含配音音轨”的 mp4（同时规范化时间戳/帧率，降低 VFR 漂移）
        - 再使用现有 concat filter_complex 拼接，并去除重复帧
        """
        import subprocess
        import tempfile
        import shutil

        # 检查 FFmpeg 是否已安装
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        subprocess.run(['ffprobe', '-version'], capture_output=True, check=True)

        if not video_segments:
            raise ValueError('没有视频片段可拼接')

        temp_dir = tempfile.mkdtemp()
        try:
            # 强制刷新段落，避免调用方传入的 ORM 对象被 Session 缓存旧的 audio_* 字段
            segment_ids = [s.id for s in video_segments]
            refreshed_result = await self.db.execute(
                select(VideoSegment)
                .where(VideoSegment.id.in_(segment_ids))
                .order_by(VideoSegment.segment_index)
                .execution_options(populate_existing=True)
            )
            video_segments = list(refreshed_result.scalars().all())

            async with httpx.AsyncClient(timeout=60.0) as client:
                input_files: List[str] = []
                segment_probe: List[Dict[str, Any]] = []

                # 1) 下载视频并探测真实时长/帧率
                for idx, segment in enumerate(video_segments):
                    if not segment.video_url:
                        raise ValueError(f'视频片段 {idx} 缺少 video_url')
                    resp = await client.get(segment.video_url)
                    resp.raise_for_status()
                    input_path = os.path.join(temp_dir, f'input_{idx}.mp4')
                    with open(input_path, 'wb') as f:
                        f.write(resp.content)
                    input_files.append(input_path)
                    segment_probe.append(self._ffprobe_video_file(input_path))

                # 2) 为每段生成 muxed 文件（替换音轨 + 规范化时间轴）
                muxed_files: List[str] = []
                segment_durations_sec: List[float] = []
                # 统一帧率：取第一段探测 fps
                target_fps = float(segment_probe[0].get('fps') or 24.0)
                if target_fps <= 1.0:
                    target_fps = 24.0

                for idx, segment in enumerate(video_segments):
                    duration_sec = float(segment_probe[idx].get('duration_sec') or 0.0)
                    if duration_sec <= 0:
                        duration_sec = float(getattr(segment, 'audio_duration_sec', 0.0) or 0.0)
                    if duration_sec <= 0:
                        duration_sec = float(segment.duration or 0.0)
                    duration_sec = max(0.1, duration_sec)
                    segment_durations_sec.append(float(duration_sec))

                    audio_path: Optional[str] = None
                    # 重要：最终成片不应使用原视频音轨（避免出现“不是我们希望的语音”）
                    allow_original_fallback = (
                        os.getenv("EXPORT_ALLOW_ORIGINAL_AUDIO_FALLBACK", "false")
                        .lower()
                        == "true"
                    )
                    use_original_audio = False
                    audio_ok = (
                        bool(getattr(segment, 'audio_url', None))
                        and getattr(segment, 'audio_status', None) == AudioStatus.COMPLETED
                    )
                    if audio_ok:
                        try:
                            aresp = await client.get(str(segment.audio_url))
                            aresp.raise_for_status()
                            audio_path = os.path.join(temp_dir, f'audio_{idx}.wav')
                            with open(audio_path, 'wb') as f:
                                f.write(aresp.content)
                            logger.info(
                                'Downloaded TTS audio for mux',
                                segment_id=segment.id,
                                segment_index=segment.segment_index,
                                bytes=len(aresp.content),
                            )
                        except Exception as e:
                            logger.warning(
                                'Failed to download TTS audio, fallback to silence',
                                segment_id=segment.id,
                                error=str(e),
                            )
                            audio_path = None
                            # 默认不回退原音轨；如需保底可通过环境变量开启
                            use_original_audio = allow_original_fallback and bool(
                                segment_probe[idx].get('has_audio')
                            )
                    else:
                        # 没有 TTS 音频时：默认静音（避免出现原声）；如需保底可开启 env
                        use_original_audio = allow_original_fallback and bool(
                            segment_probe[idx].get('has_audio')
                        )

                    muxed_path = os.path.join(temp_dir, f'muxed_{idx}.mp4')

                    # 视频：强制 CFR + 重建 PTS；音频：atrim/apad 对齐到 duration_sec
                    vf = f'fps={target_fps:.6f},setpts=PTS-STARTPTS'
                    af = (
                        f'atrim=0:{duration_sec:.6f},asetpts=PTS-STARTPTS,'
                        f'apad=pad_dur={duration_sec:.6f}'
                    )

                    ffmpeg_cmd: List[str] = ['ffmpeg', '-y', '-i', input_files[idx]]
                    if audio_path:
                        ffmpeg_cmd.extend(['-i', audio_path])
                        ffmpeg_cmd.extend(['-map', '0:v:0', '-map', '1:a:0'])
                    elif use_original_audio:
                        ffmpeg_cmd.extend(['-map', '0:v:0', '-map', '0:a:0'])
                    else:
                        ffmpeg_cmd.extend(
                            [
                                '-f',
                                'lavfi',
                                '-i',
                                'anullsrc=channel_layout=mono:sample_rate=44100',
                                '-map',
                                '0:v:0',
                                '-map',
                                '1:a:0',
                            ]
                        )

                    ffmpeg_cmd.extend(
                        [
                            '-vf',
                            vf,
                            '-af',
                            af,
                            '-t',
                            f'{duration_sec:.6f}',
                            '-r',
                            f'{target_fps:.6f}',
                            '-c:v',
                            'libx264',
                            '-preset',
                            'veryfast',
                            '-crf',
                            '18',
                            '-pix_fmt',
                            'yuv420p',
                            '-c:a',
                            'aac',
                            '-b:a',
                            '128k',
                            '-ac',
                            '1',
                            '-ar',
                            '44100',
                            muxed_path,
                        ]
                    )

                    result = subprocess.run(
                        ffmpeg_cmd,
                        capture_output=True,
                        text=True,
                        timeout=300,
                    )
                    if result.returncode != 0:
                        raise Exception(
                            f'单段音轨替换失败: idx={idx}, stderr={result.stderr}'
                        )

                    muxed_files.append(muxed_path)

                # 3) 拼接 muxed 文件（复用现有 concat 逻辑）
                if len(muxed_files) == 1:
                    with open(muxed_files[0], 'rb') as f:
                        return f.read(), segment_durations_sec

                video_infos = [self._ffprobe_video_file(p) for p in muxed_files]
                output_path = os.path.join(temp_dir, 'output.mp4')
                build_cmd_result = self._build_ffmpeg_concat_cmd(
                    input_files=muxed_files,
                    video_infos=video_infos,
                    output_path=output_path,
                )
                concat_cmd = build_cmd_result['ffmpeg_cmd']
                concat_run = subprocess.run(
                    concat_cmd,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                if concat_run.returncode != 0:
                    raise Exception(f'视频拼接失败: {concat_run.stderr}')

                with open(output_path, 'rb') as f:
                    return f.read(), segment_durations_sec
        finally:
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass

