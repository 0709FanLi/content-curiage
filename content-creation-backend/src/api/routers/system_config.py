"""
系统配置相关API路由
"""

import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict

from ...models.database import get_db
from ...models.tables.project import Project
from ...models.tables.script import Script
from ...models.tables.user import User
from ...models.schemas.system_config import SystemConfigUpdate
from ...services.prompt_rules_audit_service import PromptRulesAuditService
from ...services.system_config_service import SystemConfigService
from ...services.upload_limiter import upload_limiter
from ..dependencies import get_current_active_user
import structlog
from sqlalchemy import select
from ...utils.exceptions import ApiError

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/config", tags=["系统配置"])


@router.get("/script-prompt")
async def get_script_prompt(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict:
    """
    获取脚本生成提示词
    
    Returns:
        包含提示词的字典
    """
    config_service = SystemConfigService(db)
    prompt = await config_service.get_script_prompt()
    
    return {
        "code": 200,
        "message": "success",
        "data": {
            "prompt": prompt
        }
    }


@router.put("/script-prompt")
async def update_script_prompt(
    update_data: Dict,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict:
    """
    更新脚本生成提示词
    
    Args:
        update_data: 包含prompt字段的字典
        
    Returns:
        更新结果
    """
    prompt = update_data.get("prompt")
    if not prompt:
        return {
            "code": 400,
            "message": "提示词不能为空",
            "data": None
        }
    
    config_service = SystemConfigService(db)
    config = await config_service.update_script_prompt(prompt)
    
    logger.info(
        "Script prompt updated",
        user_id=current_user.id,
        username=current_user.username
    )
    
    return {
        "code": 200,
        "message": "提示词更新成功",
        "data": {
            "prompt": config.config_value,
            "updated_at": config.updated_at.isoformat()
        }
    }


@router.get("/upload-stats")
async def get_upload_stats(
    current_user: User = Depends(get_current_active_user)
) -> Dict:
    """
    获取转存任务统计信息
    
    Returns:
        包含转存统计信息的字典
    """
    stats = upload_limiter.get_stats()
    
    return {
        "code": 200,
        "message": "success",
        "data": stats
    }


@router.post("/kf-video-rules/audit")
async def manual_audit_kf_video_rules(
    payload: Dict,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Dict:
    """手动触发“关键帧/视频规则片段”迭代（默认关闭，避免误上生产）."""
    enabled = os.getenv("ENABLE_MANUAL_RULES_AUDIT", "false").strip().lower() in {"1", "true", "yes", "y", "on"}
    if not enabled:
        return {"code": 403, "message": "手动迭代功能未启用", "data": None}

    script_id = payload.get("scriptId")
    if not script_id:
        return {"code": 400, "message": "scriptId 不能为空", "data": None}

    # 校验脚本归属：script -> project -> user
    stmt = (
        select(Script)
        .join(Project, Script.project_id == Project.id)
        .where(Script.id == int(script_id), Project.user_id == current_user.id)
    )
    result = await db.execute(stmt)
    script = result.scalar_one_or_none()
    if not script:
        return {"code": 404, "message": "脚本不存在或无权限", "data": None}

    audit_service = PromptRulesAuditService(db)
    try:
        audit_result = await audit_service.audit_and_update_kf_video_rules(
            script_text=script.content,
            model=os.getenv("RULES_AUDIT_MODEL", "gemini-3-pro"),
        )

        script.rules_audit_status = "processed"
        script.rules_audit_changed = audit_result.changed
        script.rules_audit_model = audit_result.model
        script.rules_audit_checked_at = audit_result.audited_at
        script.rules_audit_error = None
        await db.commit()

        return {
            "code": 200,
            "message": "success",
            "data": {"changed": audit_result.changed},
        }
    except ApiError as e:
        script.rules_audit_status = "failed"
        script.rules_audit_changed = None
        script.rules_audit_model = os.getenv("RULES_AUDIT_MODEL", "gemini-3-pro")
        script.rules_audit_checked_at = datetime.now(timezone.utc)
        script.rules_audit_error = f"{e.status_code}: {e.detail}"
        await db.commit()
        logger.error("Manual rules audit failed(ApiError)", script_id=script.id, error=str(e), exc_info=True)
        return {"code": e.status_code, "message": str(e.detail), "data": None}
    except Exception as e:
        script.rules_audit_status = "failed"
        script.rules_audit_changed = None
        script.rules_audit_model = os.getenv("RULES_AUDIT_MODEL", "gemini-3-pro")
        script.rules_audit_checked_at = datetime.now(timezone.utc)
        script.rules_audit_error = str(e)
        await db.commit()
        logger.error("Manual rules audit failed", script_id=script.id, error=str(e), exc_info=True)
        return {"code": 500, "message": "手动迭代失败", "data": None}

