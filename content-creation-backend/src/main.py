"""
内容创作应用主入口
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import structlog
from dotenv import load_dotenv
import os

# 加载.env文件
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(env_path)

from src.api.routers import auth, projects, scripts, keyframes, videos, files, models, system_config, hotspots, timelines, tts
from src.config.settings import settings
from src.models.database import create_tables, get_db
from src.utils.logging import setup_logging
from src.utils.exceptions import ApiError, setup_exception_handlers
from src.services.model_status_service import model_status_service
from src.services.coze_service import get_coze_service
from src.services.hotspot_cache_service import HotspotCacheService


# 设置日志
setup_logging()

logger = structlog.get_logger(__name__)


async def init_default_user():
    """初始化默认测试用户（仅在开发环境）"""
    # 仅在开发环境创建测试用户
    if not settings.debug:
        return
    
    # 检查是否允许创建测试用户（通过环境变量控制）
    create_test_user = os.getenv("CREATE_TEST_USER", "false").lower() == "true"
    if not create_test_user:
        logger.info("跳过测试用户创建（设置 CREATE_TEST_USER=true 以启用）")
        return
    
    from src.models.database import async_session_maker
    from src.services.auth_service import AuthService
    from src.models.schemas import UserCreate
    
    # 从环境变量获取测试用户信息，如果没有则使用默认值
    test_username = os.getenv("TEST_USERNAME", "testuser")
    test_email = os.getenv("TEST_EMAIL", "test@example.com")
    test_password = os.getenv("TEST_PASSWORD")
    
    if not test_password:
        logger.warning("未设置 TEST_PASSWORD 环境变量，跳过测试用户创建")
        return
    
    async with async_session_maker() as db:
        auth_service = AuthService(db)
        
        # 检查用户是否已存在
        existing_user = await auth_service.get_user_by_username(test_username)
        if existing_user:
            logger.info("测试用户已存在", username=test_username)
            return
        
        # 创建测试用户
        try:
            user_data = UserCreate(
                username=test_username,
                email=test_email,
                password=test_password
            )
            user = await auth_service.create_user(user_data)
            logger.info("测试用户创建成功", username=user.username, user_id=user.id)
        except ValueError as e:
            logger.warning("测试用户创建失败（可能已存在）", error=str(e))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("Starting Content Creation API")

    # 创建数据库表
    await create_tables()
    
    # 初始化默认用户
    await init_default_user()
    
    # 启动模型状态监控（后台任务）
    import asyncio
    monitoring_task = asyncio.create_task(model_status_service.start_monitoring())
    logger.info("Model status monitoring task created")

    # 启动热点缓存刷新任务（每2小时）
    hotspot_cache_task = None
    try:
        from src.models.database import async_session_maker

        async def hotspot_cache_loop() -> None:
            """每2小时拉取热点列表并写入数据库缓存。"""
            while True:
                try:
                    async with async_session_maker() as db:
                        cache_service = HotspotCacheService(db)
                        hotspot_list = await get_coze_service().get_hotspots()
                        await cache_service.save_snapshot(hotspot_list)
                        logger.info(
                            "Hotspot cache refreshed",
                            hotspot_count=len(hotspot_list.hotspots),
                        )
                except ValueError as e:
                    # 未配置 Coze 时不报错，等待下一轮
                    logger.warning("Hotspot cache refresh skipped (config)", error=str(e))
                except Exception as e:
                    logger.error(
                        "Hotspot cache refresh failed",
                        error=str(e),
                        error_type=type(e).__name__,
                    )

                await asyncio.sleep(2 * 60 * 60)  # 2小时

        hotspot_cache_task = asyncio.create_task(hotspot_cache_loop())
        logger.info("Hotspot cache task created")
    except Exception as e:
        logger.warning(
            "Failed to start hotspot cache task",
            error=str(e),
            error_type=type(e).__name__,
        )

    # 日间规则审查任务（9/12/15/18 点）：用于迭代更新“关键帧/视频规则片段”
    rules_audit_task = None
    try:
        from src.services.daytime_rules_audit_scheduler import start_daytime_rules_audit_loop

        rules_audit_task = asyncio.create_task(start_daytime_rules_audit_loop())
        logger.info("Daytime rules audit task created")
    except Exception as e:
        logger.warning(
            "Failed to start daytime rules audit task",
            error=str(e),
            error_type=type(e).__name__,
        )

    yield

    # 停止模型状态监控
    model_status_service.stop_monitoring()
    monitoring_task.cancel()
    try:
        await monitoring_task
    except asyncio.CancelledError:
        logger.info("Model monitoring task cancelled")

    # 停止热点缓存任务
    if hotspot_cache_task:
        hotspot_cache_task.cancel()
        try:
            await hotspot_cache_task
        except asyncio.CancelledError:
            logger.info("Hotspot cache task cancelled")

    # 停止日间规则审查任务
    if rules_audit_task:
        rules_audit_task.cancel()
        try:
            await rules_audit_task
        except asyncio.CancelledError:
            logger.info("Daytime rules audit task cancelled")
    
    logger.info("Shutting down Content Creation API")


def create_application() -> FastAPI:
    """创建FastAPI应用实例"""

    app = FastAPI(
        title=settings.app_name,
        description="内容创作平台API",
        version="1.0.0",
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # 设置异常处理器
    setup_exception_handlers(app)

    # 中间件配置
    # CORS 配置：允许前端源(包括协议和端口)
    cors_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",  # Vite 默认端口
        "http://127.0.0.1:5173",
        "http://47.83.9.28:8001",  # 生产环境前端(IP)
        "http://www.content.curiage.com",  # 生产环境前端(域名)
        "http://content.curiage.com",  # 生产环境前端(域名-无www)
        "https://www.content.curiage.com",  # HTTPS支持
        "https://content.curiage.com",  # HTTPS支持
        "*",  # 允许所有源(生产环境应改为具体域名)
    ]
    # 如果配置中有自定义的 CORS 源，则使用配置的
    if settings.cors_origins:
        import json
        try:
            custom_origins = json.loads(settings.cors_origins)
            if isinstance(custom_origins, list):
                cors_origins.extend(custom_origins)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Invalid CORS origins format, using defaults")
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # TrustedHostMiddleware在生产环境会阻止外部访问,暂时禁用
    # 生产环境应配置Nginx等反向代理来处理主机验证
    # app.add_middleware(
    #     TrustedHostMiddleware,
    #     allowed_hosts=settings.allowed_hosts,
    # )

    # 路由注册
    app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
    app.include_router(projects.router, prefix="/api/projects", tags=["项目管理"])
    app.include_router(scripts.router, prefix="/api/scripts", tags=["脚本管理"])
    app.include_router(keyframes.router, prefix="/api/keyframes", tags=["关键帧管理"])
    app.include_router(videos.router, prefix="/api/videos", tags=["视频管理"])
    app.include_router(files.router, prefix="/api/files", tags=["文件管理"])
    app.include_router(models.router, prefix="/api/models", tags=["模型管理"])
    app.include_router(system_config.router, prefix="/api", tags=["系统配置"])
    app.include_router(hotspots.router, prefix="/api/hotspots", tags=["热点情报"])
    app.include_router(timelines.router, prefix="/api/timelines", tags=["时间线管理"])
    app.include_router(tts.router, prefix="/api/tts", tags=["TTS语音合成"])

    # 健康检查
    @app.get("/health", tags=["健康检查"])
    async def health_check():
        return {"status": "healthy", "version": "1.0.0"}

    # 请求日志中间件
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        logger.info(
            "Request started",
            method=request.method,
            url=str(request.url),
            client=request.client.host if request.client else None,
        )

        response = await call_next(request)

        logger.info(
            "Request completed",
            method=request.method,
            url=str(request.url),
            status_code=response.status_code,
        )

        return response

    return app


# 创建应用实例
app = create_application()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.debug,
        log_config=None,  # 使用我们的日志配置
    )
