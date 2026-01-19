"""
Medeo API 代理服务

注意：该服务仅在后端调用，API Key 从 env/settings 读取，禁止下发给前端。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import httpx
import structlog

from src.config.settings import settings

logger = structlog.get_logger(__name__)


class MedeoServiceError(Exception):
    """Medeo 调用异常."""


class MedeoService:
    """Medeo API 调用封装."""

    def __init__(self) -> None:
        self._api_key = (settings.medeo_api_key or "").strip()
        self._base_url = (settings.medeo_base_url or "https://api.prd.medeo.app").rstrip("/")

    def _require_api_key(self) -> None:
        if not self._api_key:
            raise MedeoServiceError("缺少 MEDEO_API_KEY（请在后端 env/.env 中配置）")

    def _headers(self, *, require_auth: bool) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if require_auth:
            self._require_api_key()
            headers["X-API-KEY"] = self._api_key
        return headers

    def _client(self, *, timeout: httpx.Timeout) -> httpx.AsyncClient:
        """创建 httpx client.

        注意：强制 trust_env=False，避免本机/CI 环境的 HTTP(S)_PROXY 影响外部 HTTPS 连接，
        这会导致 TLS 握手被中断（EOF）等问题。
        """
        return httpx.AsyncClient(timeout=timeout, trust_env=False)

    async def list_recipes(self, *, limit: int = 20, order: str = "desc") -> Dict[str, Any]:
        url = f"{self._base_url}/api/v2/recipes"
        params = {"limit": limit, "order": order}
        timeout = httpx.Timeout(30.0)
        async with self._client(timeout=timeout) as client:
            resp = await client.get(url, params=params, headers=self._headers(require_auth=False))
        if resp.status_code >= 400:
            raise MedeoServiceError(f"recipes 获取失败: {resp.status_code} {resp.text}")
        return resp.json()

    async def initiate_video_creation(self, *, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self._base_url}/api/v2/create_video_jobs:initiate_video_creation"
        timeout = httpx.Timeout(60.0)
        async with self._client(timeout=timeout) as client:
            resp = await client.post(url, json=payload, headers=self._headers(require_auth=True))
        if resp.status_code >= 400:
            raise MedeoServiceError(f"initiate 失败: {resp.status_code} {resp.text}")
        return resp.json()

    async def get_last_task_status(self, *, chat_session_id: str) -> Dict[str, Any]:
        url = f"{self._base_url}/api/v2/chat_sessions/{chat_session_id}/last_task_status"
        timeout = httpx.Timeout(30.0)
        async with self._client(timeout=timeout) as client:
            resp = await client.get(url, headers=self._headers(require_auth=True))
        if resp.status_code >= 400:
            raise MedeoServiceError(f"last_task_status 失败: {resp.status_code} {resp.text}")
        return resp.json()

    async def create_render_job(self, *, video_draft_op_record_id: str) -> Dict[str, Any]:
        url = f"{self._base_url}/api/v2/render_video_jobs"
        timeout = httpx.Timeout(30.0)
        async with self._client(timeout=timeout) as client:
            resp = await client.post(
                url,
                json={"video_draft_op_record_id": video_draft_op_record_id},
                headers=self._headers(require_auth=True),
            )
        if resp.status_code >= 400:
            raise MedeoServiceError(f"render_job 创建失败: {resp.status_code} {resp.text}")
        return resp.json()

    async def query_render_job(self, *, video_draft_op_record_id: str) -> Dict[str, Any]:
        url = f"{self._base_url}/api/v2/render_video_jobs"
        params = {"video_draft_op_record_id": video_draft_op_record_id}
        timeout = httpx.Timeout(30.0)
        async with self._client(timeout=timeout) as client:
            resp = await client.get(url, params=params, headers=self._headers(require_auth=True))
        if resp.status_code >= 400:
            raise MedeoServiceError(f"render_job 查询失败: {resp.status_code} {resp.text}")
        return resp.json()

