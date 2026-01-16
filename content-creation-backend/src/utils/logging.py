"""
日志配置
"""

import sys
import structlog
from structlog.dev import ConsoleRenderer
from structlog.processors import JSONRenderer

from src.config.settings import settings


def setup_logging() -> None:
    """设置结构化日志"""
    shared_processors = [
        structlog.stdlib.filter_by_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if settings.debug:
        # 开发环境：彩色控制台输出
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        # 生产环境：JSON格式输出
        processors = shared_processors + [
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """获取日志器"""
    return structlog.get_logger(name)
