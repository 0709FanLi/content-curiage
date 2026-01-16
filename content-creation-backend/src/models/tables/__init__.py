"""
表模型统一出口
"""

from .user import User
from .project import Project, ProjectStatus
from .script import Script
from .keyframe import Keyframe, KeyframeStatus
from .video_segment import VideoSegment, VideoStatus
from .file import File
from .system_config import SystemConfig
from .hotspot_snapshot import HotspotSnapshot
from .asset import Asset, AssetType, AssetSource
from .timeline import Timeline, Track, Clip, TrackType

__all__ = [
    "User",
    "Project",
    "ProjectStatus",
    "Script",
    "Keyframe",
    "KeyframeStatus",
    "VideoSegment",
    "VideoStatus",
    "File",
    "SystemConfig",
    "HotspotSnapshot",
    # Timeline 相关
    "Asset",
    "AssetType",
    "AssetSource",
    "Timeline",
    "Track",
    "Clip",
    "TrackType",
]
