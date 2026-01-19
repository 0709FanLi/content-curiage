"""
大模型调用服务
支持DeepSeek、通义千问（阿里云DashScope）和Kimi（月之暗面）
"""

import os
import json
import math
import asyncio
from datetime import datetime
from typing import Optional, Any
import httpx
from openai import OpenAI
import structlog

from src.config.settings import settings
from src.utils.exceptions import ExternalServiceError

logger = structlog.get_logger(__name__)


def retry_decorator(max_attempts: int = 3, wait_multiplier: int = 1, wait_min: int = 2, wait_max: int = 10):
    """
    重试装饰器
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            import asyncio
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


class DeepSeekService:
    """DeepSeek服务类"""

    def __init__(self) -> None:
        # 支持多种环境变量名
        self.api_key = (
            settings.deep_seek or
            os.getenv("DEEP_SEEK") or
            os.getenv("DEEPSEEK_API_KEY") or
            os.getenv("deepseek_api_key") or
            ""
        )
        self.base_url = "https://api.deepseek.com"
        # 思考模式(deepseek-reasoner)需要更长时间,设置为5分钟
        self.timeout = 300

    def _extract_strategy_context(self, inspiration: str) -> tuple[str, str]:
        """
        从灵感内容中提取热点策略上下文
        
        Returns:
            (纯净的灵感内容, 策略上下文)
        """
        import re
        
        # 检测是否包含热点策略标记（以 # 开头的标题）
        if '## 科学支撑 (TRUST)' in inspiration or '## 转化策略 (CONVERSION)' in inspiration:
            # 提取策略内容
            strategy_context = inspiration
            
            # 提取第一行作为纯净的灵感（通常是热点标题）
            lines = inspiration.split('\n')
            clean_inspiration = lines[0].strip('#').strip() if lines else inspiration
            
            return clean_inspiration, strategy_context
        
        return inspiration, ""
    
    @retry_decorator(max_attempts=3, wait_multiplier=1, wait_min=2, wait_max=10)
    async def generate_script(
        self,
        inspiration: str,
        style: str,
        total_duration: int,
        segment_duration: int,
        model: str = "deepseek-chat",
        max_tokens: int = 4000,
        temperature: float = 0.7,
        min_chars_per_sec: float = 3.3,
        max_chars_per_sec: float = 3.6,
        custom_prompt_template: Optional[str] = None,
        vision_guidance: Optional[str] = None,
        enable_search: bool = False,
        style_name: str = "",
        style_description: str = "",
    ) -> str:
        """
        生成脚本
        
        Args:
            inspiration: 创意灵感
            style: 脚本风格
            total_duration: 视频总时长（秒）
            segment_duration: 单个视频时长（秒）
            model: 模型名称
            max_tokens: 最大token数
            temperature: 温度参数
            custom_prompt_template: 自定义提示词模板（可选）
            vision_guidance: 参考图视觉分析结果（可选）
            
        Returns:
            生成的脚本内容
        """
        if not self.api_key:
            raise ExternalServiceError("DeepSeek", "API Key未配置")

        # 计算片段数量（向上取整，确保总时长不少于用户输入）
        segment_count = math.ceil(total_duration / segment_duration)
        
        # 最后一段至少 4 秒：若余量不足，则将总时长向上补齐到可用时长
        last_segment_duration = int(total_duration - segment_duration * (segment_count - 1))
        if last_segment_duration < 4:
            last_segment_duration = 4
            total_duration = int(segment_duration * (segment_count - 1) + last_segment_duration)
        
        # 口播字数控制：按“min_chars_per_sec–max_chars_per_sec 字/秒”口径（由上层按 generation_mode 选择）
        # - 常规段：segment_duration 秒
        # - 最后一段：last_segment_duration 秒（通常 < segment_duration）
        min_cps = float(min_chars_per_sec)
        max_cps = float(max_chars_per_sec)
        content_length_min = int(segment_duration * min_cps)
        content_length_max = int(segment_duration * max_cps)
        last_content_length_min = int(last_segment_duration * min_cps)
        last_content_length_max = int(last_segment_duration * max_cps)
        
        # 提取热点策略上下文
        clean_inspiration, strategy_context = self._extract_strategy_context(inspiration)
        
        # 统一口径：style 默认为“风格描述”，同时提供 style_name/style_description 两种占位符
        resolved_style_description = style_description or style

        # 日期占位符（默认本地时间）
        now = datetime.now()
        current_date_year = str(now.year)
        current_date_month = f"{now.year}年{now.month}月"
        current_date = current_date_month
        
        # 如果提供了自定义提示词模板，使用它；否则使用默认模板
        if custom_prompt_template:
            # 使用安全的模板替换方法，只替换我们定义的变量
            # 避免格式化示例文本中的大括号表达式（如 {segment_duration * 2}）
            import re
            system_prompt = custom_prompt_template
            replacements = {
                'total_duration': str(total_duration),
                'segment_duration': str(segment_duration),
                'segment_count': str(segment_count),
                'style': resolved_style_description,
                'content_length_min': str(content_length_min),
                'content_length_max': str(content_length_max),
                'last_segment_duration': str(last_segment_duration),
                'last_content_length_min': str(last_content_length_min),
                'last_content_length_max': str(last_content_length_max),

                # 智能逻辑判断模块变量
                'is_web_search_enabled': "True" if enable_search else "False",
                'current_date': current_date,
                'current_date_month': current_date_month,
                'current_date_year': current_date_year,
                'strategy_context': strategy_context,
                'style_name': style_name,
                'style_description': resolved_style_description,
            }
            for key, value in replacements.items():
                # 只替换 {key} 格式的变量，不替换 {key * 2} 等表达式
                system_prompt = re.sub(
                    r'\{' + key + r'\}',
                    value,
                    system_prompt
                )

            # 兼容历史自定义模板：有些模板写成 JS 表达式占位符（例如 {Math.floor(segment_duration * 3.3)}）
            # 统一替换为我们计算好的字数范围（3.3–3.6 字/秒口径），避免表达式残留导致指令失效。
            system_prompt = re.sub(
                r"\{Math\.floor\(\s*segment_duration\s*\*\s*[\d.]+\s*\)\}",
                str(content_length_min),
                system_prompt,
            )
            system_prompt = re.sub(
                r"\{Math\.ceil\(\s*segment_duration\s*\*\s*[\d.]+\s*\)\}",
                str(content_length_max),
                system_prompt,
            )

            # 兼容另一类模板：用算式写死（例如 “[ {segment_duration} * 3.3 ] 到 [ {segment_duration} * 3.8 ]”）
            # 为避免与 3.3–3.6 字/秒口径冲突，这里将该类表达式也强制改写为我们计算好的范围。
            system_prompt = re.sub(
                r"\{\s*segment_duration\s*\}\s*\*\s*3\.3",
                str(content_length_min),
                system_prompt,
            )
            system_prompt = re.sub(
                r"\{\s*segment_duration\s*\}\s*\*\s*3\.8",
                str(content_length_max),
                system_prompt,
            )
            system_prompt = re.sub(
                r"\{\s*segment_duration\s*\}\s*\*\s*3\.0",
                str(content_length_min),
                system_prompt,
            )
            system_prompt = re.sub(
                r"\{\s*segment_duration\s*\}\s*\*\s*4\.5",
                str(content_length_max),
                system_prompt,
            )

            system_prompt = (
                f"{system_prompt}\n\n"
                f"补充硬约束：最后一个片段时长为 {last_segment_duration} 秒，"
                f"其【口播文案】字数必须在 {last_content_length_min}-{last_content_length_max} 字之间。"
                )
        else:
            # 使用默认提示词
            system_prompt = f"""你是一个专业的视频脚本创作专家。你的任务是根据用户的创意和风格要求，生成一个结构化的视频脚本。

脚本要求：
1. 视频总时长：{total_duration}秒
2. 单个片段时长：{segment_duration}秒
3. 片段数量：{segment_count}个
4. **脚本风格（必须严格遵守）**：{resolved_style_description}
   - ⚠️ 这是最重要的要求！整个脚本的内容、结构、表达方式都必须完全符合这个风格的特点

