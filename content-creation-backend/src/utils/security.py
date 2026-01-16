"""
安全工具函数
"""

from datetime import datetime, timedelta
from typing import Any, Union
import hashlib
import secrets
from jose import JWTError, jwt

from src.config.settings import settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    import structlog
    logger = structlog.get_logger(__name__)
    
    # 简单验证：比较SHA256哈希
    computed_hash = get_password_hash(plain_password)
    is_valid = computed_hash == hashed_password
    
    logger.debug("密码验证详情",
                plain_password_length=len(plain_password),
                computed_hash=computed_hash[:20] + "...",
                stored_hash=hashed_password[:20] + "..." if hashed_password else None,
                is_valid=is_valid)
    
    return is_valid


def get_password_hash(password: str) -> str:
    """获取密码哈希"""
    # 使用SHA256 + salt进行哈希
    salt = "content_creation_salt"  # 生产环境应该使用随机salt
    combined = f"{password}{salt}".encode('utf-8')
    return hashlib.sha256(combined).hexdigest()


def create_access_token(
    data: dict,
    expires_delta: Union[timedelta, None] = None
) -> str:
    """创建访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=settings.jwt_expiration_hours)

    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """创建刷新令牌"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=30)  # 刷新令牌有效期30天

    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )
    return encoded_jwt


def verify_token(token: str, token_type: str = "access") -> Union[dict, None]:
    """验证令牌"""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )

        # 检查令牌类型
        if payload.get("type") != token_type:
            return None

        return payload
    except JWTError:
        return None


def get_token_payload(token: str) -> Union[dict, None]:
    """获取令牌载荷（不验证过期时间）"""
    try:
        payload = jwt.get_unverified_claims(token)
        return payload
    except JWTError:
        return None


def generate_secure_token(length: int = 32) -> str:
    """生成安全随机令牌"""
    import secrets
    import string

    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def sanitize_filename(filename: str) -> str:
    """清理文件名，防止路径遍历攻击"""
    import os
    import re

    # 移除路径分隔符
    filename = os.path.basename(filename)

    # 移除或替换危险字符
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)

    # 限制长度
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:255-len(ext)] + ext

    return filename


def validate_file_type(filename: str, allowed_types: list) -> bool:
    """验证文件类型"""
    import os

    if not filename:
        return False

    _, ext = os.path.splitext(filename.lower())
    return ext in allowed_types
