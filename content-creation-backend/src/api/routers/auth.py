"""
认证路由
"""

from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import get_db
from src.models.schemas import LoginRequest, LoginResponse, UserResponse, UserCreate, ApiResponse
from src.services.auth_service import AuthService
from src.utils.security import create_access_token, create_refresh_token, verify_token
from src.config.settings import settings
import structlog

router = APIRouter()
logger = structlog.get_logger(__name__)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


@router.post("/register", response_model=ApiResponse[UserResponse])
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    用户注册
    
    Args:
        user_data: 用户注册数据
        db: 数据库会话
        
    Returns:
        ApiResponse[UserResponse]: 包含用户信息的响应
        
    Raises:
        HTTPException: 注册失败时抛出
    """
    auth_service = AuthService(db)

    try:
        user = await auth_service.create_user(user_data)
        user_response = UserResponse.from_orm(user)
        return ApiResponse.success(data=user_response, message='注册成功')
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/login", response_model=ApiResponse[LoginResponse])
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    用户登录
    
    Args:
        request: 登录请求数据
        db: 数据库会话
        
    Returns:
        ApiResponse[LoginResponse]: 包含令牌和用户信息的响应
        
    Raises:
        HTTPException: 登录失败时抛出
    """
    auth_service = AuthService(db)

    # 记录登录请求信息（不记录密码，只记录长度）
    logger.info("登录请求", 
               username=request.username,
               password_length=len(request.password) if request.password else 0)

    # 验证用户凭据
    try:
        user = await auth_service.authenticate_user(request.username, request.password)
        logger.info("认证结果", 
                   username=request.username,
                   user_found=user is not None,
                   user_id=user.id if user else None)
    except Exception as e:
        logger.error("认证过程出错", 
                    username=request.username,
                    error=str(e),
                    exc_info=True)
        raise
    
    if not user:
        logger.warning("登录失败", username=request.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 创建访问令牌
    access_token_expires = timedelta(hours=settings.jwt_expiration_hours)
    access_token = create_access_token(
        data={"sub": user.username, "user_id": user.id},
        expires_delta=access_token_expires
    )

    # 创建刷新令牌
    refresh_token = create_refresh_token(
        data={"sub": user.username, "user_id": user.id}
    )

    login_response = LoginResponse(
        user=UserResponse.from_orm(user),
        access_token=access_token,
        refresh_token=refresh_token
    )

    return ApiResponse.success(data=login_response, message='登录成功')


@router.post("/refresh", response_model=dict)
async def refresh_token(
    refresh_token: str,
    db: AsyncSession = Depends(get_db)
):
    """刷新访问令牌"""
    # 验证刷新令牌
    payload = verify_token(refresh_token, "refresh")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的刷新令牌"
        )

    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的刷新令牌"
        )

    # 获取用户信息
    auth_service = AuthService(db)
    user = await auth_service.get_user_by_username(username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在"
        )

    # 创建新的访问令牌
    access_token_expires = timedelta(hours=settings.jwt_expiration_hours)
    access_token = create_access_token(
        data={"sub": user.username, "user_id": user.id},
        expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/logout", response_model=ApiResponse[dict])
async def logout(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """
    用户登出
    
    Args:
        token: 访问令牌
        db: 数据库会话
        
    Returns:
        ApiResponse[dict]: 登出成功响应
        
    Note:
        这里可以添加令牌黑名单逻辑，将token加入黑名单
        使token在过期前失效
    """
    # 验证访问令牌（可选，即使token无效也允许登出）
    try:
        payload = verify_token(token, "access")
        if payload:
            username = payload.get("sub")
            # 这里可以添加将token加入黑名单的逻辑
            # 例如：将token存储到Redis黑名单中
            # await redis_client.setex(f"blacklist:{token}", settings.jwt_expiration_hours * 3600, "1")
    except Exception:
        # Token验证失败不影响登出操作
        pass
    
    return ApiResponse.success(data={}, message='登出成功')


@router.get("/me", response_model=ApiResponse[UserResponse])
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """
    获取当前用户信息
    
    Args:
        token: 访问令牌
        db: 数据库会话
        
    Returns:
        ApiResponse[UserResponse]: 包含用户信息的响应
        
    Raises:
        HTTPException: 令牌无效或用户不存在时抛出
    """
    # 验证访问令牌
    payload = verify_token(token, "access")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的访问令牌"
        )

    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的访问令牌"
        )

    # 获取用户信息
    auth_service = AuthService(db)
    user = await auth_service.get_user_by_username(username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在"
        )

    user_response = UserResponse.from_orm(user)
    return ApiResponse.success(data=user_response)
