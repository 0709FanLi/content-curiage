"""
系统配置表模型
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from ..database import Base


class SystemConfig(Base):
    """系统配置表"""
    
    __tablename__ = "system_configs"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    config_key = Column(String(100), unique=True, nullable=False, index=True, comment="配置键")
    config_value = Column(Text, nullable=False, comment="配置值")
    description = Column(String(500), nullable=True, comment="配置描述")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间")
    
    def __repr__(self):
        return f"<SystemConfig(id={self.id}, key={self.config_key})>"

