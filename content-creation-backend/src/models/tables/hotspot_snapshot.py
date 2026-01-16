"""
热点列表缓存快照表
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import DateTime, Integer, Text, func, JSON
from sqlalchemy.orm import Mapped, mapped_column

from src.models.database import Base


class HotspotSnapshot(Base):
    """热点列表快照（缓存）。"""

    __tablename__ = "hotspot_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="拉取时间（缓存生成时间）",
    )

    daily_summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="每日总结",
    )

    hotspots: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSON,
        nullable=True,
        comment="热点列表（JSON）",
    )


