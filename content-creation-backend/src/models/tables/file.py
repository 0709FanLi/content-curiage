"""
文件表模型
"""

from datetime import datetime
from sqlalchemy import String, DateTime, Integer, BigInteger
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.models.database import Base


class File(Base):
    """文件表"""

    __tablename__ = "files"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_url: Mapped[str] = mapped_column(String(500), nullable=True)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)  # 文件大小（字节）
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)  # image, video, document等
    uploaded_by: Mapped[int] = mapped_column(Integer, nullable=True)  # 上传用户ID
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<File(id={self.id}, filename={self.filename}, file_type={self.file_type})>"
