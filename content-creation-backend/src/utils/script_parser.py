"""
脚本解析工具
解析脚本内容，根据时间戳提取段落
"""

import re
from typing import List, Dict, Optional
import structlog

logger = structlog.get_logger(__name__)


class ScriptSegment:
    """脚本段落数据类."""

    def __init__(
        self,
        segment_id: str,
        time_range: str,
        content: str,
        is_first: bool = False,
        is_last: bool = False,
        is_frame_0: bool = False,
        keyframe_desc: Optional[str] = None,
        video_desc: Optional[str] = None,
        voice_desc: Optional[str] = None,
        narration: Optional[str] = None
    ):
        """初始化脚本段落.

        Args:
            segment_id: 段落ID
            time_range: 时间段（如 "0:00 - 0:25"）
            content: 段落内容（不包含时间戳，优先使用口播文案或视频描述）
            is_first: 是否为第一段
            is_last: 是否为最后一段
            is_frame_0: (历史字段) 是否为第0帧（开场画面）。现已废弃，仅用于兼容旧数据/日志。
            keyframe_desc: 关键帧描述
            video_desc: 视频描述
            voice_desc: 音色描述
            narration: 口播文案
        """
        self.segment_id = segment_id
        self.time_range = time_range
        self.content = content
        self.is_first = is_first
        self.is_last = is_last
        self.is_frame_0 = is_frame_0
        self.keyframe_desc = keyframe_desc
        self.video_desc = video_desc
        self.voice_desc = voice_desc
        self.narration = narration

    def to_dict(self) -> Dict:
        """转换为字典.

        Returns:
            段落字典
        """
        return {
            'segment_id': self.segment_id,
            'time_range': self.time_range,
            'content': self.content,
            'is_first': self.is_first,
            'is_last': self.is_last,
            'keyframe_desc': self.keyframe_desc,
            'video_desc': self.video_desc,
            'voice_desc': self.voice_desc,
            'narration': self.narration
        }


def parse_script(script_content: str) -> List[ScriptSegment]:
    """解析脚本内容，根据时间戳提取段落（全局不再包含第0帧）.

    Args:
        script_content: 脚本内容

    Returns:
        段落列表（不包含第0帧；段落从 segment_0 开始）
    """
    if not script_content or not script_content.strip():
        logger.warning('Empty script content')
        return []

    segments: List[ScriptSegment] = []

    # 兼容历史脚本：脚本中可能包含“第0帧/开场画面”描述。全局移除第0帧后，需要将其从脚本文本中剥离，
    # 避免混入 segment_0 正文导致后续关键帧/字幕/配音文本异常。
    frame_0_pattern = (
        r'(?:^\*{0,2}第0帧[：:]\*{0,2}\s*(.+?)(?=\n|$)'
        r'|^\(0:00\s*-\s*0:00\)\s*开场画面[：:]\s*(.+?)(?=\n|$)'
        r'|^(开场画面[：:]\s*.+?)(?=\n\d+-\d+s|\n\(|\Z))'
    )
    if re.search(frame_0_pattern, script_content, re.MULTILINE | re.DOTALL):
        script_content = re.sub(
            frame_0_pattern,
            "",
            script_content,
            flags=re.MULTILINE | re.DOTALL,
        )
        logger.info("Frame 0 (opening) found and stripped (deprecated)")
    
    # 尝试分割段落以支持多行格式
    # 使用时间戳作为分隔符
    timestamp_pattern = r'(\(\d+[:\-]\d+.*?\))'
    parts = re.split(timestamp_pattern, script_content)
    
    raw_segments = []
    if len(parts) >= 2:
        # 重组 parts: part[1] is timestamp, part[2] is content...
        for i in range(1, len(parts), 2):
            if i + 1 < len(parts):
                ts = parts[i]
                body = parts[i+1]
                raw_segments.append((ts, body))
    else:
        # 兜底：按空行分割
        paragraphs = re.split(r'\n\s*\n+', script_content.strip())
        for p in paragraphs:
            # 尝试提取时间戳
            ts_match = re.search(r'(\(.*?\))', p)
            if ts_match:
                ts = ts_match.group(1)
                body = p
                raw_segments.append((ts, body))
    
    if not raw_segments:
        logger.warning('No time segments found in script')
        return [
            ScriptSegment(
                segment_id='segment_0',
                time_range='',
                content=script_content.strip(),
                is_first=True,
                is_last=True
            )
        ]

    for i, (ts_str, body_text) in enumerate(raw_segments):
        # 提取时间范围字符串
        time_range = ts_str.strip('() ')
        
        # 提取字段
        def extract_field(text, field_name):
            match = re.search(f"{field_name}[：:](.*?)(?=\n[^：:]+[：:]|\Z)", text, re.DOTALL)
            if match:
                return match.group(1).strip()
            return None

        keyframe_desc = extract_field(body_text, "关键帧")
        video_desc = extract_field(body_text, "视频")
        voice_desc = extract_field(body_text, "音色")
        narration = extract_field(body_text, "口播文案")
        
        # 如果有新格式字段
        if keyframe_desc or narration:
            main_content = narration if narration else (video_desc if video_desc else body_text.strip())
        else:
            # 旧格式：移除时间戳后的纯文本
            main_content = body_text.replace(ts_str, '').strip()
            # 移除多余空行
            main_content = re.sub(r'\n\s*\n+', '\n\n', main_content).strip()

        segment_id = f'segment_{i}'
        is_first = i == 0
        is_last = i == len(raw_segments) - 1

        segment = ScriptSegment(
            segment_id=segment_id,
            time_range=time_range,
            content=main_content,
            is_first=is_first,
            is_last=is_last,
            keyframe_desc=keyframe_desc,
            video_desc=video_desc,
            voice_desc=voice_desc,
            narration=narration
        )
        segments.append(segment)

    logger.info(
        'Script parsed successfully',
        total_segments=len(segments),
        has_deprecated_frame_0=any(s.is_frame_0 for s in segments)
    )

    return segments


def extract_prompt_for_segment(
    segment: ScriptSegment, is_first_frame: bool = False
) -> str:
    """提取段落的提示词（用于图片生成）.

    Args:
        segment: 脚本段落
        is_first_frame: 是否为第一段的第一帧

    Returns:
        提示词文本
    """
    # 关键帧生成：优先使用关键帧描述（keyframe_desc），否则回退到解析出的 content
    prompt = segment.keyframe_desc if segment.keyframe_desc else segment.content

    # 如果是第一段第一帧，添加开场关键词
    if is_first_frame and segment.is_first:
        prompt = f'{prompt} 开场画面，第一帧，初始场景'
    
    # 兼容旧逻辑：只有在“没有关键帧描述”的情况下，才补充视频描述
    if segment.video_desc and not segment.keyframe_desc:
        prompt = f"{prompt}，{segment.video_desc}"

    return prompt.strip()


def extract_narration_for_segment(segment: ScriptSegment) -> str:
    """提取段落口播文案（用于统一作为生成提示词）.

    Args:
        segment: 脚本段落

    Returns:
        口播文案文本（可能为空字符串）
    """
    return (segment.narration or "").strip()


def get_segment_by_id(
    segments: List[ScriptSegment], segment_id: str
) -> Optional[ScriptSegment]:
    """根据段落ID获取段落.

    Args:
        segments: 段落列表
        segment_id: 段落ID

    Returns:
        段落对象，如果不存在返回None
    """
    for segment in segments:
        if segment.segment_id == segment_id:
            return segment
    return None
