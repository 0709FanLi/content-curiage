"""
热点缓存服务
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.schemas.hotspot import HotspotListResponse
from src.models.tables.hotspot_snapshot import HotspotSnapshot

logger = structlog.get_logger(__name__)


class HotspotCacheService:
    """热点列表缓存服务（数据库快照）。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_latest_snapshot(self) -> Optional[HotspotSnapshot]:
        """获取最新一条快照。"""
        result = await self.db.execute(
            select(HotspotSnapshot).order_by(HotspotSnapshot.fetched_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def save_snapshot(self, hotspot_list: HotspotListResponse) -> HotspotSnapshot:
        """保存一条快照。"""
        snapshot = HotspotSnapshot(
            daily_summary=hotspot_list.daily_summary,
            hotspots=[h.model_dump() for h in hotspot_list.hotspots],
        )
        self.db.add(snapshot)
        await self.db.commit()
        await self.db.refresh(snapshot)
        logger.info(
            "Hotspot snapshot saved",
            snapshot_id=snapshot.id,
            hotspot_count=len(hotspot_list.hotspots),
        )
        return snapshot

    @staticmethod
    def is_stale(snapshot: HotspotSnapshot, max_age_hours: int = 2) -> bool:
        """判断快照是否过期（默认 2 小时）。"""
        fetched_at = snapshot.fetched_at
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - fetched_at > timedelta(hours=max_age_hours)