脚本格式要求（必须严格遵守）：
1. **片段结构（从 segment_0 开始，不要输出“第0帧/开场画面”段落）**：
   - 必须按照以下字段结构输出，不要省略任何字段：
   
(开始秒数-结束秒数s)
关键帧：(必须包含以下要素的详细描述，至少60字)
  - 主体描述：人物/物体的外观、姿态、表情、服装、动作状态等具体特征
  - 场景环境：室内/室外、空间布局、背景元素、道具细节、环境氛围
  - 光影效果：光线来源、方向、强度、色温、明暗对比、光影层次
  - 构图视角：镜头角度（平视/俯视/仰视/侧面）、景别（特写/中景/全景）、画面重心
  - 色彩风格：主色调、辅助色、配色方案、色彩情绪、整体视觉风格
  - 质感细节：材质、纹理、装饰元素、细节特写
视频：(必须包含以下要素的详细描述，至少50字)
  - 主体动作：具体的动作变化、运动轨迹、动作幅度、速度节奏、肢体语言
  - 镜头运动：推拉摇移跟升降等运镜方式、运动速度、运动轨迹
  - 画面转场：与前一帧的自然衔接方式、过渡效果
  - 视觉节奏：动作的快慢变化、画面的韵律感、张弛有度
  - 情绪氛围：通过动作和画面传达的情感、氛围营造
音色：(全局统一、唯一的、详细的中文声音描述，例如：知性女声，声音温暖，专业且富有磁性)
口播文案：(适配{segment_duration}秒语速，约{content_length_min}-{content_length_max}个汉字)
（补充：最后一个片段时长为{last_segment_duration}秒，口播文案约{last_content_length_min}-{last_content_length_max}个汉字）

3. **时间格式**：
   - 必须严格使用 (0-{segment_duration}s), ({segment_duration}-{segment_duration * 2}s) 等格式。

4. **详细要求**：
   - **关键帧**：必须详尽描述（至少60字），像电影分镜脚本一样精确，让图片生成AI能准确理解每个视觉元素。
   - **视频**：必须详细描述动态过程（至少50字），包含镜头语言、动作细节、情绪表达，让视频生成AI能准确呈现动态效果。
   - **音色**：所有片段必须保持完全一致的音色描述。
   - **口播文案**：严格控制字数，语言风格符合设定的脚本风格。
   - **一致性**：同一角色、物品在所有片段中必须保持完全一致（外观、服装、特征等）。

5. **示例参考**（展示期望的详细程度）：

第0帧：温馨的现代卧室，夜晚时分，柔和的暖黄色灯光从床头精致的台灯中洒下，形成温暖的光晕，一位30岁左右的亚洲女性穿着深蓝色丝质睡衣坐在米色床沿，手持银色智能手机，面部表情专注而平静，眼神聚焦在屏幕上，背景是浅灰色的纹理墙面和深棕色实木床头柜，台灯旁摆放着小型绿色盆栽，柔软的白色床品自然褶皱，整体色调温暖舒适，采用中景构图，略微俯视15度角，营造宁静的居家夜晚氛围。

(0-8s)
关键帧：延续第0帧场景，同一位女性保持坐姿，身体微微前倾，右手拿着手机靠近面部，左手自然放在膝盖上，台灯的暖光在她的侧脸形成柔和的轮廓光，投射出淡淡的阴影，背景中的绿植叶片清晰可见，床品的褶皱细节丰富，整体光线柔和且层次分明，采用中近景构图，平视角度，焦点在人物面部和手机上，背景略微虚化，营造专注的氛围。
视频：镜头从第0帧的静态画面开始，缓缓向前推进（dolly in），从中景过渡到中近景，女性的动作自然流畅，头部轻微下垂约10度看向手机屏幕，右手拇指在屏幕上轻轻滑动，手指动作细腻，台灯的光晕在画面中形成柔和的光斑效果，镜头推进速度平稳（约2秒完成），整体节奏舒缓宁静，营造夜晚放松的居家氛围，画面与第0帧无缝衔接。
音色：知性女声，声音温暖，专业且富有磁性
口播文案：你是否也有睡前刷手机的习惯？其实，这个习惯可能正在影响你的睡眠质量。

请直接输出脚本内容，不要添加任何解释或说明。"""

        # 口播字数强约束（模型自检）：避免出现“爆款短句偏短/硬核科普偏长/半句截断”
        system_prompt = (
            f"{system_prompt}\n\n"
            "【口播字数自检协议（必须执行）】\n"
            "1) 在输出最终脚本前，你必须逐段自检每段【口播文案】字数。\n"
            "2) 字数统计口径：仅统计“汉字 + 数字 + 英文”，不包含标点符号与空格。\n"
            f"3) 常规段口播字数必须在 {content_length_min}-{content_length_max} 字之间；"
            f"最后一段口播字数必须在 {last_content_length_min}-{last_content_length_max} 字之间。\n"
            "4) 若任意一段不满足范围，你必须在生成时自行重写该段口播文案直到满足，再输出最终脚本。\n"
            "5) 严禁输出半句截断；严禁在口播文案中写“xx字/字数/范围”等提示。\n"
            "6) 除口播文案长度调整外，不要改变脚本结构、时间戳格式与字段结构。\n"
        )

        # 如果有视觉分析结果，增强提示词
        if vision_guidance:
            system_prompt = f"""{system_prompt}

---

**参考图视觉分析结果**：

{vision_guidance}

**重要提示**：
1. 整体风格必须与参考图保持一致
2. 第0帧的描述必须严格遵循参考图的视觉特征（场景、人物、色彩、光影、构图等）
3. 后续片段的视觉风格也应与参考图协调统一
4. 如果参考图中有特定的人物、场景或物品，请在脚本中保持一致性"""
        
        # 注意：策略上下文通过 {strategy_context} 占位符注入（不再额外 append），避免和自定义模板冲突

        # 如果有策略上下文，使用纯净的灵感；否则使用原始灵感
        final_inspiration = clean_inspiration if strategy_context else inspiration
        
        user_prompt = f"""请根据以下创意生成视频脚本：

创意：{final_inspiration}

请严格按照上述格式生成脚本，确保包含第0帧和{segment_count}个标准片段。每个片段都必须包含关键帧、视频、音色、口播文案这4个字段。"""

        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ],
            "max_tokens": max_tokens,
            "stream": False
        }
        
        # DeepSeek模型说明:
        # - deepseek-chat: DeepSeek-V3.2-Exp 非思考模式
        # - deepseek-reasoner: DeepSeek-V3.2-Exp 思考模式(推理模型)
        # 思考模式直接使用deepseek-reasoner模型,不需要额外参数
        
        # deepseek-reasoner不支持temperature参数,需要移除
        if "reasoner" in model.lower():
            payload.pop("temperature", None)
            logger.info("Using DeepSeek Reasoner (thinking mode)", model=model)
        else:
            # 非reasoner模型才使用temperature
            payload["temperature"] = temperature

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                result = response.json()
                
                content = result["choices"][0]["message"]["content"].strip()
                logger.info(
                    "DeepSeek script generation completed",
                    model=model,
                    segment_count=segment_count
                )
                return content
        except httpx.HTTPStatusError as e:
            logger.error(
                "DeepSeek API error",
                status_code=e.response.status_code,
                response=e.response.text
            )
            raise ExternalServiceError("DeepSeek", f"API调用失败: {e.response.status_code}")
        except httpx.ReadTimeout:
            logger.error("DeepSeek API timeout", timeout=self.timeout, model=model)
            raise ExternalServiceError("DeepSeek", f"API请求超时(超过{self.timeout}秒),请稍后重试")
        except httpx.TimeoutException:
            logger.error("DeepSeek API timeout", timeout=self.timeout, model=model)
            raise ExternalServiceError("DeepSeek", f"API请求超时(超过{self.timeout}秒),请稍后重试")
        except Exception as e:
            error_msg = str(e) or type(e).__name__
            logger.error("DeepSeek service error", error=error_msg, error_type=type(e).__name__)
            raise ExternalServiceError("DeepSeek", f"服务异常: {error_msg}")

    @retry_decorator(max_attempts=3, wait_multiplier=1, wait_min=2, wait_max=10)
    async def optimize_script(
        self,
        script_content: str,
        creative_description: str,
        model: str = "deepseek-chat",
        max_tokens: int = 4000,
        temperature: float = 0.7,
    ) -> str:
        """
        优化脚本，使用创意描述作为补充
        """
        if not self.api_key:
            raise ExternalServiceError("DeepSeek", "API Key未配置")

        # 构建系统提示词
        system_prompt = """你是一个专业的视频脚本优化专家。你的任务是根据用户提供的创意描述，对现有脚本进行优化和改进。

