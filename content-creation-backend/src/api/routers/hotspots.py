"""
热点情报路由
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
import structlog

from sqlalchemy.ext.asyncio import AsyncSession
from src.models.database import get_db
from src.models.schemas.hotspot import (
    HotspotListResponse,
    HotspotDetailRequest,
    HotspotDetailResponse
)
from src.models.schemas.response import ApiResponse
from src.services.coze_service import get_coze_service
from src.services.hotspot_cache_service import HotspotCacheService
from src.utils.exceptions import ExternalServiceError, ValidationError

router = APIRouter()
logger = structlog.get_logger(__name__)

async def _fetch_hotspot_detail_by_title(title: str) -> HotspotDetailResponse:
    """
    获取热点详情（公共逻辑，供 GET/POST 两种入口复用）。

    Args:
        title: 热点标题

    Returns:
        HotspotDetailResponse: 热点详情响应

    Raises:
        ValidationError: 标题为空或不合法
        ExternalServiceError: 外部服务调用失败
        Exception: 其他未知错误
    """
    if not title or not title.strip():
        raise ValidationError("热点标题不能为空")

    return await get_coze_service().get_hotspot_detail(title.strip())


@router.get("", response_model=ApiResponse[HotspotListResponse])
async def get_hotspots(db: AsyncSession = Depends(get_db)):
    """
    获取今日热点列表
    
    Returns:
        热点列表数据，包含每日总结和热点项列表
    """
    try:
        logger.info("收到获取热点列表请求")

        cache_service = HotspotCacheService(db)
        latest = await cache_service.get_latest_snapshot()
        if latest and latest.hotspots is not None:
            # 直接返回缓存
            cached = HotspotListResponse(
                daily_summary=latest.daily_summary or "",
                hotspots=latest.hotspots or [],
            )
            logger.info(
                "返回热点列表缓存",
                snapshot_id=latest.id,
                hotspot_count=len(cached.hotspots),
            )
            return ApiResponse(code=200, message="成功获取热点列表", data=cached)

        # 无缓存：回源拉取并写入
        hotspot_list = await get_coze_service().get_hotspots()
        await cache_service.save_snapshot(hotspot_list)
        
        logger.info(
            "成功获取热点列表",
            hotspot_count=len(hotspot_list.hotspots)
        )
        
        return ApiResponse(
            code=200,
            message="成功获取热点列表",
            data=hotspot_list
        )
        
    except ValueError as e:
        logger.warning("获取热点列表失败 - 配置错误", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"热点功能未配置: {str(e)}"
        )
    except ExternalServiceError as e:
        logger.error("获取热点列表失败 - 外部服务错误", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(getattr(e, "detail", str(e))),
        )
    except Exception as e:
        logger.error(
            "获取热点列表失败 - 未知错误",
            error=str(e),
            error_type=type(e).__name__
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取热点列表失败: {str(e)}"
        )


@router.get("/detail", response_model=ApiResponse[HotspotDetailResponse])
async def get_hotspot_detail_by_query(
    title: str = Query(..., min_length=1, max_length=500, description="热点标题"),
):
    """
    获取热点详情分析（GET 兼容接口，便于浏览器/调试工具直接访问）。

    Args:
        title: 热点标题（query 参数）

    Returns:
        热点详情数据，包含科学支撑、转化策略、建议结构三个部分
    """
    try:
        logger.info("收到获取热点详情请求(GET)", title=title)

        hotspot_detail = await _fetch_hotspot_detail_by_title(title)

        logger.info(
            "成功获取热点详情(GET)",
            title=title,
            has_trust=bool(hotspot_detail.trust.content),
            has_conversion=bool(hotspot_detail.conversion.content),
            has_structure=bool(hotspot_detail.structure.content),
        )

        return ApiResponse(
            code=200,
            message="成功获取热点详情",
            data=hotspot_detail,
        )

    except ValidationError as e:
        logger.warning("获取热点详情失败(GET) - 验证错误", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except ValueError as e:
        logger.warning("获取热点详情失败(GET) - 配置错误", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"热点功能未配置: {str(e)}",
        )
    except ExternalServiceError as e:
        logger.error("获取热点详情失败(GET) - 外部服务错误", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"获取热点详情失败: {str(e)}",
        )
    except Exception as e:
        logger.error(
            "获取热点详情失败(GET) - 未知错误",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取热点详情失败: {str(e)}",
        )


@router.post("/detail", response_model=ApiResponse[HotspotDetailResponse])
async def get_hotspot_detail(request: HotspotDetailRequest):
    """
    获取热点详情分析
    
    Args:
        request: 热点详情请求，包含热点标题
        
    Returns:
        热点详情数据，包含科学支撑、转化策略、建议结构三个部分
    """
    try:
        logger.info("收到获取热点详情请求", title=request.title)

        hotspot_detail = await _fetch_hotspot_detail_by_title(request.title)

        logger.info(
            "成功获取热点详情",
            title=request.title,
            has_trust=bool(hotspot_detail.trust.content),
            has_conversion=bool(hotspot_detail.conversion.content),
            has_structure=bool(hotspot_detail.structure.content)
        )
        
        return ApiResponse(
            code=200,
            message="成功获取热点详情",
            data=hotspot_detail
        )
        
    except ValidationError as e:
        logger.warning("获取热点详情失败 - 验证错误", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ValueError as e:
        logger.warning("获取热点详情失败 - 配置错误", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"热点功能未配置: {str(e)}"
        )
    except ExternalServiceError as e:
        logger.error("获取热点详情失败 - 外部服务错误", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(getattr(e, "detail", str(e))),
        )
    except Exception as e:
        logger.error(
            "获取热点详情失败 - 未知错误",
            error=str(e),
            error_type=type(e).__name__
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取热点详情失败: {str(e)}"
        )

