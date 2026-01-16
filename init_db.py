#!/usr/bin/env python3
"""
生产环境数据库初始化脚本
直接使用SQLAlchemy创建所有表
"""
import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, '/opt/content-creation-prod/content-creation-backend')

async def init_database():
    """初始化数据库表"""
    try:
        # 设置环境变量
        os.environ['DATABASE_URL'] = 'postgresql+asyncpg://postgres:uX7vK9mP2wQ5nR8tL4jH6sF3dG1aZ0bY@localhost:5432/content_creation'
        os.environ['DEBUG'] = 'false'
        os.environ['JWT_SECRET_KEY'] = 'prod-secret-key-change-me'
        os.environ['JWT_ALGORITHM'] = 'HS256'
        os.environ['ACCESS_TOKEN_EXPIRE_MINUTES'] = '30'
        
        # 导入模型
        from src.models.database import Base, engine
        from src.models.tables.user import User
        from src.models.tables.project import Project
        from src.models.tables.script import Script
        from src.models.tables.keyframe import Keyframe
        from src.models.tables.video_segment import VideoSegment
        from src.models.tables.file import File
        
        # 创建所有表
        async with engine.begin() as conn:
            print("正在创建数据库表...")
            await conn.run_sync(Base.metadata.create_all)
            print("✓ 数据库表创建完成!")
            
        # 验证表是否创建成功
        from sqlalchemy import text
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'"))
            tables = [row[0] for row in result]
            print(f"\n已创建的表: {', '.join(tables)}")
            
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    print("=== 初始化生产环境数据库 ===\n")
    asyncio.run(init_database())

