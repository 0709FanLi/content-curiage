"""
数据库连接和配置
"""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
import structlog

from src.config.settings import settings

logger = structlog.get_logger(__name__)


class Base(DeclarativeBase):
    """SQLAlchemy ORM基类"""
    pass


# 创建异步引擎
engine = create_async_engine(
    settings.database_url,
    echo=settings.database_echo,
    future=True,
)

# 创建异步会话工厂
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话的依赖注入函数"""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error("Database session error", 
                        error=str(e),
                        error_type=type(e).__name__,
                        exc_info=True)
            raise
        finally:
            await session.close()


async def create_tables() -> None:
    """创建所有数据库表"""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error("Failed to create database tables", error=str(e))
        raise


async def drop_tables() -> None:
    """删除所有数据库表（仅用于开发环境）"""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        logger.info("Database tables dropped successfully")
    except Exception as e:
        logger.error("Failed to drop database tables", error=str(e))
        raise
