"""
脚本管理路由
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.models.database import get_db
from src.models.schemas.script import (
    GenerateScriptRequest, 
    ScriptResponse, 
    ScriptSegment,
    ScriptUpdate,
    OptimizeScriptRequest
)
from src.models.schemas.project import ProjectCreate
from src.models.schemas.response import ApiResponse
from src.models.tables import User
from src.services.script_service import ScriptService
from src.services.project_service import ProjectService
from src.api.dependencies import get_current_active_user
from src.utils.exceptions import ValidationError, NotFoundError, ExternalServiceError

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.post("/generate", response_model=dict)
async def generate_script(
    request: GenerateScriptRequest,
    model: str = Query("deepseek-chat", description="使用的模型名称"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    生成脚本并自动创建项目和脚本记录
    
    Args:
        request: 生成脚本请求
        model: 使用的模型名称（查询参数，默认deepseek-chat）
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        生成的脚本数据（包含项目ID和脚本ID）
    """
    try:
        script_service = ScriptService(db)
        project_service = ProjectService(db)
        
        # 记录请求信息（包括参考图）
        logger.info(
            "Received script generation request",
            inspiration=request.inspiration[:50],
            style=request.style,
            model=model,
            enable_search=getattr(request, "enable_search", False),
            has_reference_images=bool(request.reference_image_urls and len(request.reference_image_urls) > 0),
            reference_image_count=len(request.reference_image_urls) if request.reference_image_urls else 0
        )
        
        # 生成脚本内容
        result = await script_service.generate_script(request, model=model)
        
        logger.info(
            "Script generated successfully",
            inspiration=request.inspiration[:50],
            style=request.style,
            segment_count=len(result["segments"])
        )
        
        # 如果请求中没有项目ID，自动创建项目
        project_id = request.project_id
        if not project_id:
            # 创建项目，使用创意内容作为项目名称，最多10个字
            inspiration_text = request.inspiration.strip()
            if len(inspiration_text) > 10:
                project_name = inspiration_text[:10] + "..."
            else:
                project_name = inspiration_text if inspiration_text else "未命名项目"
            
            print(f"[DEBUG] 准备创建项目: generation_mode={request.generation_mode}")
            project_data = ProjectCreate(
                name=project_name,
                description=request.inspiration[:500] if len(request.inspiration) > 500 else request.inspiration,
                generation_mode=request.generation_mode or 'step_by_step',
                reference_image_urls=request.reference_image_urls,
            )
            project = await project_service.create_project(project_data, current_user.id)
            project_id = project.id
            
            # 更新项目的对话内容
            from src.models.schemas.project import ProjectUpdate
            project_update = ProjectUpdate(
                conversation_content=request.inspiration,
                reference_image_urls=request.reference_image_urls,
            )
            await project_service.update_project(project_id, project_update, current_user.id)
            
            logger.info("项目自动创建成功", project_id=project_id, user_id=current_user.id)
        
        # 创建脚本记录到数据库
        script = await script_service.create_script(
            project_id=project_id,
            content=result["content"],
            style=result["style"],
            total_duration=result["total_duration"],
            segment_duration=result["segment_duration"],
            segments=result["segments"]
        )
        
        # 立即保存 script.id，避免后续访问时对象过期
        script_id = script.id

        # 如果是复用已有 projectId 的场景，也要把参考图写入项目，保证刷新/重进后关键帧能继续使用
        if request.reference_image_urls and len(request.reference_image_urls) > 0:
            from src.models.schemas.project import ProjectUpdate
            try:
                await project_service.update_project(
                    project_id,
                    ProjectUpdate(reference_image_urls=request.reference_image_urls),
                    current_user.id,
                )
            except Exception as e:
                logger.warning(
                    "Failed to persist reference images to project",
                    project_id=project_id,
                    error=str(e),
                )
        
        # 提取脚本的第一段作为项目描述
        # 解析脚本内容，提取第一个有效段落（跳过第0帧）
        script_description = ""
        script_lines = result["content"].strip().split('\n')
        for line in script_lines:
            line = line.strip()
            # 跳过空行和第0帧
            if not line or line.startswith('第0帧') or line.startswith('(0:00 - 0:00)'):
                continue
            # 跳过时间戳行，提取内容
            if line.startswith('(') and ')' in line:
                # 提取括号后的内容
                content_start = line.index(')') + 1
                script_description = line[content_start:].strip()
                break
            elif '-' in line and 's' in line and line.split()[0].replace('-', '').replace('s', '').isdigit():
                # 格式如 "0-6s 内容"
                parts = line.split(None, 1)
                if len(parts) > 1:
                    script_description = parts[1].strip()
                    break
        
        # 如果没有找到，使用整个脚本的前100个字
        if not script_description:
            script_description = result["content"][:100]
        
        # 限制描述长度为200字
        if len(script_description) > 200:
            script_description = script_description[:200] + "..."
        
        # 构建对话历史JSON（首条对话必须包含用户的创意描述，供分步脚本页展示）
        import json
        from datetime import datetime
        from src.models.schemas.project import ProjectUpdate
        from src.models.tables.project import ProjectStatus
        
        conversation_history = [{
            "userInput": request.inspiration,  # 保存完整创意描述（来自 /inspiration）
            "aiResponse": result["content"],  # AI生成的脚本内容
            "timestamp": int(datetime.now().timestamp() * 1000),  # 毫秒时间戳
            "isEditable": True  # 最新的对话项可编辑
        }]
        conversation_content_json = json.dumps(conversation_history, ensure_ascii=False)
        
        # 更新项目状态、描述和对话内容
        project_update = ProjectUpdate(
            status=ProjectStatus.SCRIPT_GENERATED,
            description=script_description,
            conversation_content=conversation_content_json  # 更新对话内容
        )
        await project_service.update_project(project_id, project_update, current_user.id)
        
        # 转换为响应格式
        response_data = {
            "id": script_id,
            "projectId": project_id,
            "content": result["content"],
            # 可观测：参考图解析是否用于脚本生成（dev 环境会带 errorMessage）
            "visionAnalysis": result.get("vision_analysis"),
            "segments": [
                {
                    "id": seg.id,
                    "timeStart": seg.time_start,
                    "timeEnd": seg.time_end,
                    "content": seg.content,
                    "scene": seg.scene,
                    "presenter": seg.presenter,
                    "subtitle": seg.subtitle
                }
                for seg in result["segments"]
            ],
            "style": result["style"],
            "totalDuration": result["total_duration"],
            "segmentDuration": result["segment_duration"]
        }
        
        return {
            "code": 200,
            "message": "success",
            "data": response_data
        }
    except ValidationError as e:
        logger.warning("Validation error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Script generation failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"脚本生成失败: {str(e)}"
        )


