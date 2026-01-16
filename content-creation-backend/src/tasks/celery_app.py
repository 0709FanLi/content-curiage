"""Celery应用配置"""
from celery import Celery
from src.config.settings import settings

# 创建Celery应用实例
celery_app = Celery(
    "content_creation",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

# 配置
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30分钟
    task_soft_time_limit=25 * 60,  # 25分钟
)

# 自动发现任务
# celery_app.autodiscover_tasks(["src.tasks"])