优化要求：
1. 保持脚本的原有结构和时间格式（片段内的字段结构）
2. 保持音色等固定字段的一致性
3. 根据创意描述，增强关键帧、视频、口播文案的细节描述和表现力
4. 确保优化后的脚本更加生动、具体、有感染力
5. 使用创意描述中的语言风格和表达方式

请直接输出优化后的脚本内容，不要添加任何解释或说明。"""

        user_prompt = f"""请根据以下创意描述优化脚本：

原始脚本：
{script_content}

创意描述（请使用这个描述的语言风格和表达方式来优化脚本）：
{creative_description}

请使用创意描述中的语言风格和表达方式，对原始脚本进行优化。保持脚本的原有格式（包括关键帧、视频、音色、口播文案等字段）。"""

        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ],
            "max_tokens": max_tokens,
            "stream": False
        }
        
        if "reasoner" in model.lower():
            payload.pop("temperature", None)
            logger.info("Using DeepSeek Reasoner (thinking mode) for optimization", model=model)
        else:
            payload["temperature"] = temperature

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                result = response.json()
                
                content = result["choices"][0]["message"]["content"].strip()
                logger.info(
                    "DeepSeek script optimization completed",
                    model=model
                )
                return content
        except Exception as e:
            error_msg = str(e) or type(e).__name__
            logger.error("DeepSeek service error", error=error_msg, error_type=type(e).__name__)
            raise ExternalServiceError("DeepSeek", f"服务异常: {error_msg}")


class QwenService:
    """通义千问服务类（阿里云DashScope）"""

    def __init__(self) -> None:
        self.api_key = settings.dashscope_api_key or os.getenv("DASHSCOPE_API_KEY") or ""
        self.base_url = settings.qwen_base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        # Kimi K2 Thinking 需要更长时间进行深度思考，统一给较长超时避免中断
        # 这里设置为 10 分钟，兼容 kimi-k2-thinking / qwen-* 的长响应场景
        self.timeout = 600
        self.client: Optional[OpenAI] = None
        if self.api_key:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
            )
    
    def _extract_strategy_context(self, inspiration: str) -> tuple[str, str]:
        """
        从灵感内容中提取热点策略上下文
        
        Returns:
            (纯净的灵感内容, 策略上下文)
        """
        import re
        
        # 检测是否包含热点策略标记（以 # 开头的标题）
        if '## 科学支撑 (TRUST)' in inspiration or '## 转化策略 (CONVERSION)' in inspiration:
            # 提取策略内容
            strategy_context = inspiration
            
            # 提取第一行作为纯净的灵感（通常是热点标题）
            lines = inspiration.split('\n')
            clean_inspiration = lines[0].strip('#').strip() if lines else inspiration
            
            return clean_inspiration, strategy_context
        
        return inspiration, ""

    @retry_decorator(max_attempts=3, wait_multiplier=1, wait_min=2, wait_max=10)
    async def generate_script(
        self,
        inspiration: str,
        style: str,
        total_duration: int,
        segment_duration: int,
        model: str = "qwen-plus",
        max_tokens: int = 4000,
        temperature: float = 0.7,
        custom_prompt_template: Optional[str] = None,
        vision_guidance: Optional[str] = None,
        enable_search: bool = False,
        style_name: str = "",
        style_description: str = "",
    ) -> str:
        """
        生成脚本
        """
        if not self.api_key or not self.client:
            raise ExternalServiceError("Qwen", "API Key未配置")

        # 计算片段数量（向上取整，确保总时长不少于用户输入）
        segment_count = math.ceil(total_duration / segment_duration)
        
        # 最后一段至少 4 秒：若余量不足，则将总时长向上补齐到可用时长
        last_segment_duration = int(total_duration - segment_duration * (segment_count - 1))
        if last_segment_duration < 4:
            last_segment_duration = 4
            total_duration = int(segment_duration * (segment_count - 1) + last_segment_duration)
        
        # 口播字数控制：默认按“3.3–3.6 字/秒”口径（一步生成的硬约束在 DeepSeek/Gemini 路径里按 generation_mode 处理）
        content_length_min = int(segment_duration * 3.3)
        content_length_max = int(segment_duration * 3.6)
        last_content_length_min = int(last_segment_duration * 3.3)
        last_content_length_max = int(last_segment_duration * 3.6)
        
        # 提取热点策略上下文
        clean_inspiration, strategy_context = self._extract_strategy_context(inspiration)
        
        resolved_style_description = style_description or style
        now = datetime.now()
        current_date_year = str(now.year)
        current_date_month = f"{now.year}年{now.month}月"
        current_date = current_date_month
        
        if custom_prompt_template:
            import re
            system_prompt = custom_prompt_template
            replacements = {
                'total_duration': str(total_duration),
                'segment_duration': str(segment_duration),
                'segment_count': str(segment_count),
                'style': resolved_style_description,
                'content_length_min': str(content_length_min),
                'content_length_max': str(content_length_max),
                'last_segment_duration': str(last_segment_duration),
                'last_content_length_min': str(last_content_length_min),
                'last_content_length_max': str(last_content_length_max),

                'is_web_search_enabled': "True" if enable_search else "False",
                'current_date': current_date,
                'current_date_month': current_date_month,
                'current_date_year': current_date_year,
                'strategy_context': strategy_context,
                'style_name': style_name,
                'style_description': resolved_style_description,
            }
            for key, value in replacements.items():
                system_prompt = re.sub(
                    r'\{' + key + r'\}',
                    value,
                    system_prompt
                )

            # 兼容历史自定义模板中的 JS 表达式占位符（例如 {Math.floor(segment_duration * 3.3)}）
            system_prompt = re.sub(
                r"\{Math\.floor\(\s*segment_duration\s*\*\s*[\d.]+\s*\)\}",
                str(content_length_min),
                system_prompt,
            )
            system_prompt = re.sub(
                r"\{Math\.ceil\(\s*segment_duration\s*\*\s*[\d.]+\s*\)\}",
                str(content_length_max),
                system_prompt,
            )

            # 兼容另一类模板：用算式写死（例如 “[ {segment_duration} * 3.3 ] 到 [ {segment_duration} * 3.8 ]”）
            system_prompt = re.sub(
                r"\{\s*segment_duration\s*\}\s*\*\s*3\.3",
                str(content_length_min),
                system_prompt,
            )
            system_prompt = re.sub(
                r"\{\s*segment_duration\s*\}\s*\*\s*3\.8",
                str(content_length_max),
                system_prompt,
            )
            system_prompt = re.sub(
                r"\{\s*segment_duration\s*\}\s*\*\s*3\.0",
                str(content_length_min),
                system_prompt,
            )
            system_prompt = re.sub(
                r"\{\s*segment_duration\s*\}\s*\*\s*4\.5",
                str(content_length_max),
                system_prompt,
            )

            # 追加“最后一段口播字数”硬约束：避免 last=4s 仍按 10s 写
            system_prompt = (
                f"{system_prompt}\n\n"
                f"补充硬约束：最后一个片段时长为 {last_segment_duration} 秒，"
                f"其【口播文案】字数必须在 {last_content_length_min}-{last_content_length_max} 字之间。"
                )
        else:
            # 使用默认提示词
            system_prompt = f"""你是一个专业的视频脚本创作专家。你的任务是根据用户的创意和风格要求，生成一个结构化的视频脚本。

