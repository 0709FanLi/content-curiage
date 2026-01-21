"""
文件管理路由
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
import structlog

from src.models.database import get_db
from src.models.tables import User
from src.api.dependencies import get_current_active_user
from src.services.oss_service import oss_service

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get('/proxy')
async def proxy_file(
    request: Request,
    url: str = Query(..., description='文件URL'),
    download: bool = Query(False, description='是否强制下载（默认内联显示）'),
):
    """
    代理下载文件，解决CORS问题和强制下载
    
    Args:
        url: 要下载的文件URL
        
    Returns:
        文件流
    """
    try:
        import os
        from urllib.parse import urlparse, unquote

        parsed_url = urlparse(url)
        filename = os.path.basename(unquote(parsed_url.path)) or 'download'

        # 透传 Range 头（浏览器媒体预加载/拖动进度条会用到）
        upstream_headers: dict[str, str] = {}
        range_header = request.headers.get('range')
        if range_header:
            upstream_headers['Range'] = range_header

        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            upstream_resp = await client.get(url, headers=upstream_headers)

        # httpx 2xx/206 都算正常；其他状态抛错
        if upstream_resp.status_code >= 400:
            upstream_resp.raise_for_status()

        content_type = upstream_resp.headers.get('content-type', 'application/octet-stream')

        # 关键头：尽量让浏览器把它当作“媒体资源”而不是附件下载
        disposition = 'attachment' if download else 'inline'
        headers: dict[str, str] = {
            'Access-Control-Allow-Origin': '*',
            'Content-Disposition': f'{disposition}; filename=\"{filename}\"',
            'Cache-Control': 'no-cache',
        }

        # 透传与媒体相关的关键头（若有）
        for h in ('content-length', 'accept-ranges', 'content-range'):
            v = upstream_resp.headers.get(h)
            if v:
                headers[h.title()] = v

        return StreamingResponse(
            iter([upstream_resp.content]),
            media_type=content_type,
            headers=headers,
            status_code=upstream_resp.status_code,
        )
    except httpx.HTTPError as e:
        logger.error('Proxy download failed', url=url, error=str(e))
        raise HTTPException(status_code=500, detail=f'下载文件失败: {str(e)}')


@router.post('/upload-reference-images')
async def upload_reference_images(
    files: List[UploadFile] = File(..., description="参考图片文件列表，最多5张"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    批量上传参考图片到OSS
    
    Args:
        files: 上传的图片文件列表（最多5张）
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        上传结果，包含每个图片的URL
        
    Raises:
        HTTPException: 上传失败或文件数量超限
    """
    try:
        # 验证文件数量
        if len(files) > 5:
            raise HTTPException(
                status_code=400,
                detail='最多只能上传5张参考图'
            )
        
        if len(files) == 0:
            raise HTTPException(
                status_code=400,
                detail='请至少上传1张参考图'
            )
        
        # 验证文件类型
        allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
        uploaded_urls = []
        
        for idx, file in enumerate(files):
            # 读取文件内容
            file_data = await file.read()
            
            # 验证文件类型
            content_type = file.content_type or 'image/jpeg'
            if content_type not in allowed_types:
                raise HTTPException(
                    status_code=400,
                    detail=f'文件 {file.filename} 类型不支持，仅支持 JPEG、PNG、WEBP 格式'
                )
            
            # 上传到OSS
            try:
                from io import BytesIO
                file_stream = BytesIO(file_data)
                
                upload_result = oss_service.upload_file(
                    file_data=file_stream,
                    filename=file.filename or f'reference_{idx}.jpg',
                    category='reference_images',
                    content_type=content_type
                )
                
                uploaded_urls.append({
                    'filename': file.filename,
                    'url': upload_result['url'],
                    'size': upload_result['size']
                })
                
                logger.info(
                    '参考图上传成功',
                    user_id=current_user.id,
                    filename=file.filename,
                    url=upload_result['url']
                )
            except Exception as e:
                logger.error(
                    '参考图上传失败',
                    user_id=current_user.id,
                    filename=file.filename,
                    error=str(e)
                )
                raise HTTPException(
                    status_code=500,
                    detail=f'上传文件 {file.filename} 失败: {str(e)}'
                )
        
        return {
            'code': 200,
            'message': 'success',
            'data': {
                'images': uploaded_urls,
                'count': len(uploaded_urls)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error('批量上传参考图失败', error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f'批量上传失败: {str(e)}'
        )


@router.post('/upload-assets')
async def upload_assets(
    files: List[UploadFile] = File(..., description="素材文件列表（图片/视频），最多5个"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """上传图片/视频素材到 OSS（用于 Medeo 等场景）。"""
    try:
        if len(files) > 5:
            raise HTTPException(status_code=400, detail='最多只能上传5个素材')
        if len(files) == 0:
            raise HTTPException(status_code=400, detail='请至少上传1个素材')

        allowed_image = {'image/jpeg', 'image/jpg', 'image/png', 'image/webp', 'image/gif'}
        allowed_video = {'video/mp4', 'video/webm', 'video/quicktime', 'video/mov'}
        uploaded = []

        for idx, file in enumerate(files):
            file_data = await file.read()
            content_type = (file.content_type or '').lower() or 'application/octet-stream'

            if content_type not in allowed_image and content_type not in allowed_video:
                raise HTTPException(
                    status_code=400,
                    detail=f'文件 {file.filename} 类型不支持，仅支持常见图片/视频格式'
                )

            try:
                from io import BytesIO

                upload_result = oss_service.upload_file(
                    file_data=BytesIO(file_data),
                    filename=file.filename or f'asset_{idx}',
                    category='medeo_assets',
                    content_type=content_type,
                )

                uploaded.append({
                    'filename': file.filename,
                    'url': upload_result['url'],
                    'size': upload_result['size'],
                    'content_type': content_type,
                })

                logger.info(
                    '素材上传成功',
                    user_id=current_user.id,
                    filename=file.filename,
                    url=upload_result['url'],
                    content_type=content_type,
                )
            except Exception as e:
                logger.error(
                    '素材上传失败',
                    user_id=current_user.id,
                    filename=file.filename,
                    error=str(e),
                    exc_info=True,
                )
                raise HTTPException(status_code=500, detail=f'上传文件 {file.filename} 失败: {str(e)}')

        return {'code': 200, 'message': 'success', 'data': {'files': uploaded, 'count': len(uploaded)}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error('上传素材失败', error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f'上传素材失败: {str(e)}')
