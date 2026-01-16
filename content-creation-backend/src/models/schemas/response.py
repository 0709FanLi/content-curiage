"""
统一响应模型
"""

from typing import Generic, TypeVar, Optional
from pydantic import BaseModel

T = TypeVar('T')


class ApiResponse(BaseModel, Generic[T]):
    """
    统一API响应模型
    
    Attributes:
        code: 响应状态码（200表示成功）
        message: 响应消息
        data: 响应数据
    """
    code: int = 200
    message: str = '成功'
    data: Optional[T] = None

    @classmethod
    def success(cls, data: Optional[T] = None, message: str = '操作成功') -> 'ApiResponse[T]':
        """
        创建成功响应
        
        Args:
            data: 响应数据
            message: 响应消息
            
        Returns:
            ApiResponse: 成功响应对象
        """
        return cls(code=200, message=message, data=data)

    @classmethod
    def error(cls, message: str = '操作失败', code: int = 400, data: Optional[T] = None) -> 'ApiResponse[T]':
        """
        创建错误响应
        
        Args:
            message: 错误消息
            code: 错误码
            data: 额外数据
            
        Returns:
            ApiResponse: 错误响应对象
        """
        return cls(code=code, message=message, data=data)


class PageResponse(BaseModel, Generic[T]):
    """
    分页响应模型
    
    Attributes:
        items: 数据列表
        total: 总记录数
        page: 当前页码
        page_size: 每页记录数
        total_pages: 总页数
    """
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int

