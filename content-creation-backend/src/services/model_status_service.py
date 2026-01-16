"""
模型状态监控服务
定期检查 GRSAI 模型的可用性
"""

import asyncio
import os
from typing import Dict, Set, Optional
from datetime import datetime
import httpx
import structlog
from src.config.settings import settings

logger = structlog.get_logger(__name__)


class ModelStatusService:
    """模型状态监控服务类"""

    def __init__(self):
        # 允许通过环境变量一键关闭所有 GRSAI 模型（默认开启，保留现有功能）
        self.grsai_enabled = os.getenv("ENABLE_GRSAI_MODELS", "true").lower() == "true"
        self.grsai_key = settings.grsai_key
        self.base_url = settings.gemini_base_url or "https://grsai.dakka.com.cn"
        
        # 维护可用模型的集合（线程安全）
        self._available_models: Set[str] = set()
        self._last_check_time: Optional[datetime] = None
        self._check_interval = 300  # 5分钟 = 300秒
        self._is_running = False
        
        # GRSAI 支持的所有模型列表
        self.grsai_models = {
            # 图片生成模型
            "image": [
                "nano-banana-pro",
                "sora-image",
                "flux-1.1-pro",
                "flux-pro",
                "flux-dev",
                "flux-schnell",
                "imagen-3.0-generate-001",
                "imagen-3.0-fast-generate-001"
            ],
            # 视频生成模型
            "video": [
                "veo3.1-fast",
                "sora-2"  # 注意：是 sora-2，不是 sora2 或 sora-2-ref
            ],
            # 脚本生成模型（Chat模型）
            "script": [
                "gemini-3-pro",
                "gemini-3-flash",
                "gemini-2.0-flash-thinking-exp-01-21"
            ]
        }
        
        # 初始化时，假设所有模型都可用
        if self.grsai_enabled:
            for model_type in self.grsai_models.values():
                self._available_models.update(model_type)
        
        logger.info(
            "ModelStatusService initialized",
            base_url=self.base_url,
            check_interval=self._check_interval,
            total_models=len(self._available_models),
            grsai_enabled=self.grsai_enabled
        )

    def is_grsai_enabled(self) -> bool:
        """返回是否启用 GRSAI 模型。"""
        return self.grsai_enabled

    async def check_model_status(self, model_name: str) -> bool:
        """
        检查单个模型的状态
        
        Args:
            model_name: 模型名称
            
        Returns:
            True if model is available, False otherwise
        """
        if not self.grsai_key:
            logger.warning("GRSAI_KEY not configured, skipping model status check")
            return True  # 如果没有配置 key，默认模型可用
        
        try:
            url = f"{self.base_url}/client/common/getModelStatus"
            params = {"model": model_name}
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                
                result = response.json()
                
                # 检查返回结果
                if result.get("code") == 0:
                    data = result.get("data", {})
                    status = data.get("status", False)
                    error = data.get("error", "")
                    
                    if not status and error:
                        logger.warning(
                            "Model is unavailable",
                            model=model_name,
                            error=error
                        )
                    
                    return status
                else:
                    logger.error(
                        "Failed to check model status",
                        model=model_name,
                        code=result.get("code"),
                        msg=result.get("msg")
                    )
                    return False
                    
        except httpx.HTTPStatusError as e:
            logger.error(
                "HTTP error while checking model status",
                model=model_name,
                status_code=e.response.status_code,
                error=str(e)
            )
            return False
        except Exception as e:
            logger.error(
                "Error checking model status",
                model=model_name,
                error=str(e),
                error_type=type(e).__name__
            )
            return False

    async def check_all_models(self):
        """检查所有 GRSAI 模型的状态"""
        if not self.grsai_enabled:
            # 关闭 GRSAI 时：不做检查，并清空可用集合
            self._available_models = set()
            self._last_check_time = datetime.now()
            logger.info("GRSAI models disabled, skipping check_all_models")
            return

        if not self.grsai_key:
            logger.info("GRSAI_KEY not configured, skipping model status check")
            return
        
        logger.info("Starting model status check for all GRSAI models")
        
        # 收集所有模型
        all_models = []
        for model_type in self.grsai_models.values():
            all_models.extend(model_type)
        
        # 并发检查所有模型
        tasks = [self.check_model_status(model) for model in all_models]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 更新可用模型列表
        available_count = 0
        unavailable_models = []
        
        for model, result in zip(all_models, results):
            if isinstance(result, Exception):
                logger.error(
                    "Exception while checking model",
                    model=model,
                    error=str(result)
                )
                # 出错时保守处理，暂时移除该模型
                self._available_models.discard(model)
                unavailable_models.append(model)
            elif result:
                # 模型可用
                self._available_models.add(model)
                available_count += 1
            else:
                # 模型不可用
                self._available_models.discard(model)
                unavailable_models.append(model)
        
        self._last_check_time = datetime.now()
        
        logger.info(
            "Model status check completed",
            total_models=len(all_models),
            available=available_count,
            unavailable=len(unavailable_models),
            unavailable_models=unavailable_models,
            last_check=self._last_check_time.isoformat()
        )

    async def start_monitoring(self):
        """启动模型状态监控（后台任务）"""
        if not self.grsai_enabled:
            # 关闭 GRSAI 时：不启动监控循环
            self._available_models = set()
            self._last_check_time = datetime.now()
            logger.info("GRSAI models disabled, monitoring loop not started")
            return

        if self._is_running:
            logger.warning("Model monitoring is already running")
            return
        
        if not self.grsai_key:
            logger.info("GRSAI_KEY not configured, model monitoring disabled")
            return
        
        self._is_running = True
        logger.info("Starting model status monitoring")
        
        while self._is_running:
            try:
                await self.check_all_models()
                await asyncio.sleep(self._check_interval)
            except Exception as e:
                logger.error(
                    "Error in model monitoring loop",
                    error=str(e),
                    error_type=type(e).__name__
                )
                # 出错后等待一段时间再重试
                await asyncio.sleep(60)

    def stop_monitoring(self):
        """停止模型状态监控"""
        self._is_running = False
        logger.info("Model status monitoring stopped")

    def is_model_available(self, model_name: str) -> bool:
        """
        检查模型是否可用
        
        Args:
            model_name: 模型名称
            
        Returns:
            True if model is available, False otherwise
        """
        # 允许通过环境变量一键关闭 GRSAI 模型：关闭时，全部视为不可用
        if not self.grsai_enabled:
            return False

        # 如果没有配置 GRSAI_KEY，默认所有模型可用（保留原功能）
        if not self.grsai_key:
            return True
        
        return model_name in self._available_models

    def get_available_models(self, model_type: str) -> list[str]:
        """
        获取指定类型的可用模型列表
        
        Args:
            model_type: 模型类型 ('image', 'video', 'script')
            
        Returns:
            可用模型列表
        """
        if model_type not in self.grsai_models:
            return []
        
        # 关闭 GRSAI 时，直接返回空（全部不可用）
        if not self.grsai_enabled:
            return []

        # 如果没有配置 GRSAI_KEY，返回所有模型（保留原功能）
        if not self.grsai_key:
            return self.grsai_models[model_type]
        
        # 过滤出可用的模型
        available = [
            model for model in self.grsai_models[model_type]
            if model in self._available_models
        ]
        
        return available

    def get_status_info(self) -> Dict:
        """获取状态信息"""
        return {
            "is_monitoring": self._is_running,
            "last_check_time": self._last_check_time.isoformat() if self._last_check_time else None,
            "check_interval_seconds": self._check_interval,
            "total_models": sum(len(models) for models in self.grsai_models.values()),
            "available_models_count": len(self._available_models),
            "available_models": list(self._available_models)
        }


# 全局单例
model_status_service = ModelStatusService()

