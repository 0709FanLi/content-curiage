"""
应用配置管理
"""

from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import field_validator, ConfigDict
import os
from dotenv import load_dotenv

# 加载 .env 文件（如果存在）
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)


class Settings(BaseSettings):
    """应用配置类"""
    
    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra='allow'  # 允许额外字段
    )

    # 应用基本信息
    app_name: str = "Content Creation API"
    app_version: Optional[str] = "1.0.0"
    api_prefix: Optional[str] = "/api"
    debug: bool = False
    port: int = 8000

    # 数据库配置
    database_url: str = "sqlite+aiosqlite:///./content_creation.db"
    database_echo: bool = False

    # Redis配置
    redis_url: str = "redis://localhost:6379/0"

    # JWT配置
    jwt_secret_key: Optional[str] = None  # 必须通过环境变量设置
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    
    def __init__(self, **kwargs):
        """初始化配置并验证关键设置"""
        super().__init__(**kwargs)
        self._validate_security_settings()
    
    def _validate_security_settings(self):
        """验证安全相关配置"""
        # 检查是否是生产环境
        # 只有在明确设置为生产环境时才强制要求密钥
        # 检查环境变量 ENVIRONMENT 或 NODE_ENV
        environment = os.getenv("ENVIRONMENT", "").lower().strip()
        node_env = os.getenv("NODE_ENV", "").lower().strip()
        is_production = environment == "production" or node_env == "production"
        
        # 如果没有明确设置为生产环境，则认为是开发/测试环境
        # 这样更安全：默认允许使用默认密钥（带警告），只有明确的生产环境才强制要求
        
        # JWT密钥验证
        if not self.jwt_secret_key or self.jwt_secret_key in ["your-secret-key-here", ""]:
            if is_production:
                # 生产环境：强制要求
                raise ValueError(
                    "JWT_SECRET_KEY 必须通过环境变量设置！"
                    "生产环境不允许使用默认密钥。"
                    "请设置 ENVIRONMENT=production 或 NODE_ENV=production 来启用生产模式。"
                )
            else:
                # 开发/测试环境：使用默认值但给出警告
                self.jwt_secret_key = "development-secret-key-change-in-production"
                import warnings
                warnings.warn(
                    "⚠️  警告: 使用默认 JWT 密钥，仅适用于开发/测试环境！"
                    "生产环境必须设置 JWT_SECRET_KEY 环境变量，并设置 ENVIRONMENT=production。",
                    UserWarning
                )
        
        # 验证 JWT 密钥强度（至少32字符）
        if self.jwt_secret_key and len(self.jwt_secret_key) < 32:
            if is_production:
                raise ValueError(
                    f"JWT_SECRET_KEY 长度不足（当前: {len(self.jwt_secret_key)}字符），"
                    "生产环境要求至少32字符。"
                )
            else:
                import warnings
                warnings.warn(
                    f"JWT_SECRET_KEY 长度不足（当前: {len(self.jwt_secret_key)}字符），"
                    "建议使用至少32字符的强密钥。",
                    UserWarning
                )
        
        # 验证 MinIO 配置
        self._validate_minio_settings(is_production)
        
        # 验证数据库配置（如果是 PostgreSQL）
        self._validate_database_settings(is_production)
    
    def _validate_minio_settings(self, is_production: bool):
        """验证 MinIO 配置"""
        # 如果未设置，在非生产环境使用默认值
        if not self.minio_access_key:
            if is_production:
                raise ValueError(
                    "MINIO_ACCESS_KEY 必须通过环境变量设置！"
                    "生产环境不允许使用默认密钥。"
                )
            else:
                self.minio_access_key = "minioadmin"
                import warnings
                warnings.warn(
                    "⚠️  警告: 使用 MinIO 默认密钥，仅适用于开发/测试环境！"
                    "生产环境必须设置 MINIO_ACCESS_KEY 和 MINIO_SECRET_KEY 环境变量。",
                    UserWarning
                )
        
        if not self.minio_secret_key:
            if is_production:
                raise ValueError(
                    "MINIO_SECRET_KEY 必须通过环境变量设置！"
                    "生产环境不允许使用默认密钥。"
                )
            else:
                self.minio_secret_key = "minioadmin"
    
    def _validate_database_settings(self, is_production: bool):
        """验证数据库配置"""
        # 如果是 PostgreSQL，检查密码
        if self.database_url.startswith("postgresql"):
            # 从 URL 中提取密码
            if "password" in self.database_url.lower():
                # 检查是否是默认密码
                if ":password@" in self.database_url or ":password@" in self.database_url.replace("//", ""):
                    if is_production:
                        raise ValueError(
                            "数据库密码不能使用默认值 'password'！"
                            "生产环境必须设置强密码。"
                        )
                    else:
                        import warnings
                        warnings.warn(
                            "⚠️  警告: 数据库使用默认密码，仅适用于开发/测试环境！"
                            "生产环境必须设置强密码。",
                            UserWarning
                        )

    # 文件存储配置
    minio_endpoint: str = "localhost:9000"
    minio_access_key: Optional[str] = None  # 生产环境必须设置
    minio_secret_key: Optional[str] = None  # 生产环境必须设置
    minio_bucket_name: str = "content-creation"
    minio_secure: bool = False

    # AI模型API配置
    openai_api_key: Optional[str] = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_timeout: int = 60

    stability_api_key: Optional[str] = None
    stability_base_url: str = "https://api.stability.ai"
    stability_timeout: int = 60

    # 任务队列配置
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"

    # CORS配置
    allowed_hosts_str: str = "localhost,127.0.0.1,47.83.9.28,*"
    allowed_hosts: List[str] = ["localhost", "127.0.0.1", "47.83.9.28", "*"]
    cors_origins: Optional[str] = None  # JSON字符串格式的CORS源列表
    
    # 阿里云相关配置
    dashscope_api_key: Optional[str] = None
    qwen_base_url: Optional[str] = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    wanx_base_url: Optional[str] = None
    
    # DeepSeek配置
    deep_seek: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    deepseek_base_url: str = "https://api.deepseek.com"
    request_timeout: int = 60
    
    # Gemini 3配置
    gemini_api_key: Optional[str] = None
    gemini_base_url: str = "https://grsai.dakka.com.cn"  # 使用自定义代理地址
    gemini_timeout: int = 300  # 增加超时时间到5分钟，适应高思考模型
    
    # 图片生成API配置
    image_generation_api_key: Optional[str] = None
    grsai_key: Optional[str] = None  # GRSAI API密钥
    image_generation_base_url: str = "https://grsai.dakka.com.cn"  # 国内直连
    image_generation_timeout: int = 600  # 图片生成可能需要较长时间(10分钟)

    # 火山方舟（Ark）视频生成配置（Seedance/Doubao）
    huoshan_api_key: Optional[str] = None
    volc_ark_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"

    # Coze API配置
    coze_api_key: Optional[str] = None  # 从 .env 的 COZE_API_KEY 读取
    coze_agent_id: Optional[str] = None  # 从 .env 的 COZE_AGENT_ID 读取（工作流ID）
    coze_bot_id: Optional[str] = None  # 从 .env 的 COZE_BOT_ID 读取（Chat Bot ID）
    coze_base_url: str = "https://api.coze.cn"
    coze_workflow_id: str = "7584363314751782964"  # 热点工作流ID
    coze_timeout: int = 60
    coze_poll_interval: int = 2  # 轮询间隔(秒)
    coze_max_poll_time: int = 300  # 最大轮询时间(秒)

    # 文件上传配置
    max_upload_size: int = 10 * 1024 * 1024  # 10MB
    allowed_image_types: List[str] = [".jpg", ".jpeg", ".png", ".gif"]
    allowed_video_types: List[str] = [".mp4", ".avi", ".mov", ".wmv"]

    # 业务配置
    max_script_length: int = 1000
    min_video_duration: int = 60
    max_video_duration: int = 1200  # 20分钟
    enable_jimeng_video: bool = True  # 启用即梦视频生成

    @field_validator("database_url", mode="before")
    @classmethod
    def assemble_database_url(cls, v) -> str:
        """组装数据库URL"""
        if isinstance(v, str):
            return v

        # 如果没有提供完整的URL，从环境变量组装
        db_user = os.getenv("DB_USER", "user")
        db_password = os.getenv("DB_PASSWORD")
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "5432")
        db_name = os.getenv("DB_NAME", "content_creation")
        
        # 开发环境允许默认密码，生产环境必须设置
        if not db_password:
            debug_mode = os.getenv("DEBUG", "false").lower() == "true"
            if debug_mode:
                db_password = "password"  # 开发环境默认值
                import warnings
                warnings.warn(
                    "⚠️  警告: 使用默认数据库密码，仅适用于开发环境！"
                    "生产环境必须设置 DB_PASSWORD 环境变量。",
                    UserWarning
                )
            else:
                raise ValueError(
                    "DB_PASSWORD 必须通过环境变量设置！"
                    "生产环境不允许使用默认密码。"
                )

        return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

    @field_validator("redis_url", mode="before")
    @classmethod
    def assemble_redis_url(cls, v) -> str:
        """组装Redis URL"""
        if isinstance(v, str):
            return v

        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = os.getenv("REDIS_PORT", "6379")
        redis_db = os.getenv("REDIS_DB", "0")

        return f"redis://{redis_host}:{redis_port}/{redis_db}"

    @field_validator("allowed_hosts", mode="before")
    @classmethod
    def parse_allowed_hosts(cls, v, info) -> List[str]:
        """解析允许的主机列表"""
        allowed_hosts_str = info.data.get('allowed_hosts_str', 'localhost,127.0.0.1')
        return [host.strip() for host in allowed_hosts_str.split(",")]


# 创建全局配置实例
settings = Settings()
