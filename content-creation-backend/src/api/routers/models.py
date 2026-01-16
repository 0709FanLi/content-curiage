"""
模型管理路由
提供可用模型列表和脚本风格列表
"""

from typing import List, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
import structlog

from src.models.database import get_db
from src.services.llm_service import LLMService
from src.services.script_service import ScriptService
from src.services.image_model_service import ImageModelService
from src.services.system_config_service import SystemConfigService
from src.services.model_status_service import model_status_service

router = APIRouter()
logger = structlog.get_logger(__name__)


class ScriptStyleItem(BaseModel):
    """脚本风格项"""
    id: str
    name: str
    description: str
    usage: Optional[str] = None  # 用途说明，可选字段


class UpdateScriptStylesRequest(BaseModel):
    """更新脚本风格请求"""
    styles: List[ScriptStyleItem]


@router.get("/script")
async def get_script_models():
    """
    获取可用于脚本生成的模型列表（过滤掉不可用的 GRSAI 模型）
    
    Returns:
        可用模型列表
    """
    llm_service = LLMService()
    all_models = llm_service.get_available_models()
    
    # 获取 GRSAI 可用的脚本模型
    grsai_available_models = model_status_service.get_available_models("script")
    
    # 过滤模型列表
    filtered_models = []
    for model in all_models:
        model_id = model.get("id", "")
        
        # 如果是 GRSAI 模型，检查可用性
        if model_id in model_status_service.grsai_models.get("script", []):
            if model_id in grsai_available_models:
                filtered_models.append(model)
            else:
                logger.debug("Filtering out unavailable GRSAI model", model=model_id)
        else:
            # 非 GRSAI 模型，直接包含
            filtered_models.append(model)
    
    logger.info(
        "Retrieved script models",
        total_count=len(all_models),
        filtered_count=len(filtered_models)
    )
    
    return {
        "code": 200,
        "message": "success",
        "data": filtered_models
    }


@router.get("/script-styles")
async def get_script_styles(db: AsyncSession = Depends(get_db)):
    """
    获取脚本风格列表
    
    Returns:
        脚本风格列表
    """
    config_service = SystemConfigService(db)
    styles = await config_service.get_script_styles()
    
    logger.info("Retrieved script styles", count=len(styles))
    
    return {
        "code": 200,
        "message": "success",
        "data": styles
    }


@router.put("/script-styles")
async def update_script_styles(
    request: UpdateScriptStylesRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    更新脚本风格列表
    
    Args:
        request: 更新脚本风格请求
        db: 数据库会话
        
    Returns:
        更新后的脚本风格列表
    """
    try:
        config_service = SystemConfigService(db)
        
        # 转换为字典列表
        styles_data = [style.model_dump() for style in request.styles]
        
        # 更新配置
        await config_service.update_script_styles(styles_data)
        
        logger.info("Updated script styles", count=len(styles_data))
        
        return {
            "code": 200,
            "message": "success",
            "data": styles_data
        }
    except Exception as e:
        logger.error("Failed to update script styles", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/image")
async def get_image_models():
    """
    获取可用于图片生成的模型列表（过滤掉不可用的 GRSAI 模型）
    
    Returns:
        可用图片模型列表
    """
    all_models = ImageModelService.get_available_models()
    
    # 获取 GRSAI 可用的图片模型
    grsai_available_models = model_status_service.get_available_models("image")
    
    # 过滤模型列表
    filtered_models = []
    for model in all_models:
        model_id = model.get("id", "")
        
        # 如果是 GRSAI 模型，检查可用性
        if model_id in model_status_service.grsai_models.get("image", []):
            if model_id in grsai_available_models:
                filtered_models.append(model)
            else:
                logger.debug("Filtering out unavailable GRSAI model", model=model_id)
        else:
            # 非 GRSAI 模型，直接包含
            filtered_models.append(model)
    
    logger.info(
        "Retrieved image models",
        total_count=len(all_models),
        filtered_count=len(filtered_models)
    )
    
    return {
        "code": 200,
        "message": "success",
        "data": filtered_models
    }


@router.get("/status")
async def get_model_status():
    """
    获取模型监控状态信息
    
    Returns:
        模型监控状态
    """
    status_info = model_status_service.get_status_info()
    
    logger.info("Retrieved model status info")
    
    return {
        "code": 200,
        "message": "success",
        "data": status_info
    }


@router.get("/video")
async def get_video_models():
    """
    获取可用于视频生成的模型列表（过滤掉不可用的 GRSAI 模型）
    
    Returns:
        可用视频模型列表
    """
    # 统一使用与分步生成一致的后端可用模型列表（已按推荐顺序排序，并过滤不可用 GRSAI 模型）
    from src.services.video_service import VideoService

    available_models = VideoService.get_available_models()
    simplified_models = [
        {
            "id": m["id"],
            "name": m["name"],
            "aspectRatios": [],
            "qualities": [],
        }
        for m in available_models
    ]

    logger.info("Retrieved video models", total_count=len(simplified_models))
    return simplified_models


