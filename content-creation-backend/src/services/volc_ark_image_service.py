"""
火山方舟（Ark）图片生成服务（Seedream/Doubao）。

参考文档：
- 图片生成 API（Seedream 4.0-4.5 API）: https://www.volcengine.com/docs/82379/1541523?lang=zh
"""

from __future__ import annotations

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


class VolcArkImageService:
    """封装火山方舟图片生成（Seedream 4.x）调用。"""

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

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.TransportError)),
        before_sleep=before_sleep_log(logger=tenacity_logger, log_level=logging.WARNING),
    )
    async def generate_image(
        self,
        *,
        model: str,
        prompt: str,
        size: str,
        reference_image_urls: Optional[List[str]] = None,
        response_format: str = "url",
        watermark: bool = False,
    ) -> str:
        """生成图片并返回 URL。

        Args:
            model: 模型 ID（例如 doubao-seedream-4-5-251128）
            prompt: 提示词
            size: 2K/4K 或像素格式（例如 2048x2048）
            reference_image_urls: 参考图 URL 列表（最多 14 张）
            response_format: url 或 b64_json（默认 url）
            watermark: 是否添加水印（默认 False）

        Returns:
            生成图片的 URL
        """
        url = f"{self.base_url}/images/generations"
        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "sequential_image_generation": "disabled",
            "response_format": response_format,
            "size": size,
            "stream": False,
            "watermark": watermark,
        }
        if reference_image_urls:
            payload["image"] = reference_image_urls[:14]

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, headers=self._get_headers(), json=payload)

        if resp.status_code == 401:
            raise VolcArkAuthError(
                "火山方舟 401 Unauthorized：请检查 HUOSHAN_API_KEY 与模型开通状态"
            )

        resp.raise_for_status()
        data = resp.json()

        # OpenAI Images 兼容格式：data: [{url: "..."}]
        images = data.get("data")
        if isinstance(images, list) and images:
            first = images[0] or {}
            image_url = first.get("url") or first.get("data", {}).get("url")
            if image_url:
                return str(image_url)

        raise VolcArkApiError(f"火山方舟图片生成未返回 url: {data}")

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.TransportError)),
        before_sleep=before_sleep_log(logger=tenacity_logger, log_level=logging.WARNING),
    )
    async def generate_images_group(
        self,
        *,
        model: str,
        prompt: str,
        size: str,
        max_images: int,
        reference_image_urls: Optional[List[str]] = None,
        response_format: str = "url",
        watermark: bool = False,
        timeout_sec: Optional[float] = None,
    ) -> List[str]:
        """Seedream 4.5 文生组图：一次生成多张一致性更强的图片。

        说明：
        - 使用 sequential_image_generation=auto
        - 通过 sequential_image_generation_options.max_images 控制最多输出张数
        - 返回按顺序的图片 url 列表（会忽略生成失败的元素；若全部失败则抛错）
        """
        if max_images <= 0:
            raise ValueError("max_images 必须 > 0")
        max_images = max(1, min(15, int(max_images)))

        url = f"{self.base_url}/images/generations"
        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "sequential_image_generation": "auto",
            "sequential_image_generation_options": {"max_images": max_images},
            "response_format": response_format,
            "size": size,
            "stream": False,
            "watermark": watermark,
        }
        if reference_image_urls:
            payload["image"] = reference_image_urls[:14]

        # 组图通常更慢：支持外部传入超时（例如：每张图 10 分钟）
        timeout = float(timeout_sec) if timeout_sec is not None else 90.0
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=self._get_headers(), json=payload)

        if resp.status_code == 401:
            raise VolcArkAuthError(
                "火山方舟 401 Unauthorized：请检查 HUOSHAN_API_KEY 与模型开通状态"
            )

        resp.raise_for_status()
        data = resp.json()

        images = data.get("data")
        urls: List[str] = []
        if isinstance(images, list):
            for item in images:
                if not isinstance(item, dict):
                    continue
                # 成功结构
                u = item.get("url") or (item.get("data") or {}).get("url")
                if u:
                    urls.append(str(u))
                    continue
                # 失败结构：item.get("error")...
        if urls:
            return urls

        raise VolcArkApiError(f"火山方舟组图生成未返回可用 url: {data}")


volc_ark_image_service = VolcArkImageService()