@router.get("/{script_id}", response_model=dict)
async def get_script(
    script_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取脚本详情
    
    Args:
        script_id: 脚本ID
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        脚本详情
    """
    try:
        script_service = ScriptService(db)
        project_service = ProjectService(db)
        
        # 获取脚本
        from sqlalchemy import select
        from src.models.tables.script import Script
        result = await db.execute(
            select(Script).where(Script.id == script_id)
        )
        script = result.scalar_one_or_none()
        
        if not script:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"脚本 {script_id} 不存在"
            )
        
        # 验证项目是否属于当前用户
        project = await project_service.get_project(script.project_id, current_user.id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"项目不存在或无权限"
            )
        
        # 转换为响应格式
        response_data = {
            "id": script.id,
            "projectId": script.project_id,
            "content": script.content,
            "style": script.style,
            "totalDuration": script.total_duration,
            "segmentDuration": script.segment_duration,
            "segments": script.segments or [],
            "optimizedContent": script.optimized_content,
            "exportedVideoUrl": script.exported_video_url  # 添加导出视频URL
        }
        
        return {
            "code": 200,
            "message": "success",
            "data": response_data
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取脚本失败", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取脚本失败"
        )


@router.put("/{script_id}", response_model=dict)
async def update_script(
    script_id: int,
    script_data: ScriptUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    更新脚本
    
    Args:
        script_id: 脚本ID
        script_data: 脚本更新数据
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        更新后的脚本数据
    """
    try:
        script_service = ScriptService(db)
        
        # 先获取脚本以获取项目ID
        from sqlalchemy import select
        from src.models.tables.script import Script
        result = await db.execute(
            select(Script).where(Script.id == script_id)
        )
        script = result.scalar_one_or_none()
        
        if not script:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"脚本 {script_id} 不存在"
            )
        
        # 验证项目是否属于当前用户
        project_service = ProjectService(db)
        project = await project_service.get_project(script.project_id, current_user.id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"项目不存在或无权限"
            )
        
        # 更新脚本
        updated_script = await script_service.update_script(
            script_id=script_id,
            project_id=script.project_id,
            script_data=script_data
        )
        
        # 转换为响应格式
        response_data = {
            "id": updated_script.id,
            "projectId": updated_script.project_id,
            "content": updated_script.content,
            "style": updated_script.style,
            "totalDuration": updated_script.total_duration,
            "segmentDuration": updated_script.segment_duration,
            "segments": updated_script.segments or [],
            "optimizedContent": updated_script.optimized_content
        }
        
        return {
            "code": 200,
            "message": "success",
            "data": response_data
        }
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error("更新脚本失败", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新脚本失败: {str(e)}"
        )


