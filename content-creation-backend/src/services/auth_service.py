"""
认证服务
"""

import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from src.models.tables import User
from src.models.schemas import UserCreate
from src.utils.security import verify_password, get_password_hash


class AuthService:
    """认证服务类"""

    def __init__(self, db: AsyncSession):
        self.db = db

    def validate_password_strength(self, password: str) -> bool:
        """
        验证密码强度：至少6位，包含数字和英文
        """
        if len(password) < 6:
            return False

        # 检查是否包含字母
        has_letter = bool(re.search(r'[a-zA-Z]', password))
        # 检查是否包含数字
        has_digit = bool(re.search(r'\d', password))

        return has_letter and has_digit

    def validate_username(self, username: str) -> bool:
        """
        验证用户名：3-50位，只能包含字母、数字、下划线
        """
        if len(username) < 3 or len(username) > 50:
            return False

        return bool(re.match(r'^[a-zA-Z0-9_]+$', username))

    async def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """验证用户凭据"""
        import structlog
        logger = structlog.get_logger(__name__)
        
        # 查询用户
        logger.info("开始查询用户", username=username, username_type=type(username).__name__)
        
        stmt = select(User).where(
            (User.username == username) | (User.email == username)
        )
        
        # 打印SQL语句用于调试
        logger.debug("SQL查询", sql=str(stmt))
        
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        
        logger.info("查询结果", 
                   username=username,
                   user_found=user is not None,
                   user_id=user.id if user else None,
                   user_username=user.username if user else None)

        if not user:
            logger.warning("用户不存在", username=username)
            return None

        # 验证密码
        password_valid = verify_password(password, user.hashed_password)
        logger.info("密码验证", 
                   username=username,
                   password_length=len(password),
                   hashed_password_length=len(user.hashed_password) if user.hashed_password else 0,
                   password_valid=password_valid)
        
        if not password_valid:
            logger.warning("密码验证失败", username=username)
            return None

        return user

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """根据用户名获取用户"""
        stmt = select(User).where(User.username == username)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """根据邮箱获取用户"""
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """根据ID获取用户"""
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_user(self, user_data: UserCreate) -> User:
        """创建新用户"""
        # 验证用户名格式
        if not self.validate_username(user_data.username):
            raise ValueError("用户名格式不正确：3-50位，只能包含字母、数字、下划线")

        # 验证密码强度
        if not self.validate_password_strength(user_data.password):
            raise ValueError("密码格式不正确：至少6位，必须包含字母和数字")

        # 检查用户名是否已存在
        if await self.get_user_by_username(user_data.username):
            raise ValueError("用户名已存在")

        # 检查邮箱是否已存在
        if await self.get_user_by_email(user_data.email):
            raise ValueError("邮箱已存在")

        # 创建用户
        hashed_password = get_password_hash(user_data.password)
        user = User(
            username=user_data.username,
            email=user_data.email,
            hashed_password=hashed_password,
            is_active=True
        )

        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        return user

    async def update_user(self, user_id: int, updates: dict) -> Optional[User]:
        """更新用户信息"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return None

        # 更新密码
        if 'password' in updates:
            updates['hashed_password'] = get_password_hash(updates.pop('password'))

        # 更新其他字段
        for key, value in updates.items():
            if hasattr(user, key):
                setattr(user, key, value)

        await self.db.commit()
        await self.db.refresh(user)

        return user

    async def deactivate_user(self, user_id: int) -> bool:
        """停用用户"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return False

        user.is_active = False
        await self.db.commit()

        return True
