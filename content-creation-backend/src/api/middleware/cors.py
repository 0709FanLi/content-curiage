"""
CORS中间件配置
"""

from fastapi.middleware.cors import CORSMiddleware

# CORS配置
cors_middleware = CORSMiddleware(
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # 前端开发服务器地址
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
