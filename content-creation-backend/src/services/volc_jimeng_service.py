"""
火山引擎即梦图片生成服务
封装调用火山引擎即梦4.0 API的逻辑
"""

import asyncio
import hashlib
import hmac
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx
import structlog

logger = structlog.get_logger(__name__)


class VolcJiMengService:
    """火山引擎即梦服务类."""

    SERVICE_NAME = "cv"
    API_VERSION = "2022-08-31"

    def __init__(self) -> None:
        """初始化火山引擎服务."""
        # 支持多种环境变量名称，兼容 ENV_TEMPLATE.txt 中的配置
        self.access_key_id = (
            os.getenv("VOLC_ACCESS_KEY_ID") or 
            os.getenv("VOLC_ACCESS_KEY") or 
            ""
        )
        self.secret_access_key = (
            os.getenv("VOLC_SECRET_ACCESS_KEY") or 
            os.getenv("VOLC_SECRET_KEY") or 
            ""
        )
        self.base_url = os.getenv("VOLC_BASE_URL", "https://visual.volcengineapi.com")
        self.timeout = 600  # 10分钟超时

        if not self.access_key_id or not self.secret_access_key:
            logger.warning('Volc JiMeng API key not configured')

    def _generate_signature(
        self,
        method: str,
        uri: str,
        query_params: Dict[str, str],
        headers: Dict[str, str],
        body: str,
        timestamp: str
    ) -> str:
        """生成火山引擎API签名（HMAC-SHA256）.
        
        Args:
            method: HTTP方法
            uri: URI路径
            query_params: 查询参数
            headers: 请求头
            body: 请求体
            timestamp: 时间戳
            
        Returns:
            签名字符串
        """
        # 1. 构建CanonicalRequest
        canonical_headers = "\n".join([
            f"{k.lower()}:{v}" for k, v in sorted(headers.items())
        ])
        signed_headers = ";".join([k.lower() for k in sorted(headers.keys())])

        canonical_query = "&".join([
            f"{quote(k, safe='')}={quote(str(v), safe='')}"
            for k, v in sorted(query_params.items())
        ])

        hashed_payload = hashlib.sha256(body.encode('utf-8')).hexdigest()

        canonical_request = "\n".join([
            method,
            uri,
            canonical_query,
            canonical_headers,
            "",
            signed_headers,
            hashed_payload
        ])

        # 2. 构建StringToSign
        hashed_canonical_request = hashlib.sha256(
            canonical_request.encode('utf-8')
        ).hexdigest()

        credential_scope = f"{timestamp[:8]}/cn-north-1/{self.SERVICE_NAME}/request"

        string_to_sign = "\n".join([
            "HMAC-SHA256",
            timestamp,
            credential_scope,
            hashed_canonical_request
        ])

        # 3. 计算签名
        k_date = hmac.new(
            self.secret_access_key.encode('utf-8'),
            timestamp[:8].encode('utf-8'),
            hashlib.sha256
        ).digest()

        k_region = hmac.new(
            k_date,
            "cn-north-1".encode('utf-8'),
            hashlib.sha256
        ).digest()

        k_service = hmac.new(
            k_region,
            self.SERVICE_NAME.encode('utf-8'),
            hashlib.sha256
        ).digest()

        k_signing = hmac.new(
            k_service,
            "request".encode('utf-8'),
            hashlib.sha256
        ).digest()

        signature = hmac.new(
            k_signing,
            string_to_sign.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return signature

    def _build_auth_headers(
        self,
        method: str,
        uri: str,
        query_params: Dict[str, str],
        body: str
    ) -> Dict[str, str]:
        """构建认证请求头.
        
        Args:
            method: HTTP方法
            uri: URI路径
            query_params: 查询参数
            body: 请求体
            
        Returns:
            认证请求头字典
        """
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        payload_hash = hashlib.sha256(body.encode('utf-8')).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "Host": "visual.volcengineapi.com",
            "X-Date": timestamp,
            "X-Content-Sha256": payload_hash
        }

        signature = self._generate_signature(
            method, uri, query_params, headers, body, timestamp
        )

        credential_scope = f"{timestamp[:8]}/cn-north-1/{self.SERVICE_NAME}/request"
        signed_headers = "content-type;host;x-content-sha256;x-date"

        authorization = (
            f"HMAC-SHA256 "
            f"Credential={self.access_key_id}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, "
            f"Signature={signature}"
        )

        headers["Authorization"] = authorization

        return headers

    async def generate_image(
        self,
        prompt: str,
        size: str = "1024x1024",
        reference_image_urls: Optional[List[str]] = None
    ) -> str:
        """生成图片（即梦4.0，支持图生图）.

        Args:
            prompt: 提示词（最长800字符）
            size: 图片尺寸（格式：宽度x高度，如1024x1024）
            reference_image_urls: 参考图URL列表（可选，支持0-6张）

        Returns:
            生成的图片URL

        Raises:
            Exception: API调用失败
        """
        if not self.access_key_id or not self.secret_access_key:
            raise Exception('火山引擎API密钥未配置')

        # 构建请求（异步任务提交）
        uri = "/"
        query_params = {
            "Action": "CVSync2AsyncSubmitTask",
            "Version": self.API_VERSION
        }

        body_dict = {
            "req_key": "jimeng_t2i_v40",
            "prompt": prompt,
            "force_single": True,  # 强制单图输出
        }

        # 添加参考图（如果提供）
        if reference_image_urls and len(reference_image_urls) > 0:
            # 限制最多6张
            body_dict["image_urls"] = reference_image_urls[:6]
            logger.info(
                'Using reference images for JiMeng generation',
                count=len(reference_image_urls[:6])
            )

        # 解析尺寸
        if "x" in size:
            width, height = size.split("x")
            body_dict["width"] = int(width)
            body_dict["height"] = int(height)

        body = json.dumps(body_dict)

        # 构建认证头
        headers = self._build_auth_headers("POST", uri, query_params, body)

        # 发送请求（异步任务模式）
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            url = f"{self.base_url}{uri}"

            # 步骤1：提交任务
            response = await client.post(
                url,
                params=query_params,
                headers=headers,
                content=body
            )

            response.raise_for_status()
            result = response.json()

            # 检查提交状态
            if result.get("code") != 10000:
                error_msg = result.get("message", "未知错误")
                raise Exception(f"火山即梦提交任务失败: {error_msg}")

            # 获取task_id
            task_id = result.get("data", {}).get("task_id")
            if not task_id:
                raise Exception("火山即梦未返回task_id")

            logger.info(
                'JiMeng task submitted',
                task_id=task_id
            )

            # 步骤2：轮询查询结果
            query_params = {
                "Action": "CVSync2AsyncGetResult",
                "Version": self.API_VERSION
            }

            query_body_dict = {
                "req_key": "jimeng_t2i_v40",
                "task_id": task_id,
                "req_json": json.dumps({"return_url": True})
            }

            query_body = json.dumps(query_body_dict)
            query_headers = self._build_auth_headers("POST", uri, query_params, query_body)

            # 轮询查询（最多300次，每次等待2秒=600秒）
            max_retries = 300
            for i in range(max_retries):
                await asyncio.sleep(2)  # 等待2秒

                query_response = await client.post(
                    url,
                    params=query_params,
                    headers=query_headers,
                    content=query_body
                )

                query_response.raise_for_status()
                query_result = query_response.json()

                status = query_result.get("data", {}).get("status")

                if status == "done":
                    # 任务完成
                    if query_result.get("code") != 10000:
                        error_msg = query_result.get("message", "未知错误")
                        raise Exception(f"火山即梦生成失败: {error_msg}")

                    # 提取图片URL
                    image_urls = query_result.get("data", {}).get("image_urls", [])

                    if not image_urls:
                        raise Exception("火山即梦未返回图片")

                    logger.info(
                        'JiMeng image generated successfully',
                        task_id=task_id,
                        image_url=image_urls[0]
                    )

                    return image_urls[0]

                elif status in ["in_queue", "generating"]:
                    # 任务处理中，继续等待
                    logger.debug(
                        'JiMeng task in progress',
                        task_id=task_id,
                        status=status,
                        retry=i + 1
                    )
                    continue

                elif status == "not_found":
                    raise Exception("火山即梦任务未找到")

                elif status == "expired":
                    raise Exception("火山即梦任务已过期")

                else:
                    raise Exception(f"火山即梦任务状态未知: {status}")

            # 超时
            raise Exception(f"火山即梦任务超时，轮询{max_retries}次后任务仍未完成")

    async def generate_video(
        self,
        prompt: str,
        first_frame_url: str,
        last_frame_url: Optional[str] = None,
        duration: float = 5.0,
        model: str = "jimeng_i2v_first_v30_1080"
    ) -> str:
        """使用即梦 i2v 首帧模型生成视频（1080P）.

        Args:
            prompt: 视频描述提示词（建议400字以内）
            first_frame_url: 首帧图片URL（必须公网可访问）
            last_frame_url: 兼容参数：旧首尾帧模式尾帧URL（当前首帧接口会忽略）
            duration: 视频时长（5或10秒）
            model: 模型名称（req_key）

        Returns:
            生成的视频URL

        Raises:
            Exception: API调用失败
        """
        if not self.access_key_id or not self.secret_access_key:
            raise Exception('火山引擎API密钥未配置')

        # 步骤1：提交视频生成任务
        uri = "/"
        query_params = {
            "Action": "CVSync2AsyncSubmitTask",
            "Version": self.API_VERSION
        }
        
        # 根据时长确定帧数（5秒=121帧，10秒=241帧，25fps）
        frames = 121 if duration <= 5 else 241

        # 确定 req_key
        allowed_req_keys = {"jimeng_i2v_first_v30_1080", "jimeng_ti2v_v30_pro"}
        req_key = model if model in allowed_req_keys else "jimeng_i2v_first_v30_1080"

        body_dict = {
            "req_key": req_key,
            "prompt": prompt[:400],  # 限制400字
            # 首帧模式：仅需 1 张图片
            "image_urls": [first_frame_url],
            "frames": frames,
            "seed": -1  # 随机种子
        }

        body = json.dumps(body_dict)
        headers = self._build_auth_headers("POST", uri, query_params, body)

        url = f"{self.base_url}{uri}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # 提交任务
            response = await client.post(
                url,
                params=query_params,
                headers=headers,
                content=body
            )

            response.raise_for_status()
            result = response.json()

            if result.get("code") != 10000:
                error_msg = result.get("message", "未知错误")
                raise Exception(f"火山即梦视频提交失败: {error_msg}")

            # 获取task_id
            task_id = result.get("data", {}).get("task_id")
            if not task_id:
                raise Exception("火山即梦未返回task_id")

            logger.info(
                'JiMeng video task submitted',
                task_id=task_id,
                frames=frames,
                duration=duration
            )

            # 步骤2：轮询查询结果
            query_params = {
                "Action": "CVSync2AsyncGetResult",
                "Version": self.API_VERSION
            }

            query_body_dict = {
                "req_key": req_key,
                "task_id": task_id,
                "req_json": json.dumps({"return_url": True})
            }

            query_body = json.dumps(query_body_dict)
            query_headers = self._build_auth_headers("POST", uri, query_params, query_body)

            # 轮询查询（视频生成时间较长，最多120次，每次等待5秒=600秒）
            max_retries = 120
            for i in range(max_retries):
                await asyncio.sleep(5)  # 等待5秒

                query_response = await client.post(
                    url,
                    params=query_params,
                    headers=query_headers,
                    content=query_body
                )

                query_response.raise_for_status()
                query_result = query_response.json()

                status = query_result.get("data", {}).get("status")

                if status == "done":
                    # 任务完成
                    if query_result.get("code") != 10000:
                        error_msg = query_result.get("message", "未知错误")
                        raise Exception(f"火山即梦视频生成失败: {error_msg}")

                    # 提取视频URL
                    video_url = query_result.get("data", {}).get("video_url")

                    if not video_url:
                        raise Exception("火山即梦未返回视频URL")

                    logger.info(
                        'JiMeng video generated successfully',
                        task_id=task_id,
                        video_url=video_url
                    )

                    return video_url

                elif status in ["in_queue", "generating"]:
                    # 任务处理中，继续等待
                    logger.debug(
                        'JiMeng video task in progress',
                        task_id=task_id,
                        status=status,
                        retry=i + 1
                    )
                    continue

                elif status == "not_found":
                    raise Exception("火山即梦视频任务未找到")

                elif status == "expired":
                    raise Exception("火山即梦视频任务已过期")

                else:
                    raise Exception(f"火山即梦视频任务状态未知: {status}")

            # 超时
            raise Exception(f"火山即梦视频任务超时，轮询{max_retries}次后任务仍未完成")


# 创建全局即梦服务实例
volc_jimeng_service = VolcJiMengService()

