"""
项目管理服务
"""

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from sqlalchemy.orm import selectinload
import structlog

from src.models.tables.project import Project
from src.models.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse
from src.utils.exceptions import NotFoundError

logger = structlog.get_logger(__name__)


class ProjectService:
    """项目管理服务类"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_project(
        self, 
        project_data: ProjectCreate, 
        user_id: int
    ) -> Project:
        """
        创建项目
        
        Args:
            project_data: 项目创建数据
            user_id: 用户ID
            
        Returns:
            创建的项目对象
        """
        project = Project(
            name=project_data.name,
            description=project_data.description,
            user_id=user_id,
            generation_mode=project_data.generation_mode or 'step_by_step'
        )
        
        self.db.add(project)
        await self.db.commit()
        await self.db.refresh(project)
        
        logger.info("项目创建成功", project_id=project.id, user_id=user_id)
        return project

    async def get_project(self, project_id: int, user_id: int) -> Optional[Project]:
        """
        获取项目详情
        
        Args:
            project_id: 项目ID
            user_id: 用户ID
            
        Returns:
            项目对象，如果不存在返回None
        """
        from src.models.tables.script import Script
        
        result = await self.db.execute(
            select(Project)
            .where(Project.id == project_id, Project.user_id == user_id)
            .options(
                selectinload(Project.scripts).selectinload(Script.keyframes),
                selectinload(Project.scripts).selectinload(Script.video_segments)
            )
        )
        project = result.scalar_one_or_none()
        return project

    async def get_projects(
        self, 
        user_id: int, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Project]:
        """
        获取用户项目列表
        
        Args:
            user_id: 用户ID
            skip: 跳过数量
            limit: 限制数量
            
        Returns:
            项目列表
        """
        result = await self.db.execute(
            select(Project)
            .where(Project.user_id == user_id)
            .order_by(desc(func.coalesce(Project.first_script_generated_at, Project.updated_at)))
            .offset(skip)
            .limit(limit)
        )
        projects = result.scalars().all()
        return list(projects)

    async def get_recent_projects(self, user_id: int, limit: int = 5) -> List[Project]:
        """
        获取最近项目列表
        
        Args:
            user_id: 用户ID
            limit: 限制数量
            
        Returns:
            最近项目列表
        """
        result = await self.db.execute(
            select(Project)
            .where(Project.user_id == user_id)
            .order_by(desc(func.coalesce(Project.first_script_generated_at, Project.updated_at)))
            .limit(limit)
        )
        projects = result.scalars().all()
        return list(projects)

    async def update_project(
        self, 
        project_id: int, 
        project_data: ProjectUpdate, 
        user_id: int
    ) -> Project:
        """
        更新项目
        
        Args:
            project_id: 项目ID
            project_data: 项目更新数据
            user_id: 用户ID
            
        Returns:
            更新后的项目对象
            
        Raises:
            NotFoundError: 项目不存在
        """
        project = await self.get_project(project_id, user_id)
        if not project:
            raise NotFoundError(f"项目 {project_id} 不存在")

        # 更新字段（使用 by_alias=False 确保使用实际的字段名）
        update_data = project_data.model_dump(exclude_unset=True, by_alias=False)
        for field, value in update_data.items():
            setattr(project, field, value)
        
        # 手动更新 updated_at 字段，确保时间戳正确更新
        from datetime import datetime, timezone
        project.updated_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(project)
        
        logger.info("项目更新成功", project_id=project_id, user_id=user_id)
        return project

    async def delete_project(self, project_id: int, user_id: int) -> None:
        """
        删除项目
        
        Args:
            project_id: 项目ID
            user_id: 用户ID
            
        Raises:
            NotFoundError: 项目不存在
        """
        project = await self.get_project(project_id, user_id)
        if not project:
            raise NotFoundError(f"项目 {project_id} 不存在")

        await self.db.delete(project)
        await self.db.commit()
        
        logger.info("项目删除成功", project_id=project_id, user_id=user_id)

