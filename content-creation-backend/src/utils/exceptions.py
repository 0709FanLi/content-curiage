"""
自定义异常和异常处理器
"""

from typing import Any, Dict
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
import structlog

logger = structlog.get_logger(__name__)


class ApiError(HTTPException):
    """API异常基类"""

    def __init__(
        self,
        status_code: int,
        detail: str,
        error_code: str = None
    ):
        super().__init__(status_code=status_code, detail=detail)
        self.error_code = error_code or f"ERROR_{status_code}"


class ValidationError(ApiError):
    """验证错误"""

    def __init__(self, detail: str):
        super().__init__(status_code=400, detail=detail, error_code="VALIDATION_ERROR")


class AuthenticationError(ApiError):
    """认证错误"""

    def __init__(self, detail: str = "认证失败"):
        super().__init__(status_code=401, detail=detail, error_code="AUTHENTICATION_ERROR")


class AuthorizationError(ApiError):
    """授权错误"""

    def __init__(self, detail: str = "权限不足"):
        super().__init__(status_code=403, detail=detail, error_code="AUTHORIZATION_ERROR")


class NotFoundError(ApiError):
    """资源未找到错误"""

    def __init__(self, resource: str = "资源"):
        super().__init__(status_code=404, detail=f"{resource}不存在", error_code="NOT_FOUND")


class ConflictError(ApiError):
    """资源冲突错误"""

    def __init__(self, detail: str = "资源冲突"):
        super().__init__(status_code=409, detail=detail, error_code="CONFLICT_ERROR")


class BusinessError(ApiError):
    """业务逻辑错误"""

    def __init__(self, detail: str = "业务处理失败"):
        super().__init__(status_code=400, detail=detail, error_code="BUSINESS_ERROR")


class ExternalServiceError(ApiError):
    """外部服务错误"""

    def __init__(self, service: str, detail: str = None):
        detail = detail or f"{service}服务异常"
        super().__init__(status_code=502, detail=detail, error_code="EXTERNAL_SERVICE_ERROR")


def setup_exception_handlers(app):
    """设置全局异常处理器"""

    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
        """自定义API异常处理器"""
        logger.error(
            "API error occurred",
            exc_info=exc,
            path=request.url.path,
            method=request.method,
            status_code=exc.status_code,
            error_code=getattr(exc, 'error_code', None),
        )

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": getattr(exc, 'error_code', f"ERROR_{exc.status_code}"),
                "message": exc.detail,
                "data": None,
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        """HTTP异常处理器"""
        logger.warning(
            "HTTP exception occurred",
            path=request.url.path,
            method=request.method,
            status_code=exc.status_code,
            detail=exc.detail,
        )

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": f"HTTP_{exc.status_code}",
                "message": exc.detail,
                "data": None,
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """通用异常处理器"""
        logger.error(
            "Unexpected error occurred",
            exc_info=exc,
            path=request.url.path,
            method=request.method,
        )

        return JSONResponse(
            status_code=500,
            content={
                "code": "INTERNAL_SERVER_ERROR",
                "message": "服务器内部错误",
                "data": None,
            },
        )


# 常用异常实例
validation_error = ValidationError
auth_error = AuthenticationError
permission_error = AuthorizationError
not_found_error = NotFoundError
conflict_error = ConflictError
external_service_error = ExternalServiceError
