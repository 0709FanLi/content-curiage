"""
关键帧管理路由
"""

from fastapi import (
    APIRouter, Depends, HTTPException, status, UploadFile, File, Body
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional, Dict
import structlog

from src.models.database import get_db
from src.models.schemas.keyframe import (
    GenerateKeyframeRequest,
    GenerateKeyframesResponse,
    KeyframeUpdate,
    KeyframeResponse,
    UploadKeyframeImageRequest
)
from src.models.tables import User
from src.services.keyframe_service import KeyframeService
from src.api.dependencies import get_current_active_user
from src.utils.exceptions import NotFoundError, ValidationError

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.post('/generate')
async def generate_keyframes(
    request: GenerateKeyframeRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """生成关键帧（异步）.

    Args:
        request: 生成关键帧请求
        current_user: 当前用户
        db: 数据库会话

    Returns:
        关键帧列表（状态为generating，包装格式）

    Raises:
        HTTPException: 生成失败
    """
    try:
        keyframe_service = KeyframeService(db)
        keyframes = await keyframe_service.generate_keyframes(
            script_id=request.script_id,
            model=request.model,
            aspect_ratio=request.aspect_ratio,
            quality=request.quality,
            only_first_frame=request.only_first_frame,
            reference_image_urls=request.reference_image_urls
        )

        # 转换为响应模型
        keyframe_responses = [
            KeyframeResponse(
                id=kf.id,
                script_id=kf.script_id,
                segment_id=kf.segment_id,
                image_url=kf.image_url,
                prompt=kf.prompt,
                status=kf.status,
                error_message=kf.error_message,
                created_at=kf.created_at,
                updated_at=kf.updated_at
            )
            for kf in keyframes
        ]

        result = GenerateKeyframesResponse(
            keyframes=keyframe_responses,
            total_count=len(keyframe_responses)
        )
        
        # 返回包装格式，与其他API保持一致，使用别名确保字段名为驼峰命名
        return {
            "code": 200,
            "message": "success",
            "data": result.model_dump(by_alias=True)
        }

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error('生成关键帧失败', error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='生成关键帧失败'
        )


@router.post('/continue/{script_id}')
async def continue_generate_keyframes(
    script_id: int,
    request: GenerateKeyframeRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """确认首段关键帧（segment_0）后继续生成其余关键帧（兼容接口）.

    Args:
        script_id: 脚本ID
        request: 生成关键帧请求(包含model, aspect_ratio, quality)
        current_user: 当前用户
        db: 数据库会话

    Returns:
        所有关键帧列表（包装格式）

    Raises:
        HTTPException: 生成失败
    """
    try:
        keyframe_service = KeyframeService(db)
        keyframes = await keyframe_service.continue_generate_remaining_keyframes(
            script_id=script_id,
            model=request.model,
            aspect_ratio=request.aspect_ratio,
            quality=request.quality
        )

        # 转换为响应模型
        keyframe_responses = [
            KeyframeResponse(
                id=kf.id,
                script_id=kf.script_id,
                segment_id=kf.segment_id,
                image_url=kf.image_url,
                prompt=kf.prompt,
                status=kf.status,
                error_message=kf.error_message,
                created_at=kf.created_at,
                updated_at=kf.updated_at
            )
            for kf in keyframes
        ]

        result = GenerateKeyframesResponse(
            keyframes=keyframe_responses,
            total_count=len(keyframe_responses)
        )
        
        return {
            "code": 200,
            "message": "success",
            "data": result.model_dump(by_alias=True)
        }

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error('继续生成关键帧失败', error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='继续生成关键帧失败'
        )


@router.get('/script/{script_id}')
async def get_keyframes_by_script(
    script_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """获取脚本的关键帧列表.

    Args:
        script_id: 脚本ID
        current_user: 当前用户
        db: 数据库会话

    Returns:
        关键帧列表（包装格式）

    Raises:
        HTTPException: 获取失败
    """
    try:
        keyframe_service = KeyframeService(db)
        keyframes = await keyframe_service.get_keyframes_by_script_id(
            script_id
        )

        # 若关键帧 prompt 为空（例如：导入素材后用户只补了脚本文本），则从脚本中解析补齐，
        # 避免前端列表出现空描述。全局移除第0帧后，segment_0 为“首段确认帧”。
        prompt_by_segment_id: Dict[str, str] = {}
        try:
            from src.models.tables.script import Script
            from src.utils.script_parser import parse_script, extract_prompt_for_segment

            script_result = await db.execute(
                select(Script).where(Script.id == script_id)
            )
            script = script_result.scalar_one_or_none()
            if script and getattr(script, "content", None):
                segments = parse_script(str(script.content))
                for seg in segments:
                    if seg.segment_id:
                        prompt_by_segment_id[str(seg.segment_id)] = extract_prompt_for_segment(seg)
                # 兼容历史：若存在 segment_0_first_frame，则用 segment_0 的 prompt 填充（避免出现空描述）
                if "segment_0" in prompt_by_segment_id:
                    prompt_by_segment_id.setdefault(
                        "segment_0_first_frame",
                        prompt_by_segment_id["segment_0"],
                    )
        except Exception as e:
            logger.warning(
                "Failed to enrich keyframe prompts from script",
                script_id=script_id,
                error=str(e),
            )

        # 转换为响应模型
        # 需要刷新对象以避免过期属性访问触发同步数据库IO
        keyframe_responses = []
        for kf in keyframes:
            await db.refresh(kf)
            prompt = kf.prompt
            if not prompt:
                candidate = prompt_by_segment_id.get(str(kf.segment_id))
                if candidate:
                    prompt = candidate
            keyframe_responses.append(
                KeyframeResponse(
                    id=kf.id,
                    script_id=kf.script_id,
                    segment_id=kf.segment_id,
                    image_url=kf.image_url,
                    prompt=prompt,
                    status=kf.status,
                    error_message=kf.error_message,
                    created_at=kf.created_at,
                    updated_at=kf.updated_at
                )
            )

        result = GenerateKeyframesResponse(
            keyframes=keyframe_responses,
            total_count=len(keyframe_responses)
        )
        
        # 返回包装格式，与其他API保持一致，使用别名确保字段名为驼峰命名
        return {
            "code": 200,
            "message": "success",
            "data": result.model_dump(by_alias=True)
        }

    except Exception as e:
        logger.error('获取关键帧列表失败', error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='获取关键帧列表失败'
        )


@router.put('/{keyframe_id}')
async def update_keyframe(
    keyframe_id: int,
    update_data: KeyframeUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """更新关键帧（提示词、图片等）.

    Args:
        keyframe_id: 关键帧ID
        update_data: 更新数据
        current_user: 当前用户
        db: 数据库会话

    Returns:
        更新后的关键帧（包装格式）

    Raises:
        HTTPException: 更新失败
    """
    try:
        keyframe_service = KeyframeService(db)
        keyframe = await keyframe_service.get_keyframe_by_id(keyframe_id)

        if not keyframe:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'关键帧不存在: {keyframe_id}'
            )

        # 更新提示词
        if update_data.prompt is not None:
            keyframe = await keyframe_service.update_keyframe_prompt(
                keyframe_id, update_data.prompt
            )
            # update_keyframe_prompt 已经 commit 过了，需要刷新对象
            await db.refresh(keyframe)

        # 更新其他字段
        need_commit = False
        if update_data.image_url is not None:
            keyframe.image_url = update_data.image_url
            need_commit = True

        if update_data.status is not None:
            keyframe.status = update_data.status
            need_commit = True

        if update_data.error_message is not None:
            keyframe.error_message = update_data.error_message
            need_commit = True

        if need_commit:
            await db.commit()
            await db.refresh(keyframe)

        result = KeyframeResponse(
            id=keyframe.id,
            script_id=keyframe.script_id,
            segment_id=keyframe.segment_id,
            image_url=keyframe.image_url,
            prompt=keyframe.prompt,
            status=keyframe.status,
            error_message=keyframe.error_message,
            created_at=keyframe.created_at,
            updated_at=keyframe.updated_at
        )
        
        # 返回包装格式，与其他API保持一致，使用别名确保字段名为驼峰命名
        return {
            "code": 200,
            "message": "success",
            "data": result.model_dump(by_alias=True)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error('更新关键帧失败', error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='更新关键帧失败'
        )


@router.post('/{keyframe_id}/regenerate')
async def regenerate_keyframe(
    keyframe_id: int,
    request_data: Optional[Dict] = Body(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """重新生成关键帧.

    Args:
        keyframe_id: 关键帧ID
        model: 模型参数（可选，使用项目默认配置）
        aspect_ratio: 图像比例（可选）
        quality: 清晰度（可选）
        current_user: 当前用户
        db: 数据库会话

    Returns:
        更新后的关键帧（状态为generating，包装格式）

    Raises:
        HTTPException: 重新生成失败
    """
    try:
        # 从请求体中获取参数
        model = request_data.get('model') if request_data else None
        aspect_ratio = request_data.get('aspectRatio') or request_data.get('aspect_ratio') if request_data else None
        quality = request_data.get('quality') if request_data else None
        
        keyframe_service = KeyframeService(db)
        keyframe = await keyframe_service.regenerate_keyframe(
            keyframe_id=keyframe_id,
            model=model,
            aspect_ratio=aspect_ratio,
            quality=quality
        )

        result = KeyframeResponse(
            id=keyframe.id,
            script_id=keyframe.script_id,
            segment_id=keyframe.segment_id,
            image_url=keyframe.image_url,
            prompt=keyframe.prompt,
            status=keyframe.status,
            error_message=keyframe.error_message,
            created_at=keyframe.created_at,
            updated_at=keyframe.updated_at
        )
        
        # 返回包装格式，与其他API保持一致，使用别名确保字段名为驼峰命名
        return {
            "code": 200,
            "message": "success",
            "data": result.model_dump(by_alias=True)
        }

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error('重新生成关键帧失败', error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='重新生成关键帧失败'
        )


@router.post('/{keyframe_id}/upload')
async def upload_keyframe_image(
    keyframe_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """上传本地图片替换关键帧.

    Args:
        keyframe_id: 关键帧ID
        file: 上传的文件
        current_user: 当前用户
        db: 数据库会话

    Returns:
        更新后的关键帧（包装格式）

    Raises:
        HTTPException: 上传失败
    """
    try:
        # 读取文件内容
        file_data = await file.read()

        keyframe_service = KeyframeService(db)
        keyframe = await keyframe_service.upload_keyframe_image(
            keyframe_id=keyframe_id,
            file_data=file_data,
            filename=file.filename or 'uploaded_image.jpg'
        )

        result = KeyframeResponse(
            id=keyframe.id,
            script_id=keyframe.script_id,
            segment_id=keyframe.segment_id,
            image_url=keyframe.image_url,
            prompt=keyframe.prompt,
            status=keyframe.status,
            error_message=keyframe.error_message,
            created_at=keyframe.created_at,
            updated_at=keyframe.updated_at
        )
        
        # 返回包装格式，与其他API保持一致，使用别名确保字段名为驼峰命名
        return {
            "code": 200,
            "message": "success",
            "data": result.model_dump(by_alias=True)
        }

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error('上传关键帧图片失败', error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='上传关键帧图片失败'
        )