@router.post("/{script_id}/optimize", response_model=dict)
async def optimize_script(
    script_id: int,
    request: OptimizeScriptRequest,
    model: str = Query("deepseek-chat", description="使用的模型名称"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    优化脚本，使用创意描述作为补充
    
    Args:
        script_id: 脚本ID
        request: 优化请求（包含创意描述）
        model: 使用的模型名称（查询参数，默认deepseek-chat）
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        优化后的脚本数据
    """
    try:
        script_service = ScriptService(db)
        
        # 先获取脚本以获取项目ID
        from sqlalchemy import select
        from src.models.tables.script import Script
        result = await db.execute(
            select(Script).where(Script.id == script_id)
        )
        script = result.scalar_one_or_none()
        
        if not script:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"脚本 {script_id} 不存在"
            )
        
        # 验证项目是否属于当前用户
        project_service = ProjectService(db)
        project = await project_service.get_project(script.project_id, current_user.id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"项目不存在或无权限"
            )
        
        # 优化脚本
        optimized_script = await script_service.optimize_script(
            script_id=script_id,
            project_id=script.project_id,
            creative_description=request.optimization,
            model=model,
            enable_search=getattr(request, "enable_search", False),
        )
        
        # 获取当前项目的对话历史，追加新的对话项
        import json
        from datetime import datetime
        
        # 解析现有的对话历史
        existing_conversation = []
        if project.conversation_content:
            try:
                existing_conversation = json.loads(project.conversation_content)
                if not isinstance(existing_conversation, list):
                    existing_conversation = []
            except (json.JSONDecodeError, TypeError):
                existing_conversation = []
        
        # 将之前的对话项设为不可编辑
        for item in existing_conversation:
            if isinstance(item, dict):
                item["isEditable"] = False
        
        # 追加新的对话项（用户输入 + AI回复）
        new_conversation_item = {
            "userInput": request.optimization,  # 用户输入的优化描述
            "aiResponse": optimized_script.content,  # AI优化后的脚本内容
            "timestamp": int(datetime.now().timestamp() * 1000),  # 毫秒时间戳
            "isEditable": True  # 最新的对话项可编辑
        }
        existing_conversation.append(new_conversation_item)
        
        # 更新项目的对话内容
        from src.models.schemas.project import ProjectUpdate
        conversation_content_json = json.dumps(existing_conversation, ensure_ascii=False)
        project_update = ProjectUpdate(conversation_content=conversation_content_json)
        await project_service.update_project(script.project_id, project_update, current_user.id)
        
        # 更新store中的项目对话内容（如果需要）
        # 这里已经通过API更新了数据库，前端会通过项目更新接口获取最新数据
        
        logger.info(
            "Script optimized successfully",
            script_id=script_id,
            model=model,
            enable_search=getattr(request, "enable_search", False),
            optimization_length=len(request.optimization)
        )
        
        # 转换为响应格式
        response_data = {
            "id": optimized_script.id,
            "projectId": optimized_script.project_id,
            "content": optimized_script.content,
            "style": optimized_script.style,
            "totalDuration": optimized_script.total_duration,
            "segmentDuration": optimized_script.segment_duration,
            "segments": optimized_script.segments or [],
            "optimizedContent": optimized_script.optimized_content
        }
        
        return {
            "code": 200,
            "message": "success",
            "data": response_data
        }
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValidationError as e:
        logger.warning("Validation error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ExternalServiceError as e:
        # ExternalServiceError已经包含了详细的错误信息
        logger.error("外部服务调用失败", error=e.detail, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=e.detail
        )
    except Exception as e:
        logger.error("优化脚本失败", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"优化脚本失败: {str(e)}"
        )


@router.post("/{script_id}/cancel", response_model=ApiResponse[dict])
async def cancel_generation(
    script_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    取消脚本的所有生成任务（关键帧和视频）
    
    使用双重取消机制：
    1. Redis取消标志（快速响应）
    2. 数据库状态更新（持久化）
    
    Args:
        script_id: 脚本ID
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        取消结果
    """
    try:
        from sqlalchemy import select, update
        from datetime import datetime, timezone
        from src.models.tables.script import Script
        from src.models.tables.keyframe import Keyframe
        from src.models.tables.video_segment import VideoSegment
        from src.utils.redis_client import TaskCancellationManager
        
        # 验证脚本存在且属于当前用户
        result = await db.execute(
            select(Script).where(Script.id == script_id)
        )
        script = result.scalar_one_or_none()
        
        if not script:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"脚本 {script_id} 不存在"
            )
        
        # 验证项目所有权
        from src.models.tables.project import Project
        project_result = await db.execute(
            select(Project).where(Project.id == script.project_id)
        )
        project = project_result.scalar_one_or_none()
        
        if not project or project.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权操作此脚本"
            )
        
        # 1. 设置Redis取消标志（快速响应，后台任务会立即检测到）
        await TaskCancellationManager.set_cancellation_flag(script_id)

        # 1.1 写入数据库取消标记（即使 Redis 不可用，导出/耗时任务也能感知）
        try:
            script.cancelled_at = datetime.now(timezone.utc)
        except Exception:
            # 兼容没有 timezone 的环境
            script.cancelled_at = datetime.utcnow()
        
        # 2. 取消所有未完成的关键帧（包括 PENDING 和 GENERATING 状态）
        await db.execute(
            update(Keyframe)
            .where(Keyframe.script_id == script_id)
            .where(Keyframe.status.in_(['GENERATING', 'PENDING']))
            .values(status='failed', error_message='用户取消生成')
        )
        
        # 3. 取消所有未完成的视频（包括 PENDING 和 GENERATING 状态）
        await db.execute(
            update(VideoSegment)
            .where(VideoSegment.script_id == script_id)
            .where(VideoSegment.status.in_(['GENERATING', 'PENDING']))
            .values(status='failed', error_message='用户取消生成')
        )
        
        await db.commit()
        
        logger.info(
            "用户取消生成任务（Redis标志已设置，数据库状态已更新）",
            script_id=script_id,
            user_id=current_user.id
        )
        
        return ApiResponse(
            code=200,
            message="已取消所有生成任务",
            data={"script_id": script_id}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("取消生成失败", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"取消生成失败: {str(e)}"
        )
