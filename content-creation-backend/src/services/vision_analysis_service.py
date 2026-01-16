"""
视觉分析服务 - 使用阿里云通义千问VL多模态大模型分析参考图
"""

import asyncio
from typing import List, Dict, Optional
import structlog
from dashscope import MultiModalConversation
import dashscope

from ..config.settings import settings
from ..utils.exceptions import ExternalServiceError

logger = structlog.get_logger(__name__)


def retry_decorator(max_attempts: int = 3, wait_multiplier: int = 1, wait_min: int = 2, wait_max: int = 10):
    """
    重试装饰器
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            attempt = 0
            while attempt < max_attempts:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    attempt += 1
                    if attempt >= max_attempts:
                        logger.error(
                            "Max retry attempts reached",
                            function=func.__name__,
                            error=str(e),
                            attempts=attempt
                        )
                        raise
                    
                    wait_time = min(wait_min * (wait_multiplier ** (attempt - 1)), wait_max)
                    logger.warning(
                        "Retrying function",
                        function=func.__name__,
                        attempt=attempt,
                        wait_time=wait_time,
                        error=str(e)
                    )
                    await asyncio.sleep(wait_time)
            return None
        return wrapper
    return decorator


class VisionAnalysisService:
    """视觉分析服务类 - 使用通义千问VL分析图片"""
    
    def __init__(self) -> None:
        """初始化服务"""
        self.api_key = settings.dashscope_api_key
        self.model = "qwen-vl-max"  # 通义千问VL多模态模型
        
        if not self.api_key:
            logger.warning("DashScope API key not configured, vision analysis will be disabled")
    
    @retry_decorator(max_attempts=3, wait_multiplier=1, wait_min=2, wait_max=10)
    async def analyze_single_image(
        self,
        image_url: str,
        analysis_prompt: Optional[str] = None
    ) -> Dict[str, str]:
        """
        分析单张图片的视觉特征
        
        Args:
            image_url: 图片URL
            analysis_prompt: 自定义分析提示词（可选）
            
        Returns:
            包含分析结果的字典
            
        Raises:
            ExternalServiceError: API调用失败
        """
        if not self.api_key:
            raise ExternalServiceError("DashScope", "API Key未配置")
        
        # 默认分析提示词
        if not analysis_prompt:
            analysis_prompt = """请详细分析这张图片的以下视觉特征：

1. 整体风格：写实/动画/插画/其他，艺术风格特点
2. 场景描述：室内/室外，具体环境，空间布局，道具细节
3. 人物特征：如有人物，描述外观、年龄、性别、服装、姿态、表情、动作
4. 色彩方案：主色调、辅助色、整体配色特点、色彩情绪
5. 光影效果：光源类型、方向、强度、明暗对比、色温
6. 构图特点：镜头角度（平视/俯视/仰视）、景别（特写/中景/全景）、画面重心
7. 情绪氛围：画面传达的情感和氛围

