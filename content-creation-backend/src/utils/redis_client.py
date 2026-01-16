"""
Redis客户端工具类
用于任务取消、缓存等功能
"""
try:
    import redis.asyncio as aioredis
except ImportError:
    # Redis 5.0.x 使用不同的导入路径
    from redis import asyncio as aioredis
from typing import Optional
import structlog
import os

logger = structlog.get_logger(__name__)


class RedisClient:
    """Redis异步客户端单例"""
    
    _instance: Optional[aioredis.Redis] = None
    
    @classmethod
    async def get_instance(cls) -> aioredis.Redis:
        """获取Redis客户端实例（单例模式）"""
        if cls._instance is None:
            redis_host = os.getenv("REDIS_HOST", "localhost")
            redis_port = int(os.getenv("REDIS_PORT", "6379"))
            redis_db = int(os.getenv("REDIS_DB", "0"))
            
            cls._instance = await aioredis.from_url(
                f"redis://{redis_host}:{redis_port}/{redis_db}",
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            
            logger.info(
                "Redis client initialized",
                host=redis_host,
                port=redis_port,
                db=redis_db
            )
        
        return cls._instance
    
    @classmethod
    async def close(cls):
        """关闭Redis连接"""
        if cls._instance:
            await cls._instance.close()
            cls._instance = None
            logger.info("Redis client closed")


class TaskCancellationManager:
    """任务取消管理器"""
    
    CANCEL_KEY_PREFIX = "task:cancel:script:"
    CANCEL_TTL = 3600  # 1小时过期
    
    @classmethod
    async def set_cancellation_flag(cls, script_id: int) -> None:
        """设置任务取消标志
        
        Args:
            script_id: 脚本ID
        """
        try:
            redis = await RedisClient.get_instance()
            key = f"{cls.CANCEL_KEY_PREFIX}{script_id}"
            
            await redis.set(key, "1", ex=cls.CANCEL_TTL)
            
            logger.info(
                "Task cancellation flag set",
                script_id=script_id,
                key=key,
                ttl=cls.CANCEL_TTL
            )
        except Exception as e:
            logger.error(
                "Failed to set cancellation flag in Redis",
                script_id=script_id,
                error=str(e),
                exc_info=True
            )
            # 不抛出异常，让数据库状态更新继续执行
    
    @classmethod
    async def check_cancellation_flag(cls, script_id: int) -> bool:
        """检查任务是否被取消
        
        Args:
            script_id: 脚本ID
            
        Returns:
            True表示已取消，False表示未取消
        """
        try:
            redis = await RedisClient.get_instance()
            key = f"{cls.CANCEL_KEY_PREFIX}{script_id}"
            
            result = await redis.get(key)
            is_cancelled = result == "1"
            
            if is_cancelled:
                logger.info(
                    "Task cancellation detected",
                    script_id=script_id,
                    key=key
                )
            
            return is_cancelled
        except Exception as e:
            logger.warning(
                "Failed to check cancellation flag from Redis, assuming not cancelled",
                script_id=script_id,
                error=str(e)
            )
            return False  # Redis失败时，假设未取消，避免阻塞正常流程
    
    @classmethod
    async def clear_cancellation_flag(cls, script_id: int) -> None:
        """清除任务取消标志（任务完成或重新开始时调用）
        
        Args:
            script_id: 脚本ID
        """
        try:
            redis = await RedisClient.get_instance()
            key = f"{cls.CANCEL_KEY_PREFIX}{script_id}"
            
            await redis.delete(key)
            
            logger.info(
                "Task cancellation flag cleared",
                script_id=script_id,
                key=key
            )
        except Exception as e:
            logger.warning(
                "Failed to clear cancellation flag from Redis",
                script_id=script_id,
                error=str(e)
            )
            # 不抛出异常，继续执行
    
    @classmethod
    async def set_task_heartbeat(cls, script_id: int, task_type: str) -> None:
        """设置任务心跳（用于检测任务是否还在运行）
        
        Args:
            script_id: 脚本ID
            task_type: 任务类型（keyframe/video）
        """
        try:
            redis = await RedisClient.get_instance()
            key = f"task:heartbeat:script:{script_id}:{task_type}"
            
            # 心跳有效期5分钟，如果任务正常运行会持续更新
            await redis.set(key, "1", ex=300)
        except Exception as e:
            logger.warning(
                "Failed to set task heartbeat",
                script_id=script_id,
                task_type=task_type,
                error=str(e)
            )
            # 不抛出异常，继续执行
    
    @classmethod
    async def check_task_alive(cls, script_id: int, task_type: str) -> bool:
        """检查任务是否还在运行
        
        Args:
            script_id: 脚本ID
            task_type: 任务类型（keyframe/video）
            
        Returns:
            True表示任务还在运行，False表示任务可能已停止
        """
        redis = await RedisClient.get_instance()
        key = f"task:heartbeat:script:{script_id}:{task_type}"
        
        result = await redis.get(key)
        return result == "1"
