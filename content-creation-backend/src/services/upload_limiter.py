"""
转存并发限制器
用于控制图片和视频转存的并发数量，避免内存溢出
"""

import asyncio
import structlog

logger = structlog.get_logger(__name__)


class UploadLimiter:
    """转存并发限制器"""
    
    def __init__(
        self,
        max_image_uploads: int = 50,
        max_video_uploads: int = 20
    ):
        """初始化转存限制器.
        
        Args:
            max_image_uploads: 最大图片转存并发数
            max_video_uploads: 最大视频转存并发数
        """
        self.image_semaphore = asyncio.Semaphore(max_image_uploads)
        self.video_semaphore = asyncio.Semaphore(max_video_uploads)
        
        self.max_image_uploads = max_image_uploads
        self.max_video_uploads = max_video_uploads
        
        # 统计信息
        self.image_upload_count = 0
        self.video_upload_count = 0
        self.image_upload_total = 0
        self.video_upload_total = 0
        
        logger.info(
            'UploadLimiter initialized',
            max_image_uploads=max_image_uploads,
            max_video_uploads=max_video_uploads
        )
    
    async def upload_image(self, func, *args, **kwargs):
        """限制图片转存并发.
        
        Args:
            func: 转存函数
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            转存函数的返回值
        """
        self.image_upload_total += 1
        
        async with self.image_semaphore:
            self.image_upload_count += 1
            
            logger.debug(
                'Image upload started',
                current_count=self.image_upload_count,
                max_count=self.max_image_uploads,
                total=self.image_upload_total
            )
            
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                self.image_upload_count -= 1
                
                logger.debug(
                    'Image upload finished',
                    current_count=self.image_upload_count,
                    max_count=self.max_image_uploads
                )
    
    async def upload_video(self, func, *args, **kwargs):
        """限制视频转存并发.
        
        Args:
            func: 转存函数
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            转存函数的返回值
        """
        self.video_upload_total += 1
        
        async with self.video_semaphore:
            self.video_upload_count += 1
            
            logger.debug(
                'Video upload started',
                current_count=self.video_upload_count,
                max_count=self.max_video_uploads,
                total=self.video_upload_total
            )
            
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                self.video_upload_count -= 1
                
                logger.debug(
                    'Video upload finished',
                    current_count=self.video_upload_count,
                    max_count=self.max_video_uploads
                )
    
    def get_stats(self) -> dict:
        """获取统计信息.
        
        Returns:
            包含统计信息的字典
        """
        return {
            'image': {
                'current': self.image_upload_count,
                'max': self.max_image_uploads,
                'total': self.image_upload_total,
                'available': self.max_image_uploads - self.image_upload_count
            },
            'video': {
                'current': self.video_upload_count,
                'max': self.max_video_uploads,
                'total': self.video_upload_total,
                'available': self.max_video_uploads - self.video_upload_count
            }
        }


# 全局实例
# 根据8G内存服务器配置：
# - 图片转存：50个并发（50 × 6MB = 300MB）
# - 视频转存：20个并发（20 × 16MB = 320MB）
# - 总内存占用：~620MB（安全）
upload_limiter = UploadLimiter(
    max_image_uploads=50,
    max_video_uploads=20
)