脚本要求：
1. 视频总时长：{total_duration}秒
2. 单个片段时长：{segment_duration}秒
3. 片段数量：{segment_count}个
4. **脚本风格（必须严格遵守）**：{resolved_style_description}
   - ⚠️ 这是最重要的要求！整个脚本的内容、结构、表达方式都必须完全符合这个风格的特点

脚本格式要求（必须严格遵守）：
1. **片段结构（从 segment_0 开始，不要输出“第0帧/开场画面”段落）**：
   - 必须按照以下字段结构输出，不要省略任何字段：
   
(开始秒数-结束秒数s)
关键帧：(必须包含以下要素的详细描述，至少60字)
  - 主体描述：人物/物体的外观、姿态、表情、服装、动作状态等具体特征
  - 场景环境：室内/室外、空间布局、背景元素、道具细节、环境氛围
  - 光影效果：光线来源、方向、强度、色温、明暗对比、光影层次
  - 构图视角：镜头角度（平视/俯视/仰视/侧面）、景别（特写/中景/全景）、画面重心
  - 色彩风格：主色调、辅助色、配色方案、色彩情绪、整体视觉风格
  - 质感细节：材质、纹理、装饰元素、细节特写
视频：(必须包含以下要素的详细描述，至少50字)
  - 主体动作：具体的动作变化、运动轨迹、动作幅度、速度节奏、肢体语言
  - 镜头运动：推拉摇移跟升降等运镜方式、运动速度、运动轨迹
  - 画面转场：与前一帧的自然衔接方式、过渡效果
  - 视觉节奏：动作的快慢变化、画面的韵律感、张弛有度
  - 情绪氛围：通过动作和画面传达的情感、氛围营造
音色：(全局统一、唯一的、详细的中文声音描述，例如：知性女声，声音温暖，专业且富有磁性)
口播文案：(适配{segment_duration}秒语速，约{content_length_min}-{content_length_max}个汉字；最后一段{last_segment_duration}秒约{last_content_length_min}-{last_content_length_max}个汉字)

3. **时间格式**：
   - 必须严格使用 (0-{segment_duration}s), ({segment_duration}-{segment_duration * 2}s) 等格式。

4. **详细要求**：
   - **关键帧**：必须详尽描述（至少60字），像电影分镜脚本一样精确，让图片生成AI能准确理解每个视觉元素。
   - **视频**：必须详细描述动态过程（至少50字），包含镜头语言、动作细节、情绪表达，让视频生成AI能准确呈现动态效果。
   - **音色**：所有片段必须保持完全一致的音色描述。
   - **口播文案**：严格控制字数，语言风格符合设定的脚本风格。
   - **一致性**：同一角色、物品在所有片段中必须保持完全一致（外观、服装、特征等）。

5. **示例参考**（展示期望的详细程度）：

第0帧：温馨的现代卧室，夜晚时分，柔和的暖黄色灯光从床头精致的台灯中洒下，形成温暖的光晕，一位30岁左右的亚洲女性穿着深蓝色丝质睡衣坐在米色床沿，手持银色智能手机，面部表情专注而平静，眼神聚焦在屏幕上，背景是浅灰色的纹理墙面和深棕色实木床头柜，台灯旁摆放着小型绿色盆栽，柔软的白色床品自然褶皱，整体色调温暖舒适，采用中景构图，略微俯视15度角，营造宁静的居家夜晚氛围。

(0-8s)
关键帧：延续第0帧场景，同一位女性保持坐姿，身体微微前倾，右手拿着手机靠近面部，左手自然放在膝盖上，台灯的暖光在她的侧脸形成柔和的轮廓光，投射出淡淡的阴影，背景中的绿植叶片清晰可见，床品的褶皱细节丰富，整体光线柔和且层次分明，采用中近景构图，平视角度，焦点在人物面部和手机上，背景略微虚化，营造专注的氛围。
视频：镜头从第0帧的静态画面开始，缓缓向前推进（dolly in），从中景过渡到中近景，女性的动作自然流畅，头部轻微下垂约10度看向手机屏幕，右手拇指在屏幕上轻轻滑动，手指动作细腻，台灯的光晕在画面中形成柔和的光斑效果，镜头推进速度平稳（约2秒完成），整体节奏舒缓宁静，营造夜晚放松的居家氛围，画面与第0帧无缝衔接。
音色：知性女声，声音温暖，专业且富有磁性
口播文案：你是否也有睡前刷手机的习惯？其实，这个习惯可能正在影响你的睡眠质量。

请直接输出脚本内容，不要添加任何解释或说明。"""

        # 口播字数强约束（模型自检）：避免出现“爆款短句偏短/硬核科普偏长/半句截断”
        system_prompt = (
            f"{system_prompt}\n\n"
            "【口播字数自检协议（必须执行）】\n"
            "1) 在输出最终脚本前，你必须逐段自检每段【口播文案】字数。\n"
            "2) 字数统计口径：仅统计“汉字 + 数字 + 英文”，不包含标点符号与空格。\n"
            f"3) 常规段口播字数必须在 {content_length_min}-{content_length_max} 字之间；"
            f"最后一段口播字数必须在 {last_content_length_min}-{last_content_length_max} 字之间。\n"
            "4) 若任意一段不满足范围，你必须在生成时自行重写该段口播文案直到满足，再输出最终脚本。\n"
            "5) 严禁输出半句截断；严禁在口播文案中写“xx字/字数/范围”等提示。\n"
            "6) 除口播文案长度调整外，不要改变脚本结构、时间戳格式与字段结构。\n"
        )

        # 如果有视觉分析结果，增强提示词
        if vision_guidance:
            system_prompt = f"""{system_prompt}

---

**参考图视觉分析结果**：

{vision_guidance}

**重要提示**：
1. 整体风格必须与参考图保持一致
2. 第0帧的描述必须严格遵循参考图的视觉特征（场景、人物、色彩、光影、构图等）
3. 后续片段的视觉风格也应与参考图协调统一
4. 如果参考图中有特定的人物、场景或物品，请在脚本中保持一致性"""
        
        # 注意：策略上下文通过 {strategy_context} 占位符注入（不再额外 append），避免和自定义模板冲突

        # 如果有策略上下文，使用纯净的灵感；否则使用原始灵感
        final_inspiration = clean_inspiration if strategy_context else inspiration

        user_prompt = f"""请根据以下创意生成视频脚本：

创意：{final_inspiration}

请严格按照上述格式生成脚本，确保包含第0帧和{segment_count}个标准片段。每个片段都必须包含关键帧、视频、音色、口播文案这4个字段。"""

        try:
            # 若开启联网搜索：对部分模型做名称映射（百炼文档：Kimi 支持 Moonshot-Kimi-K2-Instruct）
            actual_model = model
            if enable_search and ("kimi" in model.lower() or "moonshot" in model.lower()):
                actual_model = "Moonshot-Kimi-K2-Instruct"

            api_params = {
                "model": actual_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "max_tokens": max_tokens,
                "temperature": temperature
            }
            
            extra_body = {}
            if "max" in model.lower():
                extra_body["enable_thinking"] = True
                logger.info("Qwen Max thinking mode enabled", model=model)
            if enable_search:
                extra_body["enable_search"] = True
            if extra_body:
                api_params["extra_body"] = extra_body
            
            # OpenAI Python SDK 调用为同步方法，放到线程池中避免阻塞 FastAPI/uvicorn 事件循环
            completion = await asyncio.to_thread(
                lambda: self.client.chat.completions.create(**api_params)
            )
            
            content = completion.choices[0].message.content.strip()
            
            # Kimi K2 Thinking模型可能返回思考过程，需要移除 <think> 标签
            if "kimi" in model.lower() or "thinking" in model.lower():
                import re
                # 移除成对的 think 标签及其内容
                content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
                # 移除未闭合的 think 标签及其后续所有内容
                content = re.sub(r'<think>.*', '', content, flags=re.DOTALL)
                # 移除残留的闭合标签及其之前的内容
                content = re.sub(r'.*</think>', '', content, flags=re.DOTALL)
                content = content.strip()
                
                logger.info(
                    "Removed thinking process from Kimi response",
                    model=model,
                    final_content_length=len(content)
                )
            
            logger.info(
                "Qwen script generation completed",
                model=model,
                segment_count=segment_count
            )
            return content
        except Exception as e:
            logger.error("Qwen service error", error=str(e))
            raise ExternalServiceError("Qwen", f"服务异常: {str(e)}")

    @retry_decorator(max_attempts=3, wait_multiplier=1, wait_min=2, wait_max=10)
    async def optimize_script(
        self,
        script_content: str,
        creative_description: str,
        model: str = "qwen-plus",
        max_tokens: int = 4000,
        temperature: float = 0.7,
        enable_search: bool = False,
    ) -> str:
        """
        优化脚本，使用创意描述作为补充
        """
        if not self.api_key or not self.client:
            raise ExternalServiceError("Qwen", "API Key未配置")

        system_prompt = """你是一个专业的视频脚本优化专家。你的任务是根据用户提供的创意描述，对现有脚本进行优化和改进。

