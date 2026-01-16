"""
提示词规则审查服务

职责：
- 读取当前“关键帧/视频规则片段”
- 把（规则片段 + 已生成脚本）交给 gemini-3-pro 审查
- 若返回了更新片段，则全局替换写回脚本生成提示词（system_config）

注意：外部大模型调用封装在 llm_service.py 中，本服务只做编排。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import json
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.llm_service import LLMService
from src.services.system_config_service import SystemConfigService
from src.models.schemas.system_config import SystemConfigUpdate
from src.utils.exceptions import ValidationError

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class RulesAuditResult:
    """规则审查结果."""

    changed: bool
    previous_snippet: str
    updated_snippet: str
    model: str
    audited_at: datetime


class PromptRulesAuditService:
    """提示词规则审查服务类."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.config_service = SystemConfigService(db)
        self.llm_service = LLMService()

    async def audit_and_update_kf_video_rules(
        self,
        *,
        script_text: str,
        model: str = "gemini-3-pro",
        max_script_chars: int = 12000,
    ) -> RulesAuditResult:
        """审查脚本并按需全局更新关键帧/视频规则片段.

        Args:
            script_text: 已生成脚本全文（中文）
            model: 审查模型（默认 gemini-3-pro）
            max_script_chars: 传入审查模型的脚本长度上限，避免过长导致失败

        Returns:
            审查结果（含是否变更）
        """
        if not script_text or not script_text.strip():
            raise ValidationError("script_text 不能为空")

        current_snippet = await self.config_service.get_kf_video_rules_snippet()
        trimmed_script = script_text.strip()
        if len(trimmed_script) > max_script_chars:
            trimmed_script = trimmed_script[:max_script_chars]

        updated_snippet = await self.llm_service.gemini3_service.audit_kf_video_rules_snippet(
            rules_snippet=current_snippet,
            script_text=trimmed_script,
            model=model,
        )

        # 规范化：去掉首尾空行
        updated_snippet = updated_snippet.strip("\n")
        current_snippet_norm = current_snippet.strip("\n")

        audited_at = datetime.now(timezone.utc)
        changed = updated_snippet != current_snippet_norm

        if changed:
            # 更新全局片段（写回 script_generation_prompt）
            await self.config_service.update_kf_video_rules_snippet(updated_snippet)
            await self._bump_audit_version(model=model, audited_at=audited_at)
            logger.info(
                "KF/Video rules snippet updated",
                old_len=len(current_snippet_norm),
                new_len=len(updated_snippet),
                model=model,
            )
        else:
            logger.info("KF/Video rules snippet unchanged", model=model)

        return RulesAuditResult(
            changed=changed,
            previous_snippet=current_snippet_norm,
            updated_snippet=updated_snippet,
            model=model,
            audited_at=audited_at,
        )

    async def _bump_audit_version(self, *, model: str, audited_at: datetime) -> None:
        """记录审查版本与元信息（用于可观测性）。"""
        await self.config_service.get_or_create_config(
            config_key="kf_video_rules_snippet_version",
            default_value="0",
            description="关键帧/视频规则片段版本号（自增）",
        )
        await self.config_service.get_or_create_config(
            config_key="kf_video_rules_snippet_last_audit",
            default_value="",
            description="关键帧/视频规则片段最近一次审查信息（JSON）",
        )

        # 读取当前版本并自增
        current_version_str = await self.config_service.get_config_value(
            "kf_video_rules_snippet_version",
            default="0",
        ) or "0"
        try:
            current_version = int(current_version_str)
        except ValueError:
            current_version = 0

        new_version = current_version + 1
        await self.config_service.update_config(
            "kf_video_rules_snippet_version",
            config_data=SystemConfigUpdate(
                config_value=str(new_version),
                description="关键帧/视频规则片段版本号（自增）",
            ),
        )

        audit_info = {
            "version": new_version,
            "model": model,
            "audited_at": audited_at.isoformat(),
        }
        await self.config_service.update_config(
            "kf_video_rules_snippet_last_audit",
            config_data=SystemConfigUpdate(
                config_value=json.dumps(audit_info, ensure_ascii=False),
                description="关键帧/视频规则片段最近一次审查信息（JSON）",
            ),
        )


