"""
阿里云OSS服务类
提供文件上传、下载、删除等功能
"""

import os
import uuid
from datetime import datetime
from io import BytesIO
from typing import Any, BinaryIO, Dict, List, Optional
from urllib.parse import quote

import oss2
from oss2.exceptions import OssError
import structlog

logger = structlog.get_logger(__name__)


class OSSService:
    """阿里云OSS服务类."""

    def __init__(self) -> None:
        """初始化OSS服务."""
        self.access_key_id = os.getenv('OSS_ACCESS_KEY_ID', '')
        self.access_key_secret = os.getenv('OSS_ACCESS_KEY_SECRET', '')
        self.endpoint = os.getenv(
            'OSS_ENDPOINT', 'https://oss-cn-shanghai.aliyuncs.com'
        )
        self.bucket_name = os.getenv('OSS_BUCKET_NAME', '')
        self.public_read = os.getenv('OSS_PUBLIC_READ', 'true').lower() == 'true'
        self.url_expire_seconds = int(
            os.getenv('OSS_URL_EXPIRE_SECONDS', '3600')
        )
        self.max_file_size = int(
            os.getenv('OSS_MAX_FILE_SIZE', str(200 * 1024 * 1024))  # 默认200MB，支持长视频
        )

        # 检查配置是否完整
        self._is_configured = bool(
            self.access_key_id
            and self.access_key_secret
            and self.bucket_name
        )

        # 初始化OSS客户端
        self.auth: Optional[oss2.Auth] = None
        self.bucket: Optional[oss2.Bucket] = None

        if self._is_configured:
            try:
                self.auth = oss2.Auth(
                    self.access_key_id, self.access_key_secret
                )
                self.bucket = oss2.Bucket(
                    self.auth, self.endpoint, self.bucket_name
                )
                logger.info(
                    'OSSService initialized',
                    bucket=self.bucket_name,
                    endpoint=self.endpoint
                )
            except Exception as e:
                logger.error('OSS initialization failed', error=str(e))
                self._is_configured = False
        else:
            logger.warning('OSS configuration incomplete')

    def _ensure_configured(self) -> None:
        """确保OSS已配置，否则抛出异常."""
        if not self._is_configured or not self.bucket:
            raise Exception('OSS服务未配置，请检查环境变量')

    def _generate_object_key(
        self,
        category: str,
        filename: str,
        use_date_path: bool = True
    ) -> str:
        """生成OSS对象键（文件路径）.

        Args:
            category: 文件类别
            filename: 原始文件名
            use_date_path: 是否使用日期路径

        Returns:
            OSS对象键
        """
        # 生成唯一ID
        unique_id = uuid.uuid4().hex[:8]

        # 处理文件名（保留扩展名）
        name, ext = os.path.splitext(filename)
        safe_filename = f'{unique_id}_{name}{ext}'

        # 构建路径
        if use_date_path:
            now = datetime.now()
            date_path = now.strftime('%Y/%m/%d')
            object_key = f'{category}/{date_path}/{safe_filename}'
        else:
            object_key = f'{category}/{safe_filename}'

        return object_key

    def _get_public_url(self, object_key: str) -> str:
        """获取公共访问URL.

        Args:
            object_key: OSS对象键

        Returns:
            公共访问URL
        """
        endpoint_host = self.endpoint.replace('https://', '')
        return f'https://{self.bucket_name}.{endpoint_host}/{quote(object_key)}'

    def _get_signed_url(
        self, object_key: str, expires: Optional[int] = None
    ) -> str:
        """获取带签名的URL.

        Args:
            object_key: OSS对象键
            expires: 过期时间（秒）

        Returns:
            签名URL
        """
        if expires is None:
            expires = self.url_expire_seconds

        try:
            url = self.bucket.sign_url('GET', object_key, expires)
            return url
        except Exception as e:
            logger.error('Failed to generate signed URL', error=str(e))
            return self._get_public_url(object_key)

    def upload_file(
        self,
        file_data: BinaryIO,
        filename: str,
        category: str = 'uploads',
        content_type: Optional[str] = None,
        force_download: bool = False
    ) -> Dict[str, Any]:
        """上传文件到OSS.

        Args:
            file_data: 文件数据流
            filename: 原始文件名
            category: 文件类别 (images/videos/keyframes)
            content_type: 文件MIME类型
            force_download: 是否强制下载（设置 Content-Disposition 为 attachment）

        Returns:
            包含文件信息的字典

        Raises:
            Exception: 文件大小超过限制或上传失败
        """
        self._ensure_configured()

        # 读取文件内容
        file_content = file_data.read()
        file_size = len(file_content)

        # 检查文件大小
        if file_size > self.max_file_size:
            raise Exception(
                f'文件大小超过限制: {file_size / 1024 / 1024:.2f}MB'
            )

        # 生成对象键
        object_key = self._generate_object_key(category, filename)

        # 设置请求头
        headers: Dict[str, str] = {}
        if content_type:
            headers['Content-Type'] = content_type
        
        # 如果需要强制下载，设置 Content-Disposition
        if force_download:
            headers['Content-Disposition'] = f'attachment; filename="{filename}"'

        # 上传文件
        result = self.bucket.put_object(
            object_key, file_content, headers=headers
        )

        # 获取访问URL
        if self.public_read:
            url = self._get_public_url(object_key)
        else:
            url = self._get_signed_url(object_key)

        logger.info(
            'File uploaded to OSS',
            object_key=object_key,
            size=file_size,
            category=category
        )

        return {
            'object_key': object_key,
            'url': url,
            'size': file_size,
            'content_type': content_type,
            'etag': result.etag,
            'bucket': self.bucket_name
        }

    async def upload_from_url(
        self, url: str, filename: str, category: str = 'images'
    ) -> Dict[str, Any]:
        """从URL下载文件并上传到OSS（异步）.

        Args:
            url: 源文件URL
            filename: 保存的文件名
            category: 文件类别 (images/videos/keyframes)

        Returns:
            包含文件信息的字典

        Raises:
            Exception: 下载或上传失败
        """
        import httpx

        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.get(url)
            response.raise_for_status()

            file_content = response.content
            content_type = response.headers.get('Content-Type')

            logger.info(
                'File downloaded from URL',
                url=url,
                size=len(file_content) / 1024 / 1024
            )

            # 上传到OSS
            file_stream = BytesIO(file_content)

            result = self.upload_file(
                file_stream, filename, category, content_type
            )

            return result

    def delete_file(self, object_key: str) -> bool:
        """删除OSS文件.

        Args:
            object_key: OSS对象键

        Returns:
            是否删除成功

        Raises:
            Exception: 删除失败
        """
        self._ensure_configured()

        try:
            self.bucket.delete_object(object_key)
            logger.info('File deleted from OSS', object_key=object_key)
            return True

        except OssError as e:
            raise Exception(f'OSS删除失败: {e.code} - {e.message}')

    def list_files(
        self, prefix: str = '', max_keys: int = 100
    ) -> List[Dict[str, Any]]:
        """列举OSS文件.

        Args:
            prefix: 文件前缀（路径）
            max_keys: 最大返回数量

        Returns:
            文件列表
        """
        self._ensure_configured()

        result = self.bucket.list_objects(prefix=prefix, max_keys=max_keys)

        files = []
        for obj in result.object_list:
            file_info = {
                'object_key': obj.key,
                'size': obj.size,
                'last_modified': obj.last_modified,
                'etag': obj.etag,
                'url': (
                    self._get_public_url(obj.key)
                    if self.public_read
                    else self._get_signed_url(obj.key)
                )
            }
            files.append(file_info)

        return files

    def download_file(self, url: str) -> bytes:
        """下载文件（通过URL或object_key）.

        Args:
            url: OSS文件URL或object_key

        Returns:
            文件内容（字节）

        Raises:
            Exception: 下载失败
        """
        import httpx

        # 从URL中提取object_key
        if url.startswith('http'):
            # 检查是否是我们自己的OSS bucket
            is_our_oss = (
                self.bucket_name in url and '.aliyuncs.com/' in url
            )

            if not is_our_oss:
                # 不是我们的OSS，直接通过HTTP下载
                response = httpx.get(url, timeout=60.0)
                response.raise_for_status()
                return response.content

            # 是我们自己的OSS，从OSS链接中提取object_key
            parts = url.split('.aliyuncs.com/')
            if len(parts) > 1:
                object_key = parts[1].split('?')[0]  # 移除查询参数
            else:
                raise Exception(f'无法从URL提取object_key: {url}')
        else:
            # 直接是object_key
            object_key = url

        # 从OSS下载文件
        self._ensure_configured()
        result = self.bucket.get_object(object_key)
        file_content = result.read()

        return file_content

    def get_file_url(
        self, object_key: str, expires: Optional[int] = None
    ) -> str:
        """获取文件访问URL.

        Args:
            object_key: OSS对象键
            expires: 过期时间（秒）

        Returns:
            文件访问URL
        """
        if self.public_read:
            return self._get_public_url(object_key)
        else:
            return self._get_signed_url(object_key, expires)

    def health_check(self) -> bool:
        """健康检查.

        Returns:
            服务是否可用
        """
        if not self._is_configured or not self.bucket:
            return False
        try:
            # 尝试列举文件（限制1个）
            self.bucket.list_objects(max_keys=1)
            return True
        except Exception as e:
            logger.error('OSS health check failed', error=str(e))
            return False


# 创建全局OSS服务实例
oss_service = OSSService()