优化要求：
1. 保持脚本的原有结构和时间格式（片段内的字段结构）
2. 保持音色等固定字段的一致性
3. 根据创意描述，增强关键帧、视频、口播文案的细节描述和表现力
4. 确保优化后的脚本更加生动、具体、有感染力
5. 使用创意描述中的语言风格和表达方式

请直接输出优化后的脚本内容，不要添加任何解释或说明。"""

        user_prompt = f"""请根据以下创意描述优化脚本：

原始脚本：
{script_content}

创意描述（请使用这个描述的语言风格和表达方式来优化脚本）：
{creative_description}

请使用创意描述中的语言风格和表达方式，对原始脚本进行优化。保持脚本的原有格式（包括关键帧、视频、音色、口播文案等字段）。"""

        try:
            actual_model = model
            if enable_search and ("kimi" in model.lower() or "moonshot" in model.lower()):
                actual_model = "Moonshot-Kimi-K2-Instruct"

            api_params = {
                "model": actual_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "max_tokens": max_tokens,
                "temperature": temperature
            }
            
            extra_body = {}
            if "max" in model.lower():
                extra_body["enable_thinking"] = True
                logger.info("Qwen Max thinking mode enabled for optimization", model=model)
            if enable_search:
                extra_body["enable_search"] = True
            if extra_body:
                api_params["extra_body"] = extra_body
            
            # OpenAI Python SDK 调用为同步方法，放到线程池中避免阻塞 FastAPI/uvicorn 事件循环
            completion = await asyncio.to_thread(
                lambda: self.client.chat.completions.create(**api_params)
            )
            
            content = completion.choices[0].message.content.strip()
            
            # Kimi K2 Thinking模型可能返回思考过程，需要移除 <think> 标签
            if "kimi" in model.lower() or "thinking" in model.lower():
                import re
                # 移除成对的 think 标签及其内容
                content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
                # 移除未闭合的 think 标签及其后续所有内容
                content = re.sub(r'<think>.*', '', content, flags=re.DOTALL)
                # 移除残留的闭合标签及其之前的内容
                content = re.sub(r'.*</think>', '', content, flags=re.DOTALL)
                content = content.strip()
                
                logger.info(
                    "Removed thinking process from Kimi response",
                    model=model,
                    final_content_length=len(content)
                )
            
            logger.info(
                "Qwen script optimization completed",
                model=model
            )
            return content
        except Exception as e:
            logger.error("Qwen service error", error=str(e))
            raise ExternalServiceError("Qwen", f"服务异常: {str(e)}")


class LLMService:
    """LLM服务统一入口"""

    def __init__(self):
        self.deepseek_service = DeepSeekService()
        self.qwen_service = QwenService()
        self.gemini3_service = Gemini3Service()

    async def generate_script(
        self,
        inspiration: str,
        style: str,
        total_duration: int,
        segment_duration: int,
        model: str = "deepseek-chat",
        **kwargs
    ) -> str:
        """
        生成脚本（统一入口）
        """
        enable_search = bool(kwargs.pop("enable_search", False))

        # 开启联网搜索时：仅对已实现透传的模型开放（百炼：DeepSeek/Kimi/Qwen；GRSAI：Gemini），其他模型直接报错避免误导
        if enable_search:
            supports = False
            if (model.startswith("deepseek") or model == "deepseek-chat") and self.qwen_service.api_key:
                supports = True
            elif (model.startswith("kimi") or model.startswith("moonshot")) and self.qwen_service.api_key:
                supports = True
            elif model.startswith("qwen") and self.qwen_service.api_key:
                supports = True
            elif model.startswith("gemini") and self.gemini3_service.api_key:
                supports = True

            if not supports:
                raise ValueError("当前模型不支持联网搜索，或未配置对应 Key（百炼：DASHSCOPE_API_KEY；GRSAI：GRSAI_KEY）")

        if model.startswith("deepseek") or model == "deepseek-chat":
            # DeepSeek 开启联网搜索时，走百炼（DashScope 兼容）并映射到百炼支持的模型码
            if enable_search:
                mapped = "deepseek-v3.2" if model in ("deepseek-chat", "deepseek-v3", "deepseek-v3.2") else "deepseek-r1"
                return await self.qwen_service.generate_script(
                    inspiration=inspiration,
                    style=style,
                    total_duration=total_duration,
                    segment_duration=segment_duration,
                    model=mapped,
                    enable_search=True,
                    **kwargs
                )
            return await self.deepseek_service.generate_script(
                inspiration=inspiration,
                style=style,
                total_duration=total_duration,
                segment_duration=segment_duration,
                model=model,
                **kwargs
            )
        elif model.startswith("qwen") or model == "qwen-plus":
            return await self.qwen_service.generate_script(
                inspiration=inspiration,
                style=style,
                total_duration=total_duration,
                segment_duration=segment_duration,
                model=model,
                enable_search=enable_search,
                **kwargs
            )
        elif model.startswith("kimi") or model.startswith("moonshot"):
            # Kimi模型使用与千问相同的DashScope API
            return await self.qwen_service.generate_script(
                inspiration=inspiration,
                style=style,
                total_duration=total_duration,
                segment_duration=segment_duration,
                model=model,  # 直接传递模型名称（kimi-k2-thinking 或 Moonshot-Kimi-K2-Instruct）
                enable_search=enable_search,
                **kwargs
            )
        elif model.startswith("gemini-3"):
            # 根据模型名称确定思考等级
            thinking_level = "high" if "high" in model else "low"
            return await self.gemini3_service.generate_script(
                inspiration=inspiration,
                style=style,
                total_duration=total_duration,
                segment_duration=segment_duration,
                model="gemini-3-pro",  # 使用 API 支持的实际模型名称
                thinking_level=thinking_level,
                enable_search=enable_search,
                **kwargs
            )
        else:
            raise ValueError(f"不支持的模型: {model}")

    async def optimize_script(
        self,
        script_content: str,
        creative_description: str,
        model: str = "deepseek-chat",
        **kwargs
    ) -> str:
        """
        优化脚本（统一入口）
        """
        enable_search = bool(kwargs.pop("enable_search", False))

        if enable_search:
            supports = False
            if (model.startswith("deepseek") or model == "deepseek-chat") and self.qwen_service.api_key:
                supports = True
            elif (model.startswith("kimi") or model.startswith("moonshot")) and self.qwen_service.api_key:
                supports = True
            elif model.startswith("qwen") and self.qwen_service.api_key:
                supports = True
            elif model.startswith("gemini") and self.gemini3_service.api_key:
                supports = True
            if not supports:
                raise ValueError("当前模型不支持联网搜索，或未配置对应 Key（百炼：DASHSCOPE_API_KEY；GRSAI：GRSAI_KEY）")

        if model.startswith("deepseek") or model == "deepseek-chat":
            if enable_search:
                mapped = "deepseek-v3.2" if model in ("deepseek-chat", "deepseek-v3", "deepseek-v3.2") else "deepseek-r1"
                return await self.qwen_service.optimize_script(
                    script_content=script_content,
                    creative_description=creative_description,
                    model=mapped,
                    enable_search=True,
                    **kwargs
                )
            return await self.deepseek_service.optimize_script(
                script_content=script_content,
                creative_description=creative_description,
                model=model,
                **kwargs
            )
        elif model.startswith("qwen") or model == "qwen-plus":
            return await self.qwen_service.optimize_script(
                script_content=script_content,
                creative_description=creative_description,
                model=model,
                enable_search=enable_search,
                **kwargs
            )
        elif model.startswith("kimi") or model.startswith("moonshot"):
            # Kimi模型使用与千问相同的DashScope API
            return await self.qwen_service.optimize_script(
                script_content=script_content,
                creative_description=creative_description,
                model=model,  # 直接传递模型名称
                enable_search=enable_search,
                **kwargs
            )
        elif model.startswith("gemini"):
            # 提取thinking_level
            thinking_level = "low"  # 默认值
            if "low" in model:
                thinking_level = "low"
            elif "high" in model:
                thinking_level = "high"
            
            return await self.gemini3_service.optimize_script(
                script_content=script_content,
                creative_description=creative_description,
                model="gemini-3-pro",  # 使用 API 支持的实际模型名称
                thinking_level=thinking_level,
                enable_search=enable_search,
                **kwargs
            )
        else:
            raise ValueError(f"不支持的模型: {model}")

    def get_available_models(self) -> list[dict[str, str]]:
        """
        获取可用模型列表
        """
        # 需求：后端只保留脚本模型
        # - deepseek-reasoner（专家硬核科普）
        # - kimi-k2-thinking（爆款网感模式）
        models: list[dict[str, str]] = []
        
        # DeepSeek 推理模型
        if self.deepseek_service.api_key:
            models.append(
                {
                "id": "deepseek-reasoner",
                "name": "专家硬核科普 [讲原理/树立权威]",
                    # 联网搜索能力由百炼（DashScope）提供，需配置 DASHSCOPE_API_KEY
                "supports_web_search": bool(self.qwen_service.api_key),
                }
            )
        
        # Kimi 模型（DashScope / OpenAI compatible）
        if self.qwen_service.api_key or settings.openai_api_key:
            models.append(
                {
                "id": "kimi-k2-thinking",
                "name": "爆款网感模式 [吸粉/流量/高情商]",
                "supports_web_search": bool(self.qwen_service.api_key),
                }
            )
        
        return models


class Gemini3Service:
    """Gemini 3服务类"""

    def __init__(self) -> None:
        # 支持多种环境变量名，优先使用 GRSAI_KEY
        self.api_key = (
            settings.grsai_key or
            os.getenv("GRSAI_KEY") or
            settings.gemini_api_key or
            os.getenv("GEMINI_API_KEY") or
            os.getenv("GEMINI3_API_KEY") or
            ""
        )
        self.base_url = settings.gemini_base_url or "https://grsai.dakka.com.cn"
        self.timeout = settings.gemini_timeout or 60
    
    def _extract_strategy_context(self, inspiration: str) -> tuple[str, str]:
        """
        从灵感内容中提取热点策略上下文
        
        Returns:
            (纯净的灵感内容, 策略上下文)
        """
        import re
        
        # 检测是否包含热点策略标记（以 # 开头的标题）
        if '## 科学支撑 (TRUST)' in inspiration or '## 转化策略 (CONVERSION)' in inspiration:
            # 提取策略内容
            strategy_context = inspiration
            
            # 提取第一行作为纯净的灵感（通常是热点标题）
            lines = inspiration.split('\n')
            clean_inspiration = lines[0].strip('#').strip() if lines else inspiration
            
            return clean_inspiration, strategy_context
        
        return inspiration, ""

    @retry_decorator(max_attempts=3, wait_multiplier=1, wait_min=2, wait_max=10)
    async def generate_script(
        self,
        inspiration: str,
        style: str,
        total_duration: int,
        segment_duration: int,
        model: str = "gemini-3-pro",
        thinking_level: str = "low",
        max_tokens: int = 4000,
        temperature: float = 1.0,
        min_chars_per_sec: float = 3.3,
        max_chars_per_sec: float = 3.6,
        custom_prompt_template: Optional[str] = None,
        vision_guidance: Optional[str] = None,
        enable_search: bool = False,
        style_name: str = "",
        style_description: str = "",
    ) -> str:
        """
        生成脚本
        """
        if not self.api_key:
            raise ExternalServiceError("Gemini 3", "API Key未配置")

        # 计算片段数量（向上取整，确保总时长不少于用户输入）
        segment_count = math.ceil(total_duration / segment_duration)
        
        # 最后一段至少 4 秒：若余量不足，则将总时长向上补齐到可用时长
        last_segment_duration = int(total_duration - segment_duration * (segment_count - 1))
        if last_segment_duration < 4:
            last_segment_duration = 4
            total_duration = int(segment_duration * (segment_count - 1) + last_segment_duration)
        
        # 口播字数控制：按“min_chars_per_sec–max_chars_per_sec 字/秒”口径（由上层按 generation_mode 选择）
        min_cps = float(min_chars_per_sec)
        max_cps = float(max_chars_per_sec)
        content_length_min = int(segment_duration * min_cps)
        content_length_max = int(segment_duration * max_cps)
        last_content_length_min = int(last_segment_duration * min_cps)
        last_content_length_max = int(last_segment_duration * max_cps)
        
        # 提取热点策略上下文
        clean_inspiration, strategy_context = self._extract_strategy_context(inspiration)
        
        resolved_style_description = style_description or style
        now = datetime.now()
        current_date_year = str(now.year)
        current_date_month = f"{now.year}年{now.month}月"
        current_date = current_date_month
        
        if custom_prompt_template:
            import re
            system_prompt = custom_prompt_template
            replacements = {
                'total_duration': str(total_duration),
                'segment_duration': str(segment_duration),
                'segment_count': str(segment_count),
                'style': resolved_style_description,
                'content_length_min': str(content_length_min),
                'content_length_max': str(content_length_max),
                'last_segment_duration': str(last_segment_duration),
                'last_content_length_min': str(last_content_length_min),
                'last_content_length_max': str(last_content_length_max),

                'is_web_search_enabled': "True" if enable_search else "False",
                'current_date': current_date,
                'current_date_month': current_date_month,
                'current_date_year': current_date_year,
                'strategy_context': strategy_context,
                'style_name': style_name,
                'style_description': resolved_style_description,
            }
            for key, value in replacements.items():
                system_prompt = re.sub(
                    r'\{' + key + r'\}',
                    value,
                    system_prompt
                )

            system_prompt = re.sub(
                r"\{Math\.floor\(\s*segment_duration\s*\*\s*[\d.]+\s*\)\}",
                str(content_length_min),
                system_prompt,
            )
            system_prompt = re.sub(
                r"\{Math\.ceil\(\s*segment_duration\s*\*\s*[\d.]+\s*\)\}",
                str(content_length_max),
                system_prompt,
            )

            system_prompt = re.sub(
                r"\{\s*segment_duration\s*\}\s*\*\s*3\.3",
                str(content_length_min),
                system_prompt,
            )
            system_prompt = re.sub(
                r"\{\s*segment_duration\s*\}\s*\*\s*3\.8",
                str(content_length_max),
                system_prompt,
            )
            system_prompt = re.sub(
                r"\{\s*segment_duration\s*\}\s*\*\s*3\.0",
                str(content_length_min),
                system_prompt,
            )
            system_prompt = re.sub(
                r"\{\s*segment_duration\s*\}\s*\*\s*4\.5",
                str(content_length_max),
                system_prompt,
            )

            system_prompt = (
                f"{system_prompt}\n\n"
                f"补充硬约束：最后一个片段时长为 {last_segment_duration} 秒，"
                f"其【口播文案】字数必须在 {last_content_length_min}-{last_content_length_max} 字之间。"
                )
        else:
            # 使用默认提示词
            system_prompt = f"""你是一个专业的视频脚本创作专家。你的任务是根据用户的创意和风格要求，生成一个结构化的视频脚本。

