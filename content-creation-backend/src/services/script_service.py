"""
脚本生成服务
"""

import re
import json
import math
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.services.llm_service import LLMService
from src.services.system_config_service import SystemConfigService
from src.services.vision_analysis_service import VisionAnalysisService
from src.models.schemas.script import ScriptSegment, GenerateScriptRequest, ScriptUpdate
from src.models.tables.script import Script
from src.utils.exceptions import ValidationError, NotFoundError

logger = structlog.get_logger(__name__)


class ScriptService:
    """脚本生成服务类"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm_service = LLMService()

    @staticmethod
    def _normalize_script_timestamps(
        content: str,
        *,
        total_duration: int,
        segment_duration: int,
    ) -> str:
        """归一化脚本文本中的时间戳，使其与 segment_duration 对齐。

        背景：
        - 部分模型（例如 kimi）会输出非均匀时间段（如 (0-5s)(5-16s)），导致解析出的 segments 与预期不符。
        - 这里强制将时间段重写为：
          - 前 N-1 段：长度为 segment_duration
          - 最后一段：到 total_duration 为止（可能短于 segment_duration）

        注意：仅重写形如 "(0-8s)" 或 "(0-8s)  " 的时间戳行，不改其他内容。
        """
        if not content:
            return content

        total_duration = int(total_duration)
        segment_duration = int(segment_duration)
        if total_duration <= 0 or segment_duration <= 0:
            return content

        expected_segments = math.ceil(total_duration / segment_duration)
        if expected_segments <= 0:
            return content

        # 逐行扫描，遇到时间戳行时按顺序替换为规范时间段
        lines = content.splitlines()
        seg_idx = 0
        out_lines: List[str] = []

        # 匹配一行内的时间戳（允许末尾空格、允许无 s）
        ts_line_re = re.compile(r"^\s*\(\s*(\d+)\s*-\s*(\d+)\s*s?\s*\)\s*$")

        for line in lines:
            if seg_idx < expected_segments and ts_line_re.match(line):
                start = seg_idx * segment_duration
                end = min(total_duration, (seg_idx + 1) * segment_duration)
                # 最后一段至少 4 秒：若余量不足 4 秒，则向上补齐（可能超过 total_duration）
                if seg_idx == expected_segments - 1 and (end - start) < 4:
                    end = start + 4
                out_lines.append(f"({start}-{end}s)")
                seg_idx += 1
            else:
                out_lines.append(line)

        return "\n".join(out_lines)

    @staticmethod
    def _strip_markdown_code_fences(text: str) -> str:
        """提取 ```...``` 代码块内部文本（常见为 ```json），避免解析器误把 Markdown 当脚本。"""
        if not text:
            return ""
        raw = str(text).strip()
        if "```" not in raw:
            return raw

        m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw, flags=re.IGNORECASE)
        if m and m.group(1):
            return m.group(1).strip()

        return raw.replace("```json", "").replace("```", "").strip()

    @staticmethod
    def _repair_json_like_script_to_text(
        text: str,
        *,
        total_duration: int,
        segment_duration: int,
    ) -> str:
        """
        兜底修复：当模型输出了 JSON/类 JSON（例如包含 \"片段1\":\"(0-4s)\"）时，
        尽量提取字段并拼回标准脚本文本格式。
        """
        if not text or not str(text).strip():
            return ""

        src = str(text)
        if "片段" not in src:
            return src.strip()

        # 找到所有片段时间定义： "片段1": "(0-4s)"
        seg_re = re.compile(
            r'["“]?\s*片段\s*(\d+)\s*["”]?\s*:\s*["“]?\(?\s*(\d+)\s*-\s*(\d+)\s*s?\s*\)?["”]?',
            flags=re.IGNORECASE,
        )
        matches = list(seg_re.finditer(src))
        if not matches:
            return src.strip()

        def _extract(block: str, key: str) -> Optional[str]:
            # 尝试抓取类似 "口播文案": "..." 的内容（默认不含未转义双引号）
            pat = re.compile(rf'"{re.escape(key)}"\s*:\s*"([\s\S]*?)"\s*(?:,|\n|\}})', flags=re.IGNORECASE)
            m = pat.search(block)
            return m.group(1).strip() if m else None

        segs = []
        for idx, m in enumerate(matches):
            start = int(m.group(2))
            end = int(m.group(3))
            block_start = m.end()
            block_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(src)
            block = src[block_start:block_end]

            narration = _extract(block, "口播文案") or ""
            keyframe = _extract(block, "关键帧") or ""
            video = _extract(block, "视频") or ""
            voice = _extract(block, "音色") or ""

            segs.append((start, end, keyframe, video, voice, narration))

        # 按时间排序并生成文本
        segs.sort(key=lambda x: x[0])
        out_lines: List[str] = []
        for start, end, keyframe, video, voice, narration in segs:
            out_lines.append(f"({start}-{end}s)")
            out_lines.append(f"关键帧：{keyframe}".rstrip())
            out_lines.append(f"视频：{video}".rstrip())
            out_lines.append(f"音色：{voice}".rstrip())
            out_lines.append(f"口播文案：{narration}".rstrip())
            out_lines.append("")

        repaired = "\n".join(out_lines).strip()
        # 若修复后仍无时间戳，则回退
        if "(" not in repaired:
            return src.strip()
        return repaired


    def parse_script_content(self, content: str, segment_duration: int) -> List[ScriptSegment]:
        """
        解析脚本内容，提取时间段和内容
        
        支持格式：
        (0-8s)
        关键帧：...
        视频：...
        音色：...
        口播文案：...
        
        Args:
            content: 脚本内容
            segment_duration: 单个片段时长
            
        Returns:
            脚本片段列表
        """
        segments = []
        segment_index = 0
        
        # 分割成段落（使用空行分隔）
        # 注意：新格式可能包含多行，所以依然按空行分割是合理的，假设LLM在不同时间段之间留有空行
        # 如果LLM没有留空行，可能需要按时间戳分割
        
        # 尝试按时间戳分割
        # 匹配 (0-8s) 或 (0:00-0:08) 格式的时间戳行
        timestamp_pattern = r'(\(\d+[:\-]\d+.*?\))'
        parts = re.split(timestamp_pattern, content)
        
        # 如果分割后只有一部分（没匹配到），尝试按空行分割兜底
        if len(parts) < 2:
            logger.warning("Timestamp splitting failed, falling back to paragraph splitting")
            paragraphs = re.split(r'\n\s*\n+', content.strip())
        else:
            # 重组 parts: part[1] is timestamp, part[2] is content, part[3] is timestamp...
            paragraphs = []
            # 第0部分通常是前言或第0帧
            if parts[0].strip():
                paragraphs.append(parts[0].strip())
            
            for i in range(1, len(parts), 2):
                if i + 1 < len(parts):
                    ts = parts[i]
                    body = parts[i+1]
                    paragraphs.append(f"{ts}\n{body}")
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            
            # 匹配第0帧
            if paragraph.startswith('第0帧') or paragraph.startswith('**第0帧'):
                # 第0帧不作为普通segment处理
                continue

            # 提取时间戳
            # 格式：(0-6s) 或 (0:00 - 0:06)
            time_match = re.search(r'\((\d+)\s*-\s*(\d+)s?\)', paragraph)
            start_time = 0
            end_time = segment_duration
            
            if time_match:
                start_time = float(time_match.group(1))
                end_time = float(time_match.group(2))
            else:
                # 尝试匹配 MM:SS 格式
                time_match_2 = re.search(r'\((\d+):(\d+)\s*-\s*(\d+):(\d+)\)', paragraph)
                if time_match_2:
                    start_min, start_sec, end_min, end_sec = map(int, time_match_2.groups())
                    start_time = start_min * 60 + start_sec
                    end_time = end_min * 60 + end_sec
                else:
                    # 如果没有时间戳且不是第0帧，可能是无法解析的文本，跳过或作为默认
                    # 但为了健壮性，如果是新格式，应该都有时间戳
                    # 检查是否有"关键帧："等关键字，如果有，可能是漏了时间戳
                    if "关键帧：" in paragraph:
                         start_time = segment_index * segment_duration
                         end_time = (segment_index + 1) * segment_duration
                    else:
                        continue

            # 提取字段
            def extract_field(text, field_name):
                pattern = f"{field_name}[：:]\s*(.*?)(\n|$|{field_name})" 
                # 简单的正则可能无法处理跨行，尝试更通用的
                # 假设字段顺序固定或以换行分隔
                # 使用非贪婪匹配直到行尾，或者下一行是关键词
                # 既然格式是 Key: Value \n Key: Value
                match = re.search(f"{field_name}[：:](.*?)(?=\n[^：:]+[：:]|\Z)", text, re.DOTALL)
                if match:
                    return match.group(1).strip()
                return None

            # 针对新格式的提取
            keyframe_desc = extract_field(paragraph, "关键帧")
            video_desc = extract_field(paragraph, "视频")
            voice_desc = extract_field(paragraph, "音色")
            narration = extract_field(paragraph, "口播文案")
            
            # 如果提取到了关键字段，说明是新格式
            if keyframe_desc or narration:
                # 优先使用口播文案作为content（为了兼容）
                # 如果没有口播文案，使用视频描述，或者整个段落
                main_content = narration if narration else (video_desc if video_desc else paragraph)
                
                segment = ScriptSegment(
                    id=f"segment_{segment_index}",
                    time_start=float(start_time),
                    time_end=float(end_time),
                    content=main_content, # 兼容字段
                    narration=narration,
                    keyframe_desc=keyframe_desc,
                    video_desc=video_desc,
                    voice_desc=voice_desc,
                    subtitle=narration # 假设字幕即口播文案
                )
                segments.append(segment)
                segment_index += 1
                continue
            
            # 旧格式处理 (0-8s) 内容...
            # 移除时间戳行
            content_text = re.sub(r'\(.*?\)', '', paragraph).strip()
            if content_text:
                segment = ScriptSegment(
                    id=f"segment_{segment_index}",
                    time_start=float(start_time),
                    time_end=float(end_time),
                    content=content_text
                )
                segments.append(segment)
                segment_index += 1
        
        logger.info(f"Parsed {len(segments)} segments from script")
        return segments

    @staticmethod
    def _count_spoken_chars(text: str) -> int:
        """统计口播“有效字数”（不含空格与标点）。

        口径：汉字 + 数字 + 英文（不包含标点、引号、空格等）。
        """
        if not text:
            return 0
        tokens = re.findall(r"[\u4e00-\u9fff0-9A-Za-z]", text)
        return len(tokens)

    @staticmethod
    def _build_narration_length_targets(
        segments: List[ScriptSegment],
        *,
        min_chars_per_sec: float,
        max_chars_per_sec: float,
    ) -> List[tuple[str, int, int]]:
        """为每个 segment 生成口播字数目标区间。"""
        targets: List[tuple[str, int, int]] = []
        for seg in segments:
            sec = max(0.0, float(seg.time_end) - float(seg.time_start))
            min_len = int(sec * float(min_chars_per_sec))
            max_len = int(sec * float(max_chars_per_sec))
            if max_len < min_len:
                max_len = min_len
            targets.append((seg.id, min_len, max_len))
        return targets

    @staticmethod
    def _needs_narration_rewrite(
        segments: List[ScriptSegment],
        *,
        min_chars_per_sec: float,
        max_chars_per_sec: float,
    ) -> bool:
        """判断是否需要触发“口播字数兜底重写”."""
        targets = ScriptService._build_narration_length_targets(
            segments,
            min_chars_per_sec=min_chars_per_sec,
            max_chars_per_sec=max_chars_per_sec,
        )
        for seg, (_, min_len, max_len) in zip(segments, targets):
            narration = (seg.narration or seg.content or "").strip()
            n = ScriptService._count_spoken_chars(narration)
            # 允许 1 字的浮动，减少无意义的二次调用
            if n < max(0, min_len - 1) or n > (max_len + 1):
                return True
        return False

    async def generate_script(
        self,
        request: GenerateScriptRequest,
        model: str = "deepseek-chat"
    ) -> dict:
        """
        生成脚本
        
        Args:
            request: 生成脚本请求
            model: 使用的模型名称
            
        Returns:
            包含脚本内容和片段的字典
        """
        # 验证参数
        if request.total_duration < request.segment_duration:
            raise ValidationError("视频总时长不能小于单个视频时长")
        
        if request.total_duration % request.segment_duration != 0:
            logger.warning(
                "Duration not divisible",
                total_duration=request.total_duration,
                segment_duration=request.segment_duration
            )
        
        # 获取风格描述（从数据库获取）
        config_service = SystemConfigService(self.db)
        styles = await config_service.get_script_styles()
        style_info = next((s for s in styles if s["id"] == request.style), None)
        style_name = style_info["name"] if style_info else request.style
        style_description = style_info["description"] if style_info else request.style
        
        # 从数据库获取提示词模板
        prompt_template = await config_service.get_script_prompt()
        
        # 如果有参考图，先进行视觉分析
        vision_guidance = None
        if request.reference_image_urls and len(request.reference_image_urls) > 0:
            try:
                logger.info(
                    "Starting vision analysis for reference images",
                    image_count=len(request.reference_image_urls)
                )
                
                vision_service = VisionAnalysisService()
                vision_guidance = await vision_service.analyze_and_merge(
                    image_urls=request.reference_image_urls
                )
                
                if vision_guidance:
                    logger.info(
                        "Vision analysis completed",
                        image_count=len(request.reference_image_urls),
                        guidance_length=len(vision_guidance)
                    )
                else:
                    logger.warning(
                        "Vision analysis returned no results, continuing without guidance"
                    )
            except Exception as e:
                # 视觉分析失败不应阻止脚本生成
                logger.error(
                    "Vision analysis failed, continuing without guidance",
                    error=str(e),
                    error_type=type(e).__name__
                )
                vision_guidance = None
        
        # 调用LLM生成脚本
        logger.info(
            "Generating script",
            inspiration=request.inspiration[:50],
            style=request.style,
            model=model,
            total_duration=request.total_duration,
            segment_duration=request.segment_duration,
            using_custom_prompt=bool(prompt_template),
            has_vision_guidance=bool(vision_guidance)
        )
        
        script_content = await self.llm_service.generate_script(
            inspiration=request.inspiration,
            style=style_description,
            total_duration=request.total_duration,
            segment_duration=request.segment_duration,
            model=model,
            # 追加一层“反 JSON/反 Markdown code block”的硬约束，避免自定义风格误导模型输出 JSON
            custom_prompt_template=(
                (prompt_template or "")
                + "\n\n【严格输出格式约束】\n"
                + "1) 只输出最终脚本文本，不要输出任何解释、不要输出 Markdown 代码块、不要输出 JSON。\n"
                + "2) 每个片段必须以单独一行的时间戳开头，例如：(0-4s)\n"
                + "3) 每个片段必须包含且仅包含以下四行字段：关键帧： / 视频： / 音色： / 口播文案：\n"
                + "4) 严禁输出“第0帧/开场画面”。\n"
            ),
            vision_guidance=vision_guidance,
            enable_search=getattr(request, "enable_search", False),
            style_name=style_name,
            style_description=style_description,
        )

        # 兜底：如果模型输出了 ```json 或“片段1: (0-4s)”这类类JSON，先剥离/修复为标准脚本文本再进入解析逻辑
        script_content = self._strip_markdown_code_fences(script_content)
        if "片段" in script_content and ("\"" in script_content or "：" in script_content):
            script_content = self._repair_json_like_script_to_text(
                script_content,
                total_duration=request.total_duration,
                segment_duration=request.segment_duration,
            )

        # 归一化时间戳：避免模型输出非均匀时间段导致 segments 与预期不一致
        # 同时强制最后一段至少 4 秒：若余量不足 4 秒，则向上补齐（可能超过 request.total_duration）
        expected_segments = math.ceil(request.total_duration / request.segment_duration)
        last_start = max(0, (expected_segments - 1) * request.segment_duration)
        effective_total_duration = int(request.total_duration)
        if (effective_total_duration - last_start) < 4:
            effective_total_duration = int(last_start + 4)

        script_content = self._normalize_script_timestamps(
            script_content,
            total_duration=effective_total_duration,
            segment_duration=request.segment_duration,
        )
        
        # 解析脚本内容
        segments = self.parse_script_content(script_content, request.segment_duration)

        # --- 口播字数兜底：不截断，触发一次“重写口播文案” ---
        # 背景：部分模型会忽略字数约束，导致 10s 只有 20 多字或超长。
        # 策略：若检测到明显不符合范围，则调用一次 optimize_script，只重写“口播文案”行。
        min_cps = 3.3
        max_cps = 3.6
        if segments and self._needs_narration_rewrite(
            segments, min_chars_per_sec=min_cps, max_chars_per_sec=max_cps
        ):
            targets = self._build_narration_length_targets(
                segments, min_chars_per_sec=min_cps, max_chars_per_sec=max_cps
            )
            # 用“规范时间戳”为每段生成约束（与后续 normalize 对齐）
            expected_segments = math.ceil(
                effective_total_duration / request.segment_duration
            )
            constraints: List[str] = []
            for i, (_, min_len, max_len) in enumerate(targets):
                start = i * request.segment_duration
                end = min(
                    effective_total_duration, (i + 1) * request.segment_duration
                )
                if i == expected_segments - 1 and (end - start) < 4:
                    end = start + 4
                constraints.append(f"- ({start}-{end}s)：{min_len}-{max_len} 字")

            creative_desc = (
                "请只修改下面脚本中的【口播文案：】内容，使其满足字数要求；"
                "其余字段（时间戳、关键帧、视频、音色等）必须保持原样，"
                "不要改变结构，不要添加解释，不要新增段落。\n\n"
                "字数统计口径：仅统计“汉字+数字+英文”，不包含标点与空格。\n"
                "每段口播文案必须严格落在对应区间内：\n"
                + "\n".join(constraints)
                + "\n\n输出要求：只输出最终脚本文本。口播文案必须是完整句子，不能半句截断。"
            )

            try:
                logger.info(
                    "Narration length out of range; optimizing narration lines",
                    script_total_duration=effective_total_duration,
                    segment_duration=request.segment_duration,
                    model=model,
                )
                script_content = await self.llm_service.optimize_script(
                    script_content=script_content,
                    creative_description=creative_desc,
                    model=model,
                    enable_search=getattr(request, "enable_search", False),
                )
                # 再次归一化时间戳，避免优化过程改坏时间段
                script_content = self._normalize_script_timestamps(
                    script_content,
                    total_duration=effective_total_duration,
                    segment_duration=request.segment_duration,
                )
                segments = self.parse_script_content(
                    script_content, request.segment_duration
                )
            except Exception as exc:
                logger.warning(
                    "Narration optimization failed; returning original script",
                    error=str(exc),
                    model=model,
                )
        
        # 如果解析的片段数量不对，记录警告（向上取整，确保总时长不少于用户输入）
        expected_segments = math.ceil(request.total_duration / request.segment_duration)
        # 允许一定的误差，或者只是警告
        if len(segments) != expected_segments:
            logger.warning(
                "Segment count mismatch",
                expected=expected_segments,
                actual=len(segments),
                total_duration=request.total_duration,
                segment_duration=request.segment_duration
            )
        
        return {
            "content": script_content,
            "segments": segments,
            "style": request.style,
            "total_duration": effective_total_duration,
            "segment_duration": request.segment_duration,
        }

    async def create_script(
        self,
        project_id: int,
        content: str,
        style: str,
        total_duration: int,
        segment_duration: int,
        segments: List[ScriptSegment]
    ) -> Script:
        """
        创建脚本记录到数据库
        
        Args:
            project_id: 项目ID
            content: 脚本内容
            style: 脚本风格
            total_duration: 总时长
            segment_duration: 单段时长
            segments: 脚本片段列表
            
        Returns:
            创建的脚本对象
        """
        # 将segments转换为JSON格式
        # 使用 model_dump 自动处理所有字段
        segments_json = [
            seg.model_dump()
            for seg in segments
        ]
        
        script = Script(
            project_id=project_id,
            content=content,
            style=style,
            total_duration=total_duration,
            segment_duration=segment_duration,
            segments=segments_json
        )
        
        self.db.add(script)
        await self.db.commit()
        await self.db.refresh(script)
        
        # 如果是第一次生成脚本,记录生成时间到项目
        from sqlalchemy import select
        from src.models.tables.project import Project
        from datetime import datetime
        
        result = await self.db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()
        
        if project and project.first_script_generated_at is None:
            project.first_script_generated_at = datetime.now()
            await self.db.commit()
            logger.info(
                "记录第一次脚本生成时间",
                project_id=project_id,
                first_script_generated_at=project.first_script_generated_at
            )
        
        logger.info("脚本创建成功", script_id=script.id, project_id=project_id)
        return script

    async def get_script(self, script_id: int, project_id: int) -> Optional[Script]:
        """
        获取脚本
        
        Args:
            script_id: 脚本ID
            project_id: 项目ID
            
        Returns:
            脚本对象，如果不存在返回None
        """
        from sqlalchemy import select
        result = await self.db.execute(
            select(Script).where(
                Script.id == script_id,
                Script.project_id == project_id
            )
        )
        script = result.scalar_one_or_none()
        return script

    async def update_script(
        self,
        script_id: int,
        project_id: int,
        script_data: ScriptUpdate
    ) -> Script:
        """
        更新脚本
        
        Args:
            script_id: 脚本ID
            project_id: 项目ID
            script_data: 脚本更新数据
            
        Returns:
            更新后的脚本对象
            
        Raises:
            NotFoundError: 脚本不存在
        """
        script = await self.get_script(script_id, project_id)
        if not script:
            raise NotFoundError(f"脚本 {script_id} 不存在")
        
        # 更新字段
        update_data = script_data.model_dump(exclude_unset=True)
        
        # 如果更新segments，需要转换为JSON格式
        if "segments" in update_data and update_data["segments"] is not None:
            segments_json = [
                seg.model_dump()
                for seg in script_data.segments # 注意这里直接用原始对象列表转换，避免多次转换
            ]
            update_data["segments"] = segments_json
        
        for field, value in update_data.items():
            setattr(script, field, value)
        
        await self.db.commit()
        await self.db.refresh(script)
        
        logger.info("脚本更新成功", script_id=script_id, project_id=project_id)
        return script

    async def optimize_script(
        self,
        script_id: int,
        project_id: int,
        creative_description: str,
        model: str = "deepseek-chat",
        enable_search: bool = False,
    ) -> Script:
        """
        优化脚本，使用创意描述作为补充
        
        Args:
            script_id: 脚本ID
            project_id: 项目ID
            creative_description: 创意描述（用于优化脚本）
            model: 使用的模型名称
            
        Returns:
            优化后的脚本对象
            
        Raises:
            NotFoundError: 脚本不存在
        """
        script = await self.get_script(script_id, project_id)
        if not script:
            raise NotFoundError(f"脚本 {script_id} 不存在")
        
        if not script.content:
            raise ValidationError("脚本内容为空，无法优化")
        
        logger.info(
            "Optimizing script",
            script_id=script_id,
            model=model,
            creative_description_length=len(creative_description)
        )
        
        # 调用LLM优化脚本
        optimized_content = await self.llm_service.optimize_script(
            script_content=script.content,
            creative_description=creative_description,
            model=model,
            enable_search=enable_search,
        )
        
        # 更新脚本内容
        script.content = optimized_content
        script.optimized_content = optimized_content
        
        # 重新解析segments并更新
        # 注意：优化后的脚本可能改变了分段，这里需要重新解析
        # 获取原有的segment_duration
        segment_duration = script.segment_duration or 8 # 默认8秒
        
        new_segments = self.parse_script_content(optimized_content, segment_duration)
        
        # 转换为JSON
        segments_json = [seg.model_dump() for seg in new_segments]
        script.segments = segments_json
        
        await self.db.commit()
        await self.db.refresh(script)
        
        logger.info("脚本优化成功", script_id=script_id, project_id=project_id)
        return script

    @staticmethod
    def get_script_styles() -> List[dict]:
        """
        获取脚本风格列表
        
        Returns:
            风格列表
        """
        return [
            {
                "id": "storytelling",
                "name": "故事化叙事风格",
                "description": "将创意扩展为一个完整的故事，通过一个具体的故事或场景引入理论或知识的科普。脚本结构：开端（问题）：展示一个普通人或企业面临的困境。发展（引入理论知识）：科学理论如何介入，解决问题。高潮（价值升华）：展示问题解决后的美好结果。结尾（呼吁）：点明主题，如'xxx生活习惯，让你更年轻'。每一段片段开头强调这是一个写实场景，用写实画面表现。"
            },
            {
                "id": "visual_animation",
                "name": "可视化动画/图形动画风格",
                "description": "将创意扩展为一个完整的科普动画，通过一个具体的故事或场景引入理论或知识的科普。脚本结构：开端（问题）：展示一个普通人或企业面临的困境。发展（引入理论知识）：科学理论如何介入，解决问题。高潮（价值升华）：展示问题解决后的美好结果。结尾（呼吁）：点明主题，如'xxx生活习惯，让你更年轻'。每一段片段开头强调这是一个写实场景，用写实画面表现。特点：用生动的动画、MG（Motion Graphics）来解释抽象的医学概念（如神经网络）,必须保证所有的描述风格统一。脚本结构：提出概念：'什么是抗炎？'比喻解释：用动画过程，类比细胞抵抗炎症的过程。步骤拆解：分解为几个可视化步骤。每一段片段开头强调这是一个动画非真实场景，用动画表现。"
            }
        ]
