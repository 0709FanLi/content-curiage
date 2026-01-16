"""
修复数据库表结构脚本
用于添加缺失的列
"""

import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from src.models.database import engine


async def fix_database_schema():
    """修复数据库表结构"""
    async with engine.begin() as conn:
        # 检查projects表的列
        result = await conn.execute(text('PRAGMA table_info(projects)'))
        columns = result.fetchall()
        col_names = [col[1] for col in columns]
        
        print('当前projects表的列:', col_names)
        
        # 需要添加的列
        columns_to_add = {
            'conversation_content': 'TEXT',
            'image_model': 'VARCHAR(100)',
            'aspect_ratio': 'VARCHAR(50)',
            'quality': 'VARCHAR(50)'
        }
        
        # 添加缺失的列
        for col_name, col_type in columns_to_add.items():
            if col_name not in col_names:
                print(f'添加列: {col_name} ({col_type})')
                try:
                    await conn.execute(
                        text(f'ALTER TABLE projects ADD COLUMN {col_name} {col_type}')
                    )
                    print(f'  ✓ 成功添加 {col_name}')
                except Exception as e:
                    print(f'  ✗ 添加 {col_name} 失败: {e}')
            else:
                print(f'  - {col_name} 已存在')
        
        print('\n数据库表结构修复完成')


if __name__ == '__main__':
    asyncio.run(fix_database_schema())

