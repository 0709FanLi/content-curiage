"""
数据模型统一出口
"""

from .auth import *
from .project import *
from .script import *
from .keyframe import *
from .video import *
from .file import *
from .response import *
from .hotspot import *
from .asset import *
from .timeline import *

__all__ = [
    # 响应
    "ApiResponse", "PageResponse",
    
    # 认证
    "UserBase", "UserCreate", "UserUpdate", "UserResponse",
    "Token", "TokenData", "LoginRequest", "LoginResponse",
    "RefreshTokenRequest", "ChangePasswordRequest",

    # 项目
    "ProjectStatus", "ProjectBase", "ProjectCreate", "ProjectUpdate", "ProjectResponse", "ProjectDetailResponse",

    # 脚本
    "ScriptSegment", "ScriptBase", "ScriptCreate", "ScriptUpdate", "ScriptResponse",
    "GenerateScriptRequest", "OptimizeScriptRequest",

    # 关键帧
    "KeyframeStatus", "KeyframeBase", "KeyframeCreate", "KeyframeUpdate", "KeyframeResponse",
    "GenerateKeyframeRequest", "GenerateKeyframesResponse", "UploadKeyframeImageRequest",

    # 视频
    "VideoStatus", "VideoSegmentBase", "VideoSegmentCreate", "VideoSegmentUpdate", "VideoSegmentResponse",
    "GenerateVideoRequest", "GenerateVideosResponse", "ExportVideosRequest", "ExportVideosResponse",

    # 文件
    "FileBase", "FileCreate", "FileUpdate", "FileResponse",
    "UploadFileResponse", "FileUploadRequest",

    # 热点
    "HotspotItem", "HotspotListResponse", "HotspotDetailSection",
    "HotspotDetailResponse", "HotspotDetailRequest",

    # 资产
    "AssetType", "AssetSource", "AssetBase", "AssetCreate", "AssetUpdate", 
    "AssetResponse", "AssetListResponse",

    # 时间线
    "TrackType", 
    "ClipBase", "ClipCreate", "ClipUpdate", "ClipResponse",
    "TrackBase", "TrackCreate", "TrackUpdate", "TrackResponse",
    "TimelineBase", "TimelineCreate", "TimelineUpdate", "TimelineResponse",
    "ClipBatchCreate", "ClipBatchUpdate", "ClipBatchDelete",
    "TimelinePatch", "TimelinePatchResponse",
]
