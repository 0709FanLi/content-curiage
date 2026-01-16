"""
日间规则审查调度器

在 9/12/15/18 点自动挑选最早未处理脚本，调用 Gemini 审查并按需更新
“关键帧/视频规则片段”，从而让后续脚本更不容易描述出会导致画面出现中文文字的内容。

说明：
- 不回头重生成脚本；只更新全局提示词片段，下一次生成自然生效。
- 使用 Redis 锁（可用则优先）避免同一时间段重复运行；Redis 不可用则退化为 DB 锁（system_config）。
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Optional

import structlog
from sqlalchemy import select

from src.models.database import async_session_maker
from src.models.tables.script import Script
from src.services.prompt_rules_audit_service import PromptRulesAuditService
from src.services.system_config_service import SystemConfigService
from src.models.schemas.system_config import SystemConfigUpdate

logger = structlog.get_logger(__name__)


RUN_HOURS = {9, 12, 15, 18}


def _is_enabled() -> bool:
    value = os.getenv("ENABLE_DAYTIME_RULES_AUDIT", "true").strip().lower()
    return value in {"1", "true", "yes", "y", "on"}


def _get_model_name() -> str:
    return os.getenv("RULES_AUDIT_MODEL", "gemini-3-pro").strip() or "gemini-3-pro"


async def _try_acquire_lock_with_db(slot_key: str) -> bool:
    """使用 system_config 作为幂等锁（退化方案）。"""
    async with async_session_maker() as db:
        config_service = SystemConfigService(db)
        # 确保 key 存在
        await config_service.get_or_create_config(
            config_key="rules_audit_last_slot",
            default_value="",
            description="规则审查最后运行 slot（YYYYMMDDHH）",
        )
        last = await config_service.get_config_value("rules_audit_last_slot", default="")
        if last == slot_key:
            return False
        await config_service.update_config(
            "rules_audit_last_slot",
            config_data=SystemConfigUpdate(
                config_value=slot_key,
                description="规则审查最后运行 slot（YYYYMMDDHH）",
            ),
        )
        return True


async def _try_acquire_lock(slot_key: str) -> bool:
    """尽量用 Redis 锁，失败则退化为 DB 锁。"""
    try:
        from src.utils.redis_client import RedisClient

        redis = await RedisClient.get_instance()
        ok = await redis.set(f"rules_audit:slot:{slot_key}", "1", ex=3 * 60 * 60, nx=True)
        return bool(ok)
    except Exception as exc:
        logger.warning("Redis lock unavailable, fallback to DB lock", error=str(exc))
        return await _try_acquire_lock_with_db(slot_key)


async def _pick_oldest_unprocessed_script(db) -> Optional[Script]:
    stmt = (
        select(Script)
        .where((Script.rules_audit_status.is_(None)) | (Script.rules_audit_status != "processed"))
        .order_by(Script.created_at.asc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def run_once_if_due() -> None:
    """检查当前时间是否命中运行窗口，若命中则执行一次审查。"""
    if not _is_enabled():
        return

    now = datetime.now()
    if now.hour not in RUN_HOURS:
        return

    # 允许在整点后的前 10 分钟内触发（避免服务重启错过精确整点）
    if now.minute >= 10:
        return

    slot_key = now.strftime("%Y%m%d%H")
    acquired = await _try_acquire_lock(slot_key)
    if not acquired:
        return

    model = _get_model_name()
    async with async_session_maker() as db:
        script = await _pick_oldest_unprocessed_script(db)
        if not script:
            logger.info("No unprocessed script found for rules audit")
            return

        logger.info(
            "Running rules audit",
            script_id=script.id,
            project_id=script.project_id,
            model=model,
        )

        service = PromptRulesAuditService(db)
        try:
            result = await service.audit_and_update_kf_video_rules(script_text=script.content, model=model)
            script.rules_audit_status = "processed"
            script.rules_audit_changed = result.changed
            script.rules_audit_model = result.model
            script.rules_audit_checked_at = result.audited_at
            script.rules_audit_error = None
            await db.commit()
        except Exception as exc:
            script.rules_audit_status = "failed"
            script.rules_audit_changed = None
            script.rules_audit_model = model
            script.rules_audit_checked_at = datetime.now(timezone.utc)
            script.rules_audit_error = str(exc)
            await db.commit()
            logger.error("Rules audit failed", script_id=script.id, error=str(exc), exc_info=True)


async def start_daytime_rules_audit_loop() -> None:
    """启动日间循环（在 FastAPI lifespan 中以 create_task 方式运行）。"""
    logger.info("Daytime rules audit loop started", enabled=_is_enabled(), run_hours=sorted(RUN_HOURS))
    while True:
        try:
            await run_once_if_due()
        except Exception as exc:
            logger.error("Daytime rules audit loop error", error=str(exc), exc_info=True)
        await asyncio.sleep(60)


