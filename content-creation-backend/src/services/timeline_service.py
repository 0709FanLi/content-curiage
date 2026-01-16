"""
时间线管理服务

提供 Timeline、Track、Clip 的 CRUD 操作和业务逻辑
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
import structlog

from src.models.tables.timeline import Timeline, Track, Clip, TrackType
from src.models.tables.asset import Asset
from src.models.schemas.timeline import (
    TimelineCreate, TimelineUpdate, TimelineResponse,
    TrackCreate, TrackUpdate, TrackResponse,
    ClipCreate, ClipUpdate, ClipResponse,
    TimelinePatch, TimelinePatchResponse,
)
from src.utils.exceptions import NotFoundError, BusinessError

logger = structlog.get_logger(__name__)


class TimelineService:
    """时间线管理服务类"""

    def __init__(self, db: AsyncSession):
        """
        初始化服务
        
        Args:
            db: 数据库会话
        """
        self.db = db

    # ========== Timeline CRUD ==========

    async def create_timeline(
        self, 
        project_id: int,
        data: Optional[TimelineCreate] = None
    ) -> Timeline:
        """
        创建时间线
        
        Args:
            project_id: 项目ID
            data: 时间线创建数据（可选）
            
        Returns:
            创建的时间线对象
        """
        # 检查是否已存在时间线
        existing = await self.get_timeline_by_project(project_id)
        if existing:
            raise BusinessError(f"项目 {project_id} 已存在时间线")

        timeline = Timeline(
            project_id=project_id,
            duration_ms=data.duration_ms if data else 0,
            aspect_ratio=data.aspect_ratio if data else "9:16",
            fps=data.fps if data else 30,
        )
        
        self.db.add(timeline)
        await self.db.flush()
        
        # 自动创建默认轨道
        default_tracks = [
            Track(timeline_id=timeline.id, type=TrackType.VIDEO, name="视频轨", sort_order=0),
            Track(timeline_id=timeline.id, type=TrackType.SPEECH, name="配音轨", sort_order=1),
            Track(timeline_id=timeline.id, type=TrackType.BGM, name="背景音乐", sort_order=2),
            Track(timeline_id=timeline.id, type=TrackType.CAPTION, name="字幕轨", sort_order=3),
        ]
        for track in default_tracks:
            self.db.add(track)
        
        await self.db.commit()
        await self.db.refresh(timeline)
        
        logger.info("时间线创建成功", timeline_id=timeline.id, project_id=project_id)
        return timeline

    async def get_timeline(self, timeline_id: int) -> Optional[Timeline]:
        """
        获取时间线详情（包含轨道和片段）
        
        Args:
            timeline_id: 时间线ID
            
        Returns:
            时间线对象，包含所有轨道和片段
        """
        result = await self.db.execute(
            select(Timeline)
            .where(Timeline.id == timeline_id)
            .options(
                selectinload(Timeline.tracks).selectinload(Track.clips).selectinload(Clip.asset)
            )
        )
        return result.scalar_one_or_none()

    async def get_timeline_by_project(self, project_id: int) -> Optional[Timeline]:
        """
        根据项目ID获取时间线
        
        Args:
            project_id: 项目ID
            
        Returns:
            时间线对象
        """
        result = await self.db.execute(
            select(Timeline)
            .where(Timeline.project_id == project_id)
            .options(
                selectinload(Timeline.tracks).selectinload(Track.clips).selectinload(Clip.asset)
            )
        )
        return result.scalar_one_or_none()

    async def update_timeline(
        self, 
        timeline_id: int, 
        data: TimelineUpdate,
        expected_version: Optional[int] = None
    ) -> Timeline:
        """
        更新时间线
        
        Args:
            timeline_id: 时间线ID
            data: 更新数据
            expected_version: 期望的版本号（用于乐观锁）
            
        Returns:
            更新后的时间线对象
        """
        timeline = await self.get_timeline(timeline_id)
        if not timeline:
            raise NotFoundError(f"时间线 {timeline_id} 不存在")
        
        # 乐观锁检查
        if expected_version is not None and timeline.version != expected_version:
            raise BusinessError(f"版本冲突：期望 {expected_version}，实际 {timeline.version}")
        
        # 更新字段
        update_data = data.model_dump(exclude_unset=True, by_alias=False)
        for key, value in update_data.items():
            if hasattr(timeline, key) and key != 'version':
                setattr(timeline, key, value)
        
        timeline.version += 1
        
        await self.db.commit()
        await self.db.refresh(timeline)
        
        logger.info("时间线更新成功", timeline_id=timeline_id, version=timeline.version)
        return timeline

    async def delete_timeline(self, timeline_id: int) -> bool:
        """
        删除时间线（级联删除轨道和片段）
        
        Args:
            timeline_id: 时间线ID
            
        Returns:
            是否删除成功
        """
        timeline = await self.get_timeline(timeline_id)
        if not timeline:
            return False
        
        await self.db.delete(timeline)
        await self.db.commit()
        
        logger.info("时间线删除成功", timeline_id=timeline_id)
        return True

    # ========== Track CRUD ==========

    async def create_track(self, data: TrackCreate) -> Track:
        """
        创建轨道
        
        Args:
            data: 轨道创建数据
            
        Returns:
            创建的轨道对象
        """
        track = Track(
            timeline_id=data.timeline_id,
            type=data.type,
            name=data.name,
            is_muted=data.is_muted,
            is_locked=data.is_locked,
            volume=data.volume,
            sort_order=data.sort_order,
        )
        
        self.db.add(track)
        await self.db.commit()
        await self.db.refresh(track)
        
        logger.info("轨道创建成功", track_id=track.id, type=track.type.value)
        return track

    async def get_track(self, track_id: int) -> Optional[Track]:
        """
        获取轨道详情
        
        Args:
            track_id: 轨道ID
            
        Returns:
            轨道对象
        """
        result = await self.db.execute(
            select(Track)
            .where(Track.id == track_id)
            .options(selectinload(Track.clips).selectinload(Clip.asset))
        )
        return result.scalar_one_or_none()

    async def update_track(self, track_id: int, data: TrackUpdate) -> Track:
        """
        更新轨道
        
        Args:
            track_id: 轨道ID
            data: 更新数据
            
        Returns:
            更新后的轨道对象
        """
        track = await self.get_track(track_id)
        if not track:
            raise NotFoundError(f"轨道 {track_id} 不存在")
        
        update_data = data.model_dump(exclude_unset=True, by_alias=False)
        for key, value in update_data.items():
            if hasattr(track, key):
                setattr(track, key, value)
        
        await self.db.commit()
        await self.db.refresh(track)
        
        logger.info("轨道更新成功", track_id=track_id)
        return track

    async def delete_track(self, track_id: int) -> bool:
        """
        删除轨道
        
        Args:
            track_id: 轨道ID
            
        Returns:
            是否删除成功
        """
        track = await self.get_track(track_id)
        if not track:
            return False
        
        await self.db.delete(track)
        await self.db.commit()
        
        logger.info("轨道删除成功", track_id=track_id)
        return True

    # ========== Clip CRUD ==========

    async def create_clip(self, data: ClipCreate) -> Clip:
        """
        创建片段
        
        Args:
            data: 片段创建数据
            
        Returns:
            创建的片段对象
        """
        # 验证时间范围
        if data.end_ms <= data.start_ms:
            raise BusinessError("结束时间必须大于开始时间")
        
        clip = Clip(
            track_id=data.track_id,
            asset_id=data.asset_id,
            start_ms=data.start_ms,
            end_ms=data.end_ms,
            asset_start_ms=data.asset_start_ms,
            asset_end_ms=data.asset_end_ms,
            content=data.content,
            properties=data.properties or {},
        )
        
        self.db.add(clip)
        await self.db.commit()
        await self.db.refresh(clip)
        
        # 更新时间线总时长
        await self._update_timeline_duration(clip.track_id)
        
        logger.info("片段创建成功", clip_id=clip.id, track_id=data.track_id)
        return clip

    async def create_clips_batch(self, clips_data: List[ClipCreate]) -> List[Clip]:
        """
        批量创建片段
        
        Args:
            clips_data: 片段创建数据列表
            
        Returns:
            创建的片段列表
        """
        clips = []
        track_ids = set()
        
        for data in clips_data:
            if data.end_ms <= data.start_ms:
                raise BusinessError(f"片段时间无效: {data.start_ms} - {data.end_ms}")
            
            clip = Clip(
                track_id=data.track_id,
                asset_id=data.asset_id,
                start_ms=data.start_ms,
                end_ms=data.end_ms,
                asset_start_ms=data.asset_start_ms,
                asset_end_ms=data.asset_end_ms,
                content=data.content,
                properties=data.properties or {},
            )
            self.db.add(clip)
            clips.append(clip)
            track_ids.add(data.track_id)
        
        await self.db.commit()
        
        for clip in clips:
            await self.db.refresh(clip)
        
        # 更新时间线总时长
        for track_id in track_ids:
            await self._update_timeline_duration(track_id)
        
        logger.info("批量创建片段成功", count=len(clips))
        return clips

    async def get_clip(self, clip_id: int) -> Optional[Clip]:
        """
        获取片段详情
        
        Args:
            clip_id: 片段ID
            
        Returns:
            片段对象
        """
        result = await self.db.execute(
            select(Clip)
            .where(Clip.id == clip_id)
            .options(selectinload(Clip.asset))
        )
        return result.scalar_one_or_none()

    async def update_clip(self, clip_id: int, data: ClipUpdate) -> Clip:
        """
        更新片段
        
        Args:
            clip_id: 片段ID
            data: 更新数据
            
        Returns:
            更新后的片段对象
        """
        clip = await self.get_clip(clip_id)
        if not clip:
            raise NotFoundError(f"片段 {clip_id} 不存在")
        
        update_data = data.model_dump(exclude_unset=True, by_alias=False)
        
        # 验证时间范围
        new_start = update_data.get('start_ms', clip.start_ms)
        new_end = update_data.get('end_ms', clip.end_ms)
        if new_end <= new_start:
            raise BusinessError("结束时间必须大于开始时间")
        
        for key, value in update_data.items():
            if hasattr(clip, key):
                setattr(clip, key, value)
        
        await self.db.commit()
        await self.db.refresh(clip)
        
        # 更新时间线总时长
        await self._update_timeline_duration(clip.track_id)
        
        logger.info("片段更新成功", clip_id=clip_id)
        return clip

    async def delete_clip(self, clip_id: int) -> bool:
        """
        删除片段
        
        Args:
            clip_id: 片段ID
            
        Returns:
            是否删除成功
        """
        clip = await self.get_clip(clip_id)
        if not clip:
            return False
        
        track_id = clip.track_id
        await self.db.delete(clip)
        await self.db.commit()
        
        # 更新时间线总时长
        await self._update_timeline_duration(track_id)
        
        logger.info("片段删除成功", clip_id=clip_id)
        return True

    async def delete_clips_batch(self, clip_ids: List[int]) -> int:
        """
        批量删除片段
        
        Args:
            clip_ids: 片段ID列表
            
        Returns:
            删除的数量
        """
        # 获取要删除的片段以便更新时间线
        result = await self.db.execute(
            select(Clip).where(Clip.id.in_(clip_ids))
        )
        clips = result.scalars().all()
        track_ids = set(clip.track_id for clip in clips)
        
        # 删除
        await self.db.execute(
            delete(Clip).where(Clip.id.in_(clip_ids))
        )
        await self.db.commit()
        
        # 更新时间线总时长
        for track_id in track_ids:
            await self._update_timeline_duration(track_id)
        
        logger.info("批量删除片段成功", count=len(clips))
        return len(clips)

    # ========== Helper Methods ==========

    async def _update_timeline_duration(self, track_id: int) -> None:
        """
        更新时间线总时长（基于所有片段的最大结束时间）
        
        Args:
            track_id: 轨道ID
        """
        track = await self.get_track(track_id)
        if not track:
            return
        
        timeline = await self.get_timeline(track.timeline_id)
        if not timeline:
            return
        
        # 计算所有轨道中片段的最大结束时间
        max_end_ms = 0
        for t in timeline.tracks:
            for clip in t.clips:
                if clip.end_ms > max_end_ms:
                    max_end_ms = clip.end_ms
        
        if timeline.duration_ms != max_end_ms:
            timeline.duration_ms = max_end_ms
            timeline.version += 1
            await self.db.commit()
            logger.info("时间线时长更新", timeline_id=timeline.id, duration_ms=max_end_ms)

    async def get_or_create_timeline(self, project_id: int) -> Timeline:
        """
        获取或创建项目的时间线
        
        Args:
            project_id: 项目ID
            
        Returns:
            时间线对象
        """
        timeline = await self.get_timeline_by_project(project_id)
        if not timeline:
            timeline = await self.create_timeline(project_id)
        return timeline

    async def get_track_by_type(
        self, 
        timeline_id: int, 
        track_type: TrackType
    ) -> Optional[Track]:
        """
        根据类型获取轨道
        
        Args:
            timeline_id: 时间线ID
            track_type: 轨道类型
            
        Returns:
            轨道对象
        """
        result = await self.db.execute(
            select(Track)
            .where(Track.timeline_id == timeline_id, Track.type == track_type)
            .options(selectinload(Track.clips))
        )
        return result.scalar_one_or_none()

    # ========== Patch Operation (用于撤销/重做) ==========

    async def apply_patch(self, patch: TimelinePatch) -> TimelinePatchResponse:
        """
        应用时间线补丁操作
        
        Args:
            patch: 补丁数据
            
        Returns:
            补丁响应
        """
        try:
            affected_ids = []
            
            if patch.operation == "add_clip" and patch.data:
                clip_data = ClipCreate(**patch.data)
                clip = await self.create_clip(clip_data)
                affected_ids.append(clip.id)
                
            elif patch.operation == "update_clip" and patch.target_id:
                clip_data = ClipUpdate(**patch.data) if patch.data else ClipUpdate()
                clip = await self.update_clip(patch.target_id, clip_data)
                affected_ids.append(clip.id)
                
            elif patch.operation == "delete_clip" and patch.target_id:
                await self.delete_clip(patch.target_id)
                affected_ids.append(patch.target_id)
                
            elif patch.operation == "move_clip" and patch.target_id and patch.data:
                clip_data = ClipUpdate(
                    start_ms=patch.data.get('start_ms'),
                    end_ms=patch.data.get('end_ms')
                )
                clip = await self.update_clip(patch.target_id, clip_data)
                affected_ids.append(clip.id)
            
            # 获取最新版本号
            if patch.target_type == "clip" and patch.target_id:
                clip = await self.get_clip(patch.target_id if patch.operation != "delete_clip" else affected_ids[0])
                if clip:
                    track = await self.get_track(clip.track_id)
                    timeline = await self.get_timeline(track.timeline_id) if track else None
                    new_version = timeline.version if timeline else patch.version + 1
                else:
                    new_version = patch.version + 1
            else:
                new_version = patch.version + 1
            
            return TimelinePatchResponse(
                success=True,
                new_version=new_version,
                affected_ids=affected_ids
            )
            
        except Exception as e:
            logger.error("补丁应用失败", error=str(e), patch=patch.model_dump())
            return TimelinePatchResponse(
                success=False,
                new_version=patch.version,
                affected_ids=[],
                error=str(e)
            )