**重要：请务必使用中文回复，所有脚本内容（包括关键帧描述、视频描述、口播文案等）都必须是中文。无论用户输入是什么语言，你都必须用中文生成脚本。**

脚本要求：
1. 视频总时长：{total_duration}秒
2. 单个片段时长：{segment_duration}秒
3. 片段数量：{segment_count}个
4. **脚本风格（必须严格遵守）**：{resolved_style_description}
   - ⚠️ 这是最重要的要求！整个脚本的内容、结构、表达方式都必须完全符合这个风格的特点

脚本格式要求（必须严格遵守）：
1. **片段结构（从 segment_0 开始，不要输出“第0帧/开场画面”段落）**：
   - 必须按照以下字段结构输出，不要省略任何字段：
   
(开始秒数-结束秒数s)
关键帧：(必须包含以下要素的详细描述，至少60字)
  - 主体描述：人物/物体的外观、姿态、表情、服装、动作状态等具体特征
  - 场景环境：室内/室外、空间布局、背景元素、道具细节、环境氛围
  - 光影效果：光线来源、方向、强度、色温、明暗对比、光影层次
  - 构图视角：镜头角度（平视/俯视/仰视/侧面）、景别（特写/中景/全景）、画面重心
  - 色彩风格：主色调、辅助色、配色方案、色彩情绪、整体视觉风格
  - 质感细节：材质、纹理、装饰元素、细节特写
