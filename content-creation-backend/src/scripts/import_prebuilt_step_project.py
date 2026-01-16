"""
Import a prebuilt step-by-step project into the production database.

This script is designed for the "I already have keyframes + final video URL" case.
It writes records directly into:
- projects
- scripts
- keyframes
- video_segments

It does NOT call any external model APIs.

Run inside the production backend container (recommended), so DB config matches
the running service.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import datetime
import re
from typing import Iterable, List, Optional

import structlog
from sqlalchemy import select

from src.models.database import async_session_maker
from src.models.tables.project import Project, ProjectStatus
from src.models.tables.script import Script
from src.models.tables.keyframe import Keyframe, KeyframeStatus
from src.models.tables.video_segment import VideoSegment, VideoStatus
from src.models.tables.user import User

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class PrebuiltProjectInput:
    """Parsed input for a prebuilt project import."""

    title: str
    keyframe_urls: List[str]
    final_video_url: str
    aspect_ratio: str


def _read_text_file(path: str) -> str:
    """Read a UTF-8 text file."""

    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def parse_proje_txt(path: str, *, aspect_ratio: str) -> PrebuiltProjectInput:
    """Parse `src/proje/p*.txt` into structured input.

    Expected format (spaces are flexible):
        1. 标题：xxx
        2. 关键帧
            https://...
        3. 视频
            https://...

    Args:
        path: Input file path.
        aspect_ratio: Project aspect ratio, e.g. "9:16" or "16:9".

    Returns:
        Parsed input.

    Raises:
        ValueError: When required fields are missing.
    """

    raw = _read_text_file(path)
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]

    title: Optional[str] = None
    keyframe_urls: List[str] = []
    final_video_url: Optional[str] = None

    mode: Optional[str] = None  # "keyframes" | "video"
    for ln in lines:
        if "标题" in ln:
            # e.g. "1. 标题：xxx"
            parts = re.split(r"标题[:：]", ln, maxsplit=1)
            if len(parts) == 2 and parts[1].strip():
                title = parts[1].strip()
            continue

        if "关键帧" in ln:
            mode = "keyframes"
            continue

        if ln.startswith("3.") and "视频" in ln:
            mode = "video"
            continue

        if ln.startswith("http://") or ln.startswith("https://"):
            if mode == "keyframes":
                keyframe_urls.append(ln)
            elif mode == "video":
                # only take the first video url
                if final_video_url is None:
                    final_video_url = ln

    if not title:
        raise ValueError(f"Missing title in {path}")
    if len(keyframe_urls) < 1:
        raise ValueError(f"Need at least 1 keyframe (segment_0), got {len(keyframe_urls)}")
    if not final_video_url:
        raise ValueError(f"Missing final video URL in {path}")
    if aspect_ratio not in {"9:16", "16:9"}:
        raise ValueError(f"Invalid aspect_ratio: {aspect_ratio}")

    return PrebuiltProjectInput(
        title=title,
        keyframe_urls=keyframe_urls,
        final_video_url=final_video_url,
        aspect_ratio=aspect_ratio,
    )


def _build_placeholder_script_content(
    *,
    segment_count: int,
    segment_duration: int,
) -> str:
    """Build a minimal script text that the parser/UI can display.

    Args:
        segment_count: Number of non-frame0 segments.
        segment_duration: Duration per segment in seconds.

    Returns:
        Script content.
    """

    total_duration = segment_count * segment_duration
    lines: List[str] = []
    lines.append(
        "第0帧：开场画面占位。用于在系统内展示已导入素材，不触发任何模型生成。"
    )

    for i in range(segment_count):
        start = i * segment_duration
        end = min(total_duration, (i + 1) * segment_duration)
        lines.append(f"({start}-{end}s)")
        lines.append("口播文案：")
        lines.append("关键帧：")
        lines.append("视频：")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def _build_placeholder_segments(
    *,
    segment_count: int,
    segment_duration: int,
) -> List[dict]:
    """Build placeholder `scripts.segments` JSON list.

    Note: routers often return DB JSON directly (snake_case keys), so we keep
    snake_case field names.
    """

    segments: List[dict] = []
    for i in range(segment_count):
        start = float(i * segment_duration)
        end = float((i + 1) * segment_duration)
        segments.append(
            {
                "id": f"segment_{i}",
                "time_start": start,
                "time_end": end,
                "content": "",
                "narration": "",
                "keyframe_desc": "",
                "video_desc": "",
            }
        )
    return segments


def _segment_ids_for_keyframes(keyframe_urls: List[str]) -> List[str]:
    """Map keyframe URLs to system segment_ids.

    Rule:
    - keyframe_urls[0]  -> segment_0
    - keyframe_urls[1:] -> segment_1, segment_2, ...
    """

    segment_ids: List[str] = []
    for i in range(len(keyframe_urls)):
        segment_ids.append(f"segment_{i}")
    return segment_ids


def _iter_pairs(items: List[str]) -> Iterable[tuple[str, Optional[str]]]:
    """Yield (current, next) pairs."""

    for i in range(len(items)):
        cur = items[i]
        nxt = items[i + 1] if i + 1 < len(items) else None
        yield cur, nxt


async def _get_user_id_by_email(email: str) -> int:
    """Get user id by email.

    Raises:
        ValueError: If user is not found.
    """

    async with async_session_maker() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError(f"User not found: {email}")
        return int(user.id)


async def import_prebuilt_project(
    *,
    input_path: str,
    user_email: str,
    aspect_ratio: str,
    segment_duration: int = 4,
    video_model: Optional[str] = None,
    commit: bool = False,
    force: bool = False,
) -> dict:
    """Import a single prebuilt project.

    Args:
        input_path: Path to p*.txt.
        user_email: Owner email.
        aspect_ratio: "9:16" or "16:9".
        segment_duration: Segment duration, seconds.
        video_model: Optional model id to fill into video_segments.model.
        commit: If False, performs a dry-run and rolls back.
        force: If True, bypass de-duplication check.

    Returns:
        Created ids and summary.
    """

    parsed = parse_proje_txt(input_path, aspect_ratio=aspect_ratio)
    user_id = await _get_user_id_by_email(user_email)

    segment_count = len(parsed.keyframe_urls)
    total_duration = segment_count * int(segment_duration)

    async with async_session_maker() as db:
        # De-dupe by exported_video_url to prevent accidental double import.
        if not force:
            existing = await db.execute(
                select(Script).where(Script.exported_video_url == parsed.final_video_url)
            )
            if existing.scalar_one_or_none():
                raise ValueError(
                    "A script with the same exported_video_url already exists. "
                    "Use --force to import anyway."
                )

        project = Project(
            name=parsed.title,
            description=None,
            status=ProjectStatus.COMPLETED,
            user_id=user_id,
            aspect_ratio=parsed.aspect_ratio,
            generation_mode="step_by_step",
            first_script_generated_at=datetime.now(),
        )
        db.add(project)
        await db.flush()

        script_content = _build_placeholder_script_content(
            segment_count=segment_count, segment_duration=int(segment_duration)
        )
        script_segments = _build_placeholder_segments(
            segment_count=segment_count, segment_duration=int(segment_duration)
        )
        script = Script(
            project_id=int(project.id),
            content=script_content,
            style=None,
            total_duration=total_duration,
            segment_duration=int(segment_duration),
            segments=script_segments,
            exported_video_url=parsed.final_video_url,
        )
        db.add(script)
        await db.flush()

        # Keyframes
        segment_ids = _segment_ids_for_keyframes(parsed.keyframe_urls)
        keyframes: List[Keyframe] = []
        for seg_id, url in zip(segment_ids, parsed.keyframe_urls):
            kf = Keyframe(
                script_id=int(script.id),
                segment_id=seg_id,
                image_url=url,
                prompt=None,
                status=KeyframeStatus.COMPLETED,
                error_message=None,
            )
            db.add(kf)
            keyframes.append(kf)
        await db.flush()

        # Video segments (use final video URL for each segment preview/download)
        # 全局移除第0帧后：segment_0 即首段关键帧，第一段视频也以 segment_0 为首帧参考。
        for i, (cur_kf_url, next_kf_url) in enumerate(_iter_pairs(parsed.keyframe_urls)):
            vs = VideoSegment(
                script_id=int(script.id),
                segment_index=i,
                first_frame_url=cur_kf_url,
                last_frame_url=next_kf_url,
                prompt=None,
                video_url=parsed.final_video_url,
                model=video_model,
                aspect_ratio=parsed.aspect_ratio,
                status=VideoStatus.COMPLETED,
                duration=float(segment_duration),
                task_id=None,
                error_message=None,
            )
            db.add(vs)

        await db.flush()

        summary = {
            "project_id": int(project.id),
            "script_id": int(script.id),
            "keyframes_count": len(parsed.keyframe_urls),
            "video_segments_count": segment_count,
            "exported_video_url": parsed.final_video_url,
            "commit": commit,
        }

        if commit:
            await db.commit()
            logger.info("Import committed", **summary)
        else:
            await db.rollback()
            logger.info("Dry-run completed (rolled back)", **summary)

        return summary


def build_arg_parser() -> argparse.ArgumentParser:
    """Build CLI parser."""

    parser = argparse.ArgumentParser(
        description="Import a prebuilt step-by-step project into DB (no model calls)."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Input file path, e.g. /app/src/proje/p1.txt",
    )
    parser.add_argument(
        "--user-email",
        required=True,
        help="Project owner email, e.g. test123@123.com",
    )
    parser.add_argument(
        "--aspect-ratio",
        required=True,
        choices=["9:16", "16:9"],
        help="Project aspect ratio.",
    )
    parser.add_argument(
        "--segment-duration",
        type=int,
        default=4,
        help="Segment duration in seconds (default: 4).",
    )
    parser.add_argument(
        "--video-model",
        default=None,
        help="Optional model id to fill into video_segments.model.",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Actually write to DB. If omitted, runs dry-run and rolls back.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass de-duplication check (exported_video_url).",
    )
    return parser


async def _main_async() -> None:
    """Async CLI entrypoint."""

    args = build_arg_parser().parse_args()

    summary = await import_prebuilt_project(
        input_path=str(args.input),
        user_email=str(args.user_email),
        aspect_ratio=str(args.aspect_ratio),
        segment_duration=int(args.segment_duration),
        video_model=args.video_model,
        commit=bool(args.commit),
        force=bool(args.force),
    )

    # Keep the output minimal and machine-friendly.
    logger.info("Import finished", **summary)


def main() -> None:
    """CLI entrypoint."""

    asyncio.run(_main_async())


if __name__ == "__main__":
    main()

