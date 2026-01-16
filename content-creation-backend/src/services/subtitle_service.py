"""
字幕生成服务（ASS burn-in）.

该模块用于在导出拼接视频时生成 .ass 字幕文件内容，供 FFmpeg subtitles 滤镜烧录。
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import List, Sequence, Tuple


@dataclass(frozen=True)
class SubtitleEvent:
    """单条字幕事件（ASS Events 行）."""

    start_sec: float
    end_sec: float
    text: str


class SubtitleService:
    """字幕服务：生成 ASS 文本（逐行 line-level）."""

    def __init__(self) -> None:
        # 默认字体必须在 Linux 容器内存在，否则会出现“字幕方块/乱码”（缺字形）。
        # 生产镜像会安装 Noto CJK 字体，因此默认改为 Noto Sans CJK SC。
        self.font_name = os.getenv("SUBTITLE_FONT", "Noto Sans CJK SC")
        # 字幕默认样式（可通过环境变量覆盖）：
        # - Fontsize：默认较大，适配 1080x1920 竖屏；如仍偏小可继续增大
        # - MarginV：底部留白，值越大字幕越靠上（避免贴底）
        self.font_size = int(os.getenv("SUBTITLE_FONT_SIZE", "50"))
        self.margin_v = int(os.getenv("SUBTITLE_MARGIN_V", "120"))
        self.outline = int(os.getenv("SUBTITLE_OUTLINE", "3"))
        self.shadow = int(os.getenv("SUBTITLE_SHADOW", "1"))
        self.max_line_len = int(os.getenv("SUBTITLE_MAX_LINE_LEN", "18"))
        self.max_lines_per_segment = int(
            os.getenv("SUBTITLE_MAX_LINES_PER_SEGMENT", "3")
        )
        self.min_caption_sec = float(os.getenv("SUBTITLE_MIN_SEC", "0.8"))

    def build_ass(
        self,
        *,
        narrations: Sequence[str],
        segment_durations_sec: Sequence[float],
    ) -> Tuple[str, List[SubtitleEvent]]:
        """生成 ASS 字幕内容。

        Args:
            narrations: 与视频段顺序一致的口播文本（可为空字符串）。
            segment_durations_sec: 与视频段顺序一致的真实时长（秒）。

        Returns:
            (ass_text, events)
        """
        if len(narrations) != len(segment_durations_sec):
            raise ValueError("narrations 与 segment_durations_sec 长度不一致")

        events: List[SubtitleEvent] = []
        offset = 0.0
        # Python 3.9 不支持 zip(strict=...)；长度已在上方校验
        for narration, duration in zip(narrations, segment_durations_sec):
            duration = max(0.1, float(duration))
            narration = (narration or "").strip()
            if narration:
                lines = self._split_to_lines(narration)
                events.extend(
                    self._allocate_time_for_lines(
                        lines=lines,
                        segment_offset_sec=offset,
                        segment_duration_sec=duration,
                    )
                )
            offset += duration

        ass_text = self._render_ass(events)
        return ass_text, events

    def _split_to_lines(self, text: str) -> List[str]:
        """将口播按句/逗号切分，并限制行长."""
        text = re.sub(r"\s+", " ", text.strip())
        if not text:
            return []

        # 先按句末标点切分
        parts = [
            p.strip()
            for p in re.split(r"(?<=[。！？；…])", text)
            if p and p.strip()
        ]

        # 二次切分过长句子
        refined: List[str] = []
        for part in parts:
            refined.extend(self._split_long_piece(part))

        # 限制每段最多 k 行（逐行出现），多余则合并到最后一行
        k = max(1, self.max_lines_per_segment)
        if len(refined) <= k:
            return refined

        head = refined[: k - 1]
        tail = " ".join(refined[k - 1 :]).strip()
        return [*head, tail]

    def _split_long_piece(self, piece: str) -> List[str]:
        """对单句按 max_line_len 进行软切分."""
        piece = piece.strip()
        if len(piece) <= self.max_line_len:
            return [piece]

        # 优先在弱标点处切分
        tokens = re.split(r"(?<=[，,、:：])", piece)
        out: List[str] = []
        buf = ""
        for t in tokens:
            t = t.strip()
            if not t:
                continue
            if not buf:
                buf = t
                continue
            if len(buf) + len(t) <= self.max_line_len:
                buf += t
            else:
                out.append(buf.strip())
                buf = t
        if buf:
            out.append(buf.strip())

        # 仍然过长则硬切
        final: List[str] = []
        for seg in out:
            if len(seg) <= self.max_line_len:
                final.append(seg)
            else:
                for i in range(0, len(seg), self.max_line_len):
                    final.append(seg[i : i + self.max_line_len].strip())
        return [s for s in final if s]

    def _allocate_time_for_lines(
        self,
        *,
        lines: Sequence[str],
        segment_offset_sec: float,
        segment_duration_sec: float,
    ) -> List[SubtitleEvent]:
        """按字符权重在段内分配每行的显示时长."""
        if not lines:
            return []

        d = max(0.1, float(segment_duration_sec))
        weights = [max(1, len(re.sub(r"\s+", "", line))) for line in lines]
        total = float(sum(weights))

        raw = [d * (w / total) for w in weights]
        min_sec = max(0.1, float(self.min_caption_sec))

        # 先满足最小展示时长
        adjusted = raw[:]
        deficit = 0.0
        for i, v in enumerate(adjusted):
            if v < min_sec:
                deficit += (min_sec - v)
                adjusted[i] = min_sec

        # 从最长行回收 deficit
        if deficit > 0:
            indices = sorted(range(len(adjusted)), key=lambda i: adjusted[i], reverse=True)
            for idx in indices:
                if deficit <= 0:
                    break
                can_take = max(0.0, adjusted[idx] - min_sec)
                take = min(can_take, deficit)
                adjusted[idx] -= take
                deficit -= take

        # 归一化（避免浮点累积误差）
        total_adj = sum(adjusted)
        if total_adj <= 0:
            adjusted = [d / len(lines)] * len(lines)
        else:
            scale = d / total_adj
            adjusted = [v * scale for v in adjusted]

        out: List[SubtitleEvent] = []
        cursor = float(segment_offset_sec)
        # Python 3.9 不支持 zip(strict=...)；这里两者长度应一致
        for line, dur in zip(lines, adjusted):
            start = cursor
            end = cursor + float(dur)
            out.append(SubtitleEvent(start_sec=start, end_sec=end, text=line))
            cursor = end
        return out

    def _render_ass(self, events: Sequence[SubtitleEvent]) -> str:
        """渲染 ASS 全文."""
        header = self._ass_header()
        lines = [header, "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
        for e in events:
            start = self._format_ass_time(e.start_sec)
            end = self._format_ass_time(e.end_sec)
            text = self._escape_ass_text(e.text)
            lines.append(
                f"Dialogue: 0,{start},{end},Default,,0,0,{self.margin_v},,{text}"
            )
        return "\n".join(lines) + "\n"

    def _ass_header(self) -> str:
        # 颜色为 ASS BGR 格式：&HAABBGGRR（AA=透明度）
        primary = "&H00FFFFFF"  # white
        outline = "&H00000000"  # black
        back = "&H64000000"  # semi-transparent black (unused)
        return "\n".join(
            [
                "[Script Info]",
                "ScriptType: v4.00+",
                "PlayResX: 1080",
                "PlayResY: 1920",
                "ScaledBorderAndShadow: yes",
                "",
                "[V4+ Styles]",
                "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
                (
                    "Style: Default,"
                    f"{self.font_name},{self.font_size},"
                    f"{primary},{primary},{outline},{back},"
                    "0,0,0,0,100,100,0,0,1,"
                    f"{self.outline},{self.shadow},2,"
                    "60,60,"
                    f"{self.margin_v},1"
                ),
            ]
        )

    @staticmethod
    def _format_ass_time(sec: float) -> str:
        sec = max(0.0, float(sec))
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = sec % 60
        # ASS 使用 centiseconds
        cs = int(round((s - int(s)) * 100))
        return f"{h}:{m:02d}:{int(s):02d}.{cs:02d}"

    @staticmethod
    def _escape_ass_text(text: str) -> str:
        # 替换换行与特殊字符
        t = text.replace("\n", " ").replace("\r", " ").strip()
        t = t.replace("{", r"\{").replace("}", r"\}")
        return t