视频：(必须包含以下要素的详细描述，至少50字)
  - 主体动作：具体的动作变化、运动轨迹、动作幅度、速度节奏、肢体语言
  - 镜头运动：推拉摇移跟升降等运镜方式、运动速度、运动轨迹
  - 画面转场：与前一帧的自然衔接方式、过渡效果
  - 视觉节奏：动作的快慢变化、画面的韵律感、张弛有度
  - 情绪氛围：通过动作和画面传达的情感、氛围营造
音色：(全局统一、唯一的、详细的中文声音描述，例如：知性女声，声音温暖，专业且富有磁性)
口播文案：(适配{segment_duration}秒语速，约{content_length_min}-{content_length_max}个汉字；最后一段{last_segment_duration}秒约{last_content_length_min}-{last_content_length_max}个汉字)

3. **时间格式**：
   - 必须严格使用 (0-{segment_duration}s), ({segment_duration}-{segment_duration * 2}s) 等格式。

4. **详细要求**：
   - **关键帧**：必须详尽描述（至少60字），像电影分镜脚本一样精确，让图片生成AI能准确理解每个视觉元素。
   - **视频**：必须详细描述动态过程（至少50字），包含镜头语言、动作细节、情绪表达，让视频生成AI能准确呈现动态效果。
   - **音色**：所有片段必须保持完全一致的音色描述。
   - **口播文案**：严格控制字数，语言风格符合设定的脚本风格。
   - **一致性**：同一角色、物品在所有片段中必须保持完全一致（外观、服装、特征等）。

5. **示例参考**（展示期望的详细程度）：

第0帧：温馨的现代卧室，夜晚时分，柔和的暖黄色灯光从床头精致的台灯中洒下，形成温暖的光晕，一位30岁左右的亚洲女性穿着深蓝色丝质睡衣坐在米色床沿，手持银色智能手机，面部表情专注而平静，眼神聚焦在屏幕上，背景是浅灰色的纹理墙面和深棕色实木床头柜，台灯旁摆放着小型绿色盆栽，柔软的白色床品自然褶皱，整体色调温暖舒适，采用中景构图，略微俯视15度角，营造宁静的居家夜晚氛围。

(0-8s)
关键帧：延续第0帧场景，同一位女性保持坐姿，身体微微前倾，右手拿着手机靠近面部，左手自然放在膝盖上，台灯的暖光在她的侧脸形成柔和的轮廓光，投射出淡淡的阴影，背景中的绿植叶片清晰可见，床品的褶皱细节丰富，整体光线柔和且层次分明，采用中近景构图，平视角度，焦点在人物面部和手机上，背景略微虚化，营造专注的氛围。
视频：镜头从第0帧的静态画面开始，缓缓向前推进（dolly in），从中景过渡到中近景，女性的动作自然流畅，头部轻微下垂约10度看向手机屏幕，右手拇指在屏幕上轻轻滑动，手指动作细腻，台灯的光晕在画面中形成柔和的光斑效果，镜头推进速度平稳（约2秒完成），整体节奏舒缓宁静，营造夜晚放松的居家氛围，画面与第0帧无缝衔接。
音色：知性女声，声音温暖，专业且富有磁性
口播文案：你是否也有睡前刷手机的习惯？其实，这个习惯可能正在影响你的睡眠质量。

请直接输出脚本内容，不要添加任何解释或说明。"""

        # 口播字数强约束（模型自检）：避免出现“爆款短句偏短/硬核科普偏长/半句截断”
        system_prompt = (
            f"{system_prompt}\n\n"
            "【口播字数自检协议（必须执行）】\n"
            "1) 在输出最终脚本前，你必须逐段自检每段【口播文案】字数。\n"
            "2) 字数统计口径：仅统计“汉字 + 数字 + 英文”，不包含标点符号与空格。\n"
            f"3) 常规段口播字数必须在 {content_length_min}-{content_length_max} 字之间；"
            f"最后一段口播字数必须在 {last_content_length_min}-{last_content_length_max} 字之间。\n"
            "4) 若任意一段不满足范围，你必须在生成时自行重写该段口播文案直到满足，再输出最终脚本。\n"
            "5) 严禁输出半句截断；严禁在口播文案中写“xx字/字数/范围”等提示。\n"
            "6) 除口播文案长度调整外，不要改变脚本结构、时间戳格式与字段结构。\n"
        )

        # 如果有视觉分析结果，增强提示词
        if vision_guidance:
            system_prompt = f"""{system_prompt}

---

**参考图视觉分析结果**：

{vision_guidance}

**重要提示**：
1. 整体风格必须与参考图保持一致
2. 第0帧的描述必须严格遵循参考图的视觉特征（场景、人物、色彩、光影、构图等）
3. 后续片段的视觉风格也应与参考图协调统一
4. 如果参考图中有特定的人物、场景或物品，请在脚本中保持一致性
5. 所有内容必须使用中文"""
        
        # 注意：策略上下文通过 {strategy_context} 占位符注入（不再额外 append），避免和自定义模板冲突

        # 如果有策略上下文，使用纯净的灵感；否则使用原始灵感
        final_inspiration = clean_inspiration if strategy_context else inspiration

        user_prompt = f"""请根据以下创意生成视频脚本（请用中文回复）：

创意：{final_inspiration}

