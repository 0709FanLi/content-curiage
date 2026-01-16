"""
火山方舟（Ark）视频生成服务（Seedance/Doubao）。

文档：
- 创建视频生成任务 API: https://www.volcengine.com/docs/82379/1520757?lang=zh
- 查询视频生成任务 API: https://www.volcengine.com/docs/82379/1521309?lang=zh
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional

import httpx
import logging
import structlog
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config.settings import settings

logger = structlog.get_logger(__name__)
tenacity_logger = logging.getLogger(__name__)


class VolcArkAuthError(Exception):
    """火山方舟鉴权错误（通常为 API Key 无效/未开通服务）。"""


class VolcArkApiError(Exception):
    """火山方舟 API 调用错误。"""


class VolcArkVideoService:
    """封装火山方舟视频生成任务创建与查询。"""

    def __init__(self) -> None:
        self.base_url: str = str(getattr(settings, "volc_ark_base_url", "")).rstrip("/")
        self.api_key: Optional[str] = getattr(settings, "huoshan_api_key", None)

    def _get_headers(self) -> Dict[str, str]:
        if not self.api_key:
            raise VolcArkAuthError("HUOSHAN_API_KEY 未配置")
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def _build_content(
        self,
        prompt: str,
        first_frame_url: Optional[str],
        last_frame_url: Optional[str],
    ) -> List[Dict[str, Any]]:
        content: List[Dict[str, Any]] = []

        if first_frame_url:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": first_frame_url},
                    "role": "first_frame" if last_frame_url else "first_frame",
                }
            )

        if last_frame_url:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": last_frame_url},
                    "role": "last_frame",
                }
            )

        content.append({"type": "text", "text": prompt})
        return content

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.TransportError)),
        before_sleep=before_sleep_log(logger=tenacity_logger, log_level=logging.WARNING),
    )
    async def create_task(
        self,
        *,
        model: str,
        prompt: str,
        first_frame_url: Optional[str],
        last_frame_url: Optional[str],
        generate_audio: bool,
    ) -> str:
        """创建视频生成任务并返回任务 ID。"""
        url = f"{self.base_url}/contents/generations/tasks"
        payload: Dict[str, Any] = {
            "model": model,
            "content": self._build_content(prompt, first_frame_url, last_frame_url),
        }
        # 仅 Seedance 1.5 pro 支持 generate_audionew（默认 true）。
        # 需求：豆包视频默认无声，因此对 Seedance 1.5 pro 强制传 false。
        if model.startswith("doubao-seedance-1-5-pro"):
            payload["generate_audio"] = False

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, headers=self._get_headers(), json=payload)

        if resp.status_code == 401:
            raise VolcArkAuthError("火山方舟 401 Unauthorized：请检查 HUOSHAN_API_KEY 与模型开通状态")

        resp.raise_for_status()
        data = resp.json()
        task_id = data.get("id")
        if not task_id:
            raise VolcArkApiError(f"火山方舟创建任务未返回 id: {data}")
        return str(task_id)

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.TransportError)),
        before_sleep=before_sleep_log(logger=tenacity_logger, log_level=logging.WARNING),
    )
    async def get_task(self, task_id: str) -> Dict[str, Any]:
        """查询视频生成任务详情。"""
        url = f"{self.base_url}/contents/generations/tasks/{task_id}"
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(url, headers=self._get_headers())

        if resp.status_code == 401:
            raise VolcArkAuthError("火山方舟 401 Unauthorized：请检查 HUOSHAN_API_KEY 与模型开通状态")

        resp.raise_for_status()
        return resp.json()

    async def generate_video(
        self,
        *,
        model: str,
        prompt: str,
        first_frame_url: Optional[str],
        last_frame_url: Optional[str],
        generate_audio: bool = False,
        poll_interval_seconds: float = 3.0,
        timeout_seconds: float = 600.0,
    ) -> str:
        """创建任务并轮询直到成功，返回视频 URL。"""
        task_id = await self.create_task(
            model=model,
            prompt=prompt,
            first_frame_url=first_frame_url,
            last_frame_url=last_frame_url,
            generate_audio=generate_audio,
        )

        start = time.time()
        while True:
            if time.time() - start > timeout_seconds:
                raise VolcArkApiError(f"火山方舟任务超时: {task_id}")

            task = await self.get_task(task_id)
            status = str(task.get("status", ""))

            if status == "succeeded":
                content = task.get("content") or {}
                video_url = content.get("video_url")
                if not video_url:
                    raise VolcArkApiError(f"火山方舟任务成功但未返回 video_url: {task}")
                return str(video_url)

            if status in {"failed", "expired", "cancelled"}:
                raise VolcArkApiError(f"火山方舟任务失败: status={status}, task={task}")
            await asyncio.sleep(poll_interval_seconds)


volc_ark_video_service = VolcArkVideoService()