请用结构化的方式输出，每个维度单独一段，格式如下：
【整体风格】...
【场景描述】...
【人物特征】...
【色彩方案】...
【光影效果】...
【构图特点】...
【情绪氛围】..."""
        
        try:
            logger.info(
                "Analyzing image with Qwen-VL",
                image_url=image_url[:100],
                model=self.model
            )
            
            # 构建消息
            messages = [{
                'role': 'user',
                'content': [
                    {'image': image_url},
                    {'text': analysis_prompt}
                ]
            }]
            
            # 调用通义千问VL API（同步调用，在executor中运行）
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: MultiModalConversation.call(
                    model=self.model,
                    messages=messages,
                    api_key=self.api_key
                )
            )
            
            # 检查响应状态
            if response.status_code != 200:
                error_msg = f"API返回错误: {response.code} - {response.message}"
                logger.error(
                    "Qwen-VL API error",
                    status_code=response.status_code,
                    code=response.code,
                    message=response.message
                )
                raise ExternalServiceError("Qwen-VL", error_msg)
            
            # 提取分析结果
            analysis_text = response.output.choices[0].message.content
            
            logger.info(
                "Image analysis completed",
                image_url=image_url[:100],
                result_length=len(analysis_text)
            )
            
            return {
                "image_url": image_url,
                "analysis": analysis_text,
                "model": self.model
            }
            
        except Exception as e:
            error_msg = str(e) or type(e).__name__
            logger.error(
                "Vision analysis failed",
                error=error_msg,
                error_type=type(e).__name__,
                image_url=image_url[:100]
            )
            raise ExternalServiceError("Qwen-VL", f"图片分析失败: {error_msg}")
    
    async def analyze_images(
        self,
        image_urls: List[str],
        analysis_prompt: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """
        分析多张图片
        
        Args:
            image_urls: 图片URL列表
            analysis_prompt: 自定义分析提示词（可选）
            
        Returns:
            分析结果列表
        """
        if not image_urls:
            logger.warning("No images to analyze")
            return []
        
        logger.info(
            "Starting batch image analysis",
            image_count=len(image_urls)
        )
        
        # 并发分析所有图片
        tasks = [
            self.analyze_single_image(url, analysis_prompt)
            for url in image_urls
        ]
        
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 过滤掉失败的结果
            successful_results = []
            failed_count = 0
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(
                        "Image analysis failed",
                        image_index=i,
                        image_url=image_urls[i][:100],
                        error=str(result)
                    )
                    failed_count += 1
                else:
                    successful_results.append(result)
            
            logger.info(
                "Batch image analysis completed",
                total=len(image_urls),
                successful=len(successful_results),
                failed=failed_count
            )
            
            return successful_results
            
        except Exception as e:
            logger.error(
                "Batch image analysis error",
                error=str(e),
                error_type=type(e).__name__
            )
            raise
    
    async def merge_analysis_results(
        self,
        analyses: List[Dict[str, str]]
    ) -> str:
        """
        合并多张图片的分析结果，生成统一的风格指导
        
        Args:
            analyses: 图片分析结果列表
            
        Returns:
            合并后的风格指导文本
        """
        if not analyses:
            return ""
        
        if len(analyses) == 1:
            # 只有一张图片，直接返回分析结果
            return f"""参考图视觉分析：

{analyses[0]['analysis']}"""
        
        # 多张图片，需要合并
        merged_text = f"参考图视觉分析（共{len(analyses)}张图片）：\n\n"
        
        for i, analysis in enumerate(analyses, 1):
            merged_text += f"【参考图{i}】\n{analysis['analysis']}\n\n"
        
        # 添加综合指导
        merged_text += """【综合风格指导】
请在生成脚本时综合考虑以上所有参考图的视觉特征：
1. 提取共同的风格元素（如色调、氛围、构图风格等）
2. 注意不同参考图之间的差异和变化
3. 第0帧的描述应该综合参考所有图片的特征
4. 确保整体视觉风格的连贯性和统一性"""
        
        logger.info(
            "Analysis results merged",
            image_count=len(analyses),
            merged_length=len(merged_text)
        )
        
        return merged_text
    
    async def analyze_and_merge(
        self,
        image_urls: List[str],
        analysis_prompt: Optional[str] = None
    ) -> Optional[str]:
        """
        分析图片并合并结果的便捷方法
        
        Args:
            image_urls: 图片URL列表
            analysis_prompt: 自定义分析提示词（可选）
            
        Returns:
            合并后的风格指导文本，如果分析失败返回None
        """
        try:
            if not image_urls:
                return None
            
            # 分析图片
            analyses = await self.analyze_images(image_urls, analysis_prompt)
            
            if not analyses:
                logger.warning("All image analyses failed")
                return None
            
            # 合并结果
            merged_guidance = await self.merge_analysis_results(analyses)
            
            return merged_guidance
            
        except Exception as e:
            logger.error(
                "Vision analysis and merge failed",
                error=str(e),
                error_type=type(e).__name__
            )
            # 返回None而不是抛出异常，允许脚本生成继续进行
            return None