请严格按照上述格式生成脚本，确保包含第0帧和{segment_count}个标准片段。每个片段都必须包含关键帧、视频、音色、口播文案这4个字段。所有内容必须使用中文。"""

        # 使用 OpenAI 兼容格式调用 Gemini 3 API
        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,  # 使用传入的 model
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        # 启用联网：Gemini 3 支持通过 tools 调用 Google Search（GRSAI 代理参数与 Gemini API 保持一致）
        # 参考官方文档（Gemini 3 支持 Google 搜索工具）：https://ai.google.dev/gemini-api/docs/gemini-3?hl=zh-cn
        if enable_search:
            payload["tools"] = [{"google_search": {}}]
        
        logger.info(
            "Calling Gemini 3 API",
            model=model,
            thinking_level=thinking_level,
            enable_search=enable_search,
            url=url
        )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                
                result = response.json()
                
                if "choices" in result and len(result["choices"]) > 0:
                    choice = result["choices"][0]
                    if "message" in choice and "content" in choice["message"]:
                        script_content = choice["message"]["content"]
                        
                        import re
                        # 1. 移除成对的 think 标签及其内容
                        script_content = re.sub(r'<think>.*?</think>', '', script_content, flags=re.DOTALL)
                        # 2. 移除未闭合的 think 标签及其后续所有内容（通常是被截断的情况）
                        script_content = re.sub(r'<think>.*', '', script_content, flags=re.DOTALL)
                        # 3. 移除残留的闭合标签及其之前的内容（罕见情况）
                        script_content = re.sub(r'.*</think>', '', script_content, flags=re.DOTALL)
                        
                        script_content = script_content.strip()
                        
                        if not script_content:
                            logger.error("Gemini 3 returned empty content after filtering think tags", raw_content=choice["message"]["content"][:500])
                            raise ExternalServiceError("Gemini 3", "生成的内容无效（过滤思考过程后为空）")
                        
                        logger.info(
                            "Gemini 3 script generated successfully",
                            model=model,
                            thinking_level=thinking_level,
                            content_length=len(script_content)
                        )
                        
                        return script_content
                
                if "code" in result and result["code"] != 0:
                    error_msg = result.get("msg", "未知错误")
                    logger.error("Gemini 3 API returned error", code=result.get("code"), msg=error_msg)
                    raise ExternalServiceError("Gemini 3", f"API返回错误: {error_msg}")
                
                logger.error("Unexpected Gemini 3 response format", response=result)
                raise ExternalServiceError("Gemini 3", f"响应格式异常: {json.dumps(result, ensure_ascii=False)[:200]}")
                
        except Exception as e:
            logger.error("Gemini 3 API error", error=str(e))
            raise ExternalServiceError("Gemini 3", f"API调用失败: {str(e)}")

    @retry_decorator(max_attempts=3, wait_multiplier=1, wait_min=2, wait_max=10)
    async def optimize_script(
        self,
        script_content: str,
        creative_description: str,
        model: str = "gemini-3-pro",
        thinking_level: str = "low",
        max_tokens: int = 4000,
        temperature: float = 1.0,
        enable_search: bool = False,
    ) -> str:
        """
        优化脚本，使用创意描述作为补充
        """
        if not self.api_key:
            raise ExternalServiceError("Gemini 3", "API Key未配置")

        system_prompt = """你是一个专业的视频脚本优化专家。你的任务是根据用户提供的创意描述，优化现有的视频脚本。

优化要求：
1. 保持脚本的原有结构和时间格式（片段内的字段结构）
2. 保持音色等固定字段的一致性
3. 根据创意描述，增强关键帧、视频、口播文案的细节描述和表现力
4. 确保优化后的脚本更加生动、具体、有感染力
5. 使用创意描述中的语言风格和表达方式

请直接输出优化后的脚本内容，不要添加任何解释或说明。"""

        user_prompt = f"""请优化以下视频脚本：

原始脚本：
{script_content}

创意描述：
{creative_description}

请根据创意描述优化脚本，保持原有结构和时间格式。"""

        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        if enable_search:
            payload["tools"] = [{"google_search": {}}]
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                result = response.json()
                
                if "choices" in result and len(result["choices"]) > 0:
                    choice = result["choices"][0]
                    if "message" in choice and "content" in choice["message"]:
                        optimized_content = choice["message"]["content"]
                        
                        import re
                        optimized_content = re.sub(r'<think>.*?</think>', '', optimized_content, flags=re.DOTALL)
                        optimized_content = optimized_content.strip()
                        return optimized_content
                
                raise ExternalServiceError("Gemini 3", "API响应格式错误")
                
        except Exception as e:
            logger.error("Gemini 3 API error", error=str(e))
            raise ExternalServiceError("Gemini 3", f"API调用失败: {str(e)}")

    @staticmethod
    def _strip_think_tags(text: str) -> str:
        """移除 Gemini 返回中的 think 标签内容."""
        import re

        cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
        cleaned = re.sub(r"<think>.*", "", cleaned, flags=re.DOTALL)
        cleaned = re.sub(r".*</think>", "", cleaned, flags=re.DOTALL)
        return cleaned.strip()

    @staticmethod
    def _extract_single_block(text: str) -> str:
        """尽量从模型输出中提取单一规则片段（支持代码块/纯文本两种）。"""
        stripped = text.strip()
        if "```" not in stripped:
            return stripped

        # 提取第一个 fenced code block
        parts = stripped.split("```")
        if len(parts) >= 3:
            block = parts[1]
            # 去掉可选的语言标记行
            lines = block.splitlines()
            if lines and len(lines[0].strip()) <= 20 and " " not in lines[0].strip():
                block = "\n".join(lines[1:])
            return block.strip()
        return stripped

    @retry_decorator(max_attempts=3, wait_multiplier=1, wait_min=2, wait_max=10)
    async def audit_kf_video_rules_snippet(
        self,
        *,
        rules_snippet: str,
        script_text: str,
        model: str = "gemini-3-pro",
        max_tokens: int = 2000,
        temperature: float = 0.2,
    ) -> str:
        """审查并迭代“关键帧/视频规则片段”，降低画面出现中文文字的风险。

        重要约束（按业务要求）：
        - 脚本内容整体仍是中文，这没问题；我们要避免的是“画面里出现中文文字”的描述倾向。
        - 模型只能修改 rules_snippet 中与“画面是否出现中文文字”相关的约束描述。
        - 其它规则（字段结构、60/50 字等）必须保持不变。
        - 禁止输出解释；只输出更新后的 rules_snippet（可用纯文本或一个代码块）。
        """
        if not self.api_key:
            raise ExternalServiceError("Gemini 3", "API Key未配置")

        system_prompt = """你是一名资深的“提示词规则审查/安全编辑器”。你将收到：\n\n1) rules_snippet：用于生成脚本时“关键帧/视频”的规则片段（中文）。\n2) script_text：已经生成出来的脚本（中文），其中关键帧/视频描述可能包含会让画面出现中文文字的倾向性描述。\n\n你的任务：\n- 审查 script_text 中关键帧/视频的描述，判断是否存在“画面会出现中文文字/汉字”的风险（例如：浮现毛笔字、出现中文标语、招牌中文、包装中文、屏幕中文UI、字幕中文等）。\n- 如果有风险：仅修改 rules_snippet 中与“画面出现中文文字”相关的约束描述，使后续生成脚本时避免写出这类“会导致画面出现中文文字”的描述。\n- 如果无风险：原样返回 rules_snippet。\n\n必须遵守（强约束）：\n- 输出必须是“完整的 rules_snippet”，不能只输出其中一部分。\n- 输出必须包含并保留以下两个字段标题（原样保留）：\n  1) 关键帧：\n  2) 视频：\n  任何情况下都不允许删除这两段或改名。\n- 只能改写与“画面是否出现中文文字”相关的句子/条目；不要改字段名、不要改结构、不要改其它内容要求。\n- 不得修改“关键帧至少60字、视频至少50字”的硬性要求。\n- 不得输出任何解释/分析/前后对比；只输出最终的 rules_snippet。\n- 输出必须是中文。\n"""

        user_prompt = f"""rules_snippet（只允许你在其中做极小范围的“去中文文字风险”约束修订）：\n---\n{rules_snippet}\n---\n\nscript_text（用于你判断是否存在“画面出现中文文字”的风险）：\n---\n{script_text}\n---\n\n请输出最终 rules_snippet（不要解释）。"""

        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                result = response.json()

            if "choices" in result and len(result["choices"]) > 0:
                choice = result["choices"][0]
                if "message" in choice and "content" in choice["message"]:
                    content = str(choice["message"]["content"])
                    content = self._strip_think_tags(content)
                    snippet = self._extract_single_block(content)
                    if not snippet:
                        raise ExternalServiceError("Gemini 3", "审查结果为空")
                    # 结构校验：必须包含关键字段，否则触发 retry（避免落库时报错）
                    if "关键帧" not in snippet or "视频" not in snippet:
                        raise ExternalServiceError(
                            "Gemini 3",
                            "审查输出不完整：必须同时包含“关键帧：”与“视频：”两段",
                        )
                    return snippet

            if "code" in result and result["code"] != 0:
                error_msg = result.get("msg", "未知错误")
                raise ExternalServiceError("Gemini 3", f"API返回错误: {error_msg}")

            raise ExternalServiceError("Gemini 3", f"响应格式异常: {json.dumps(result, ensure_ascii=False)[:200]}")
        except Exception as e:
            logger.error("Gemini 3 audit_kf_video_rules_snippet error", error=str(e))
            raise ExternalServiceError("Gemini 3", f"API调用失败: {str(e)}")
