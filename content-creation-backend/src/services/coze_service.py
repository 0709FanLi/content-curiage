"""
Coze API 调用服务
用于获取热点情报和详情分析
"""

import json
import re
import asyncio
from typing import Optional, Dict, Any, List
import httpx
import structlog

from src.config.settings import settings
from src.utils.exceptions import ExternalServiceError
from src.models.schemas.hotspot import (
    HotspotListResponse,
    HotspotItem,
    HotspotDetailResponse,
    HotspotDetailSection
)

logger = structlog.get_logger(__name__)


class CozeService:
    """Coze API 服务类"""

    def __init__(self) -> None:
        self.api_key = settings.coze_api_key
        self.base_url = settings.coze_base_url
        self.workflow_id = settings.coze_workflow_id
        self.bot_id = settings.coze_bot_id
        self.timeout = settings.coze_timeout
        self.poll_interval = settings.coze_poll_interval
        self.max_poll_time = settings.coze_max_poll_time

    def _check_config(self) -> None:
        """检查配置是否完整（延迟到真正调用时才检查）"""
        if not self.api_key:
            raise ValueError("COZE_API_KEY 必须在环境变量中设置，请在 .env 文件中配置")
        if not self.bot_id:
            raise ValueError("COZE_BOT_ID 必须在环境变量中设置，请在 .env 文件中配置")

    async def get_hotspots(self) -> HotspotListResponse:
        """
        获取热点列表
        调用 Coze Workflow API (流式接口)
        """
        self._check_config()  # 检查配置
        logger.info("开始获取热点列表", workflow_id=self.workflow_id)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        async def _fetch_hotspots_once() -> HotspotListResponse:
            """执行一次热点拉取（不包含重试）。"""
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/v1/workflow/stream_run",
                    headers=headers,
                    json={
                        "workflow_id": self.workflow_id,
                        "parameters": {}
                    }
                ) as response:
                    response.raise_for_status()

                    hotspot_data: Optional[Dict[str, Any]] = None
                    async for line in response.aiter_lines():
                        if not line or not line.strip():
                            continue

                        if not line.startswith("data:"):
                            continue

                        data_str = line[5:].strip()
                        if not data_str or data_str == "{}":
                            continue

                        try:
                            event_data = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        content = event_data.get("content")
                        if not content or not isinstance(content, str):
                            continue

                        # content 是 JSON 字符串，需要再次解析；失败则按纯文本兜底
                        markdown_content: Optional[str] = None
                        try:
                            content_obj = json.loads(content)
                            markdown_content = content_obj.get("data")
                        except json.JSONDecodeError:
                            markdown_content = content

                        if not markdown_content or not str(markdown_content).strip():
                            logger.warning("热点内容为空，继续等待下一个事件")
                            continue

                        logger.info("找到热点数据", content_preview=str(markdown_content)[:200])
                        hotspot_data = self._parse_hotspot_content(str(markdown_content))
                        break

                    if not hotspot_data:
                        raise ExternalServiceError(
                            "Coze",
                            "未能从 Workflow 响应中提取热点数据",
                        )

                    logger.info(
                        "成功获取热点列表",
                        hotspot_count=len(hotspot_data.get("hotspots", []))
                    )
                    return HotspotListResponse(**hotspot_data)

        # 失败自动重试 3 次（短退避）
        last_error: Optional[Exception] = None
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                if attempt > 1:
                    backoff_seconds = 1 + (attempt - 2) * 2  # 1s, 3s
                    logger.warning(
                        "获取热点列表失败，准备重试",
                        attempt=attempt,
                        max_attempts=max_attempts,
                        backoff_seconds=backoff_seconds,
                    )
                    await asyncio.sleep(backoff_seconds)

                return await _fetch_hotspots_once()

            except ValueError as e:
                # 解析失败（包括 JSONDecodeError 被包装成 ValueError）
                last_error = e
                logger.warning(
                    "解析热点内容失败",
                    attempt=attempt,
                    max_attempts=max_attempts,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                continue
            except (httpx.HTTPStatusError, httpx.RequestError, ExternalServiceError) as e:
                # 外部服务/网络/协议失败
                last_error = e
                logger.warning(
                    "获取热点列表外部失败",
                    attempt=attempt,
                    max_attempts=max_attempts,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                continue

        # 重试耗尽
        assert last_error is not None
        logger.error(
            "获取热点列表重试耗尽",
            attempts=max_attempts,
            error=str(last_error),
            error_type=type(last_error).__name__,
        )
        raise ExternalServiceError(
            "Coze",
            f"获取热点列表失败: {str(last_error)}",
        )

    def _parse_hotspot_content(self, content: str) -> Dict[str, Any]:
        """
        解析热点内容
        从 Markdown 内容中提取 JSON 数据
        """
        try:
            # content 是 Markdown 格式，包含 JSON 代码块
            logger.debug("开始解析热点内容", content_length=len(content))
            
            # 检查内容是否为空
            if not content or not content.strip():
                logger.error("热点内容为空")
                raise ValueError("热点内容为空")
            
            # 查找 JSON 代码块
            json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if json_match:
                json_str = json_match.group(1).strip()
                logger.debug("找到 JSON 代码块", json_length=len(json_str))
                if not json_str:
                    logger.error("JSON 代码块为空")
                    raise ValueError("JSON 代码块为空")
                parsed_data = json.loads(json_str)
            else:
                # 尝试直接解析整个内容
                logger.debug("未找到 JSON 代码块，尝试直接解析")
                content_stripped = content.strip()
                if not content_stripped:
                    logger.error("内容为空，无法解析")
                    raise ValueError("内容为空")
                parsed_data = json.loads(content_stripped)

            # 验证数据结构
            if not isinstance(parsed_data, dict):
                raise ValueError("解析结果不是字典")

            # 提取热点列表
            hotspots_raw = parsed_data.get("hotspots", [])
            if not hotspots_raw:
                logger.warning("解析的数据中没有 hotspots 字段", parsed_keys=list(parsed_data.keys()))
            
            hotspots = []
            for item in hotspots_raw:
                hotspots.append({
                    "title": item.get("title", ""),
                    "track": item.get("track", ""),
                    "source": item.get("source", ""),
                    "angle": item.get("angle", "")
                })

            result = {
                "daily_summary": parsed_data.get("daily_summary", ""),
                "hotspots": hotspots
            }
            
            logger.info("成功解析热点内容", hotspot_count=len(hotspots))
            return result

        except Exception as e:
            logger.error("解析热点内容失败", error=str(e), error_type=type(e).__name__, 
                        content_preview=content[:500] if content else "")
            raise ValueError(f"解析热点内容失败: {str(e)}")

    async def get_hotspot_detail(self, title: str) -> HotspotDetailResponse:
        """
        获取热点详情
        调用 Coze Chat API (流式接口)
        """
        self._check_config()  # 检查配置
        logger.info("开始获取热点详情", title=title)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient(timeout=self.max_poll_time) as client:
                # 使用流式接口获取完整内容
                detail_content = ""
                
                # 构造明确的提示词，要求返回特定格式
                prompt = f"""请针对以下热点标题，提供详细的内容策略分析：

热点标题：{title}

请按照以下格式返回分析结果：

## 🔬 科学支撑 (TRUST)
[请提供该热点背后的科学依据、研究数据、专家观点等可信度支撑]

## 💡 转化策略 (CONVERSION)
[请提供如何将该热点转化为吸引用户的内容策略、切入角度、情绪共鸣点等]

## 📋 建议结构 (STRUCTURE)
[请提供具体的内容结构建议、脚本框架、关键要素等]"""
                
                async with client.stream(
                    "POST",
                    f"{self.base_url}/v3/chat",
                    headers=headers,
                    json={
                        "bot_id": self.bot_id,
                        "user_id": "user_hotspot_detail",
                        "stream": True,  # 使用流式模式
                        "auto_save_history": False,
                        "additional_messages": [
                            {
                                "role": "user",
                                "content": prompt,
                                "content_type": "text"
                            }
                        ]
                    }
                ) as response:
                    response.raise_for_status()
                    
                    # 解析流式响应
                    current_event = None
                    line_count = 0
                    delta_count = 0
                    
                    logger.info("开始接收流式响应", title=title)
                    
                    async for line in response.aiter_lines():
                        line_count += 1
                        if not line or not line.strip():
                            continue
                        
                        # 处理 event 行
                        if line.startswith("event:"):
                            current_event = line[6:].strip()
                            if line_count <= 5:  # 记录前5个事件
                                logger.info("收到事件", event_type=current_event, line_num=line_count)
                            continue
                            
                        # 处理 data 行
                        if line.startswith("data:"):
                            data_str = line[5:].strip()
                            if not data_str or data_str == "[DONE]":
                                continue
                            
                            try:
                                data = json.loads(data_str)
                                
                                # 处理 message delta 事件
                                if current_event == "conversation.message.delta":
                                    # Coze API 的 delta 数据可能在不同的字段中
                                    content = data.get("content", "")
                                    if not content:
                                        # 尝试从 message 字段中获取
                                        message = data.get("message", {})
                                        content = message.get("content", "")
                                    if not content:
                                        # 尝试从 delta 字段中获取
                                        delta = data.get("delta", "")
                                        if delta:
                                            content = delta
                                    
                                    if content:
                                        delta_count += 1
                                        detail_content += content
                                        if delta_count <= 5:  # 记录前5个 delta
                                            logger.info("收到内容片段", delta_num=delta_count, content=content[:50])
                                    else:
                                        # 记录完整的 data 结构以便调试
                                        if delta_count == 0:  # 只记录第一次
                                            logger.warning("Delta 事件中未找到内容", data_keys=list(data.keys()), data_preview=str(data)[:200])
                                
                                # 处理对话完成事件
                                elif current_event == "conversation.chat.completed":
                                    logger.info("对话完成", content_length=len(detail_content), total_lines=line_count, delta_count=delta_count)
                                    break
                                    
                                # 处理对话失败事件
                                elif current_event == "conversation.chat.failed":
                                    error_msg = data.get("last_error", {}).get("msg", "未知错误")
                                    logger.error("对话失败", error=error_msg)
                                    raise ExternalServiceError(
                                        "Coze",
                                        f"对话失败: {error_msg}",
                                    )
                                    
                            except json.JSONDecodeError as e:
                                logger.warning("解析 JSON 失败", line_preview=data_str[:100], error_msg=str(e))
                                continue
                
                logger.info("流式响应结束", content_length=len(detail_content), total_lines=line_count, delta_count=delta_count)
                
                if not detail_content:
                    logger.error("未能获取到详情内容")
                    raise ExternalServiceError("Coze", "未能获取热点详情")
                
                logger.info("成功获取热点详情内容", title=title, content_length=len(detail_content))
                
                # 解析详情内容
                detail_response = self._parse_detail_content(title, detail_content)
                return detail_response

        except httpx.HTTPStatusError as e:
            logger.error("Coze Chat API 调用失败", status_code=e.response.status_code, error=str(e))
            raise ExternalServiceError(
                "Coze",
                f"获取热点详情失败: {e.response.status_code}",
            )
        except httpx.RequestError as e:
            logger.error("Coze Chat API 请求错误", error=str(e))
            raise ExternalServiceError("Coze", f"请求热点详情失败: {str(e)}")
        except Exception as e:
            logger.error("获取热点详情异常", error=str(e), error_type=type(e).__name__)
            raise ExternalServiceError("Coze", f"获取热点详情失败: {str(e)}")

    async def _poll_chat_result(
        self,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        conversation_id: str,
        chat_id: str
    ) -> str:
        """
        轮询获取对话结果
        """
        start_time = asyncio.get_event_loop().time()
        poll_count = 0
        last_content = ""

        while True:
            poll_count += 1
            elapsed = asyncio.get_event_loop().time() - start_time

            if elapsed > self.max_poll_time:
                logger.error("轮询超时", elapsed=elapsed, max_poll_time=self.max_poll_time)
                # 如果有部分内容，返回部分内容而不是抛出异常
                if last_content:
                    logger.warning("轮询超时但有部分内容，返回部分内容", content_length=len(last_content))
                    return last_content
                raise ExternalServiceError("Coze", "获取热点详情超时")

            # 查询对话消息列表
            messages_response = await client.get(
                f"{self.base_url}/v1/conversation/message/list",
                headers=headers,
                params={
                    "conversation_id": conversation_id,
                    "chat_id": chat_id
                }
            )
            messages_response.raise_for_status()
            messages_data = messages_response.json()

            # 检查对话状态
            data = messages_data.get("data", [])
            if not data:
                logger.debug("消息列表为空，继续轮询", poll_count=poll_count, elapsed=f"{elapsed:.1f}s")
                await asyncio.sleep(self.poll_interval)
                continue

            # 查找 assistant 的回复
            for message in data:
                if message.get("role") == "assistant" and message.get("type") == "answer":
                    content = message.get("content", "")
                    if content:
                        last_content = content
                        # 检查内容是否完整（包含三个部分的标题）
                        has_trust = "科学支撑" in content or "TRUST" in content
                        has_conversion = "转化策略" in content or "CONVERSION" in content
                        has_structure = "建议结构" in content or "STRUCTURE" in content
                        
                        if has_trust and has_conversion and has_structure:
                            logger.info("找到完整 assistant 回复", 
                                      poll_count=poll_count, 
                                      elapsed=f"{elapsed:.1f}s",
                                      content_length=len(content))
                            return content
                        else:
                            logger.debug("内容不完整，继续轮询", 
                                       poll_count=poll_count,
                                       has_trust=has_trust,
                                       has_conversion=has_conversion,
                                       has_structure=has_structure,
                                       content_preview=content[:100])

            # 检查是否有错误消息
            for message in data:
                if message.get("type") == "error":
                    error_msg = message.get("content", "未知错误")
                    logger.error("对话返回错误", error=error_msg)
                    raise ExternalServiceError("Coze", f"对话失败: {error_msg}")

            logger.debug("继续轮询", poll_count=poll_count, elapsed=f"{elapsed:.1f}s")
            await asyncio.sleep(self.poll_interval)

    def _parse_detail_content(self, title: str, content: str) -> HotspotDetailResponse:
        """
        解析详情内容
        提取"科学支撑"、"转化策略"、"建议结构"三个部分
        """
        try:
            # 初始化三个部分
            trust_section = {"title": "科学支撑 (TRUST)", "content": "", "items": []}
            conversion_section = {"title": "转化策略 (CONVERSION)", "content": "", "items": []}
            structure_section = {"title": "建议结构 (STRUCTURE)", "content": "", "items": []}

            # 使用正则表达式提取各部分内容
            # 查找科学支撑部分（可能包含 emoji 和 ##）
            trust_match = re.search(
                r'##?\s*[\U0001F300-\U0001F9FF]?\s*科学支撑.*?\(TRUST\)\s*\n(.*?)(?=##?\s*[\U0001F300-\U0001F9FF]?\s*转化策略|$)',
                content,
                re.DOTALL | re.IGNORECASE
            )
            if trust_match:
                trust_content = trust_match.group(1).strip()
                # 移除底部重复的要点列表
                trust_content = self._remove_duplicate_summary(trust_content)
                # 额外清理：移除底部所有独立的列表项
                trust_content = self._remove_trailing_lists(trust_content)
                # 额外清理：移除尾部重复的“加粗条目/纯文本条目”与单独 emoji 行
                trust_content = self._remove_standalone_emoji_lines(trust_content)
                trust_content = self._remove_redundant_tail_lines(trust_content)
                # 进一步清理：段内去重（解决“无序列表 marker 不显示/被去掉”导致的重复纯文本行）
                trust_content = self._dedupe_repeated_lines(trust_content)
                trust_content = self._remove_empty_subsections(trust_content)
                trust_section["content"] = trust_content
                trust_section["items"] = self._extract_bullet_points(trust_content)

            # 查找转化策略部分
            conversion_match = re.search(
                r'##?\s*[\U0001F300-\U0001F9FF]?\s*转化策略.*?\(CONVERSION\)\s*\n(.*?)(?=##?\s*[\U0001F300-\U0001F9FF]?\s*建议结构|$)',
                content,
                re.DOTALL | re.IGNORECASE
            )
            if conversion_match:
                conversion_content = conversion_match.group(1).strip()
                # 移除底部重复的要点列表
                conversion_content = self._remove_duplicate_summary(conversion_content)
                # 额外清理：移除底部所有独立的列表项
                conversion_content = self._remove_trailing_lists(conversion_content)
                # 额外清理：移除尾部重复的“加粗条目/纯文本条目”与单独 emoji 行
                conversion_content = self._remove_standalone_emoji_lines(conversion_content)
                conversion_content = self._remove_redundant_tail_lines(conversion_content)
                conversion_content = self._dedupe_repeated_lines(conversion_content)
                conversion_content = self._remove_empty_subsections(conversion_content)
                conversion_section["content"] = conversion_content
                conversion_section["items"] = self._extract_bullet_points(conversion_content)

            # 查找建议结构部分
            structure_match = re.search(
                r'##?\s*[\U0001F300-\U0001F9FF]?\s*建议结构.*?\(STRUCTURE\)\s*\n(.*?)$',
                content,
                re.DOTALL | re.IGNORECASE
            )
            if structure_match:
                structure_content = structure_match.group(1).strip()
                # 对于建议结构，只保留到"合规提示"之后的内容（包含合规提示）
                structure_content = self._clean_structure_content(structure_content)
                # 额外清理：移除底部所有独立的列表项
                structure_content = self._remove_trailing_lists(structure_content)
                structure_content = self._remove_standalone_emoji_lines(structure_content)
                structure_content = self._remove_redundant_tail_lines(structure_content)
                structure_content = self._dedupe_repeated_lines(structure_content)
                # 如果“关键视觉元素”段几乎全是重复项，则移除该段（常见于 bot 重复输出）
                structure_content = self._remove_redundant_key_visual_section(structure_content)
                structure_content = self._remove_empty_subsections(structure_content)
                structure_section["content"] = structure_content
                structure_section["items"] = self._extract_bullet_points(structure_content)

            return HotspotDetailResponse(
                title=title,
                trust=HotspotDetailSection(**trust_section),
                conversion=HotspotDetailSection(**conversion_section),
                structure=HotspotDetailSection(**structure_section),
                raw_content=content
            )

        except Exception as e:
            logger.error("解析详情内容失败", error=str(e), content_preview=content[:500])
            raise ValueError(f"解析详情内容失败: {str(e)}")

    def _remove_duplicate_summary(self, text: str) -> str:
        """
        移除底部重复的要点总结
        策略：
        1. 移除以 ## emoji 开始的总结部分
        2. 检测底部列表项是否与前面内容重复，如果重复则移除
        """
        # 首先查找以 ## 加 emoji 开始的部分
        emoji_match = re.search(r'\n##\s+[\U0001F300-\U0001F9FF]', text)
        if emoji_match:
            text = text[:emoji_match.start()].strip()
        
        lines = text.split('\n')
        
        # 提取所有非空的列表项内容（去除列表标记）
        def extract_list_content(line: str) -> str:
            """提取列表项的实际内容，去除前面的标记和格式"""
            line = line.strip()
            # 移除列表标记：-、•、*、1.、2. 等
            cleaned = re.sub(r'^[-•\*]\s+', '', line)
            cleaned = re.sub(r'^\d+[\.\)]\s+', '', cleaned)
            # 移除 ** 标记
            cleaned = re.sub(r'^\*\*|\*\*$', '', cleaned)
            # 移除引号
            cleaned = re.sub(r'^["""\'\']+|["""\'\']+$', '', cleaned)
            # 移除冒号
            cleaned = re.sub(r'[：:]\s*$', '', cleaned)
            return cleaned.strip()
        
        def normalize_text(text: str) -> str:
            """标准化文本用于比较"""
            # 移除所有空白字符
            text = re.sub(r'\s+', '', text)
            # 移除标点符号
            text = re.sub(r'[，。、；：""''（）【】《》\,\.\;\:\"\'\(\)\[\]<>]', '', text)
            return text.lower()
        
        # 从后往前检查，找出重复的列表项
        # 策略：如果底部的列表项内容在前面已经出现过，则认为是重复
        last_valid_idx = len(lines) - 1
        
        # 先找到最后一个非空行
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip():
                last_valid_idx = i
                break
        
        # 从最后一个非空行开始往前检查
        duplicate_start_idx = last_valid_idx + 1
        
        for i in range(last_valid_idx, -1, -1):
            line = lines[i].strip()
            
            if not line:
                continue
            
            # 检查是否是列表项
            is_list_item = bool(re.match(r'^[-•\*\d+\.]\s+', line))
            
            if is_list_item:
                # 提取列表项的实际内容
                content = extract_list_content(line)
                
                # 检查这个内容是否在前面的文本中出现过
                # 只检查前面的内容（不包括当前行及之后）
                previous_text = '\n'.join(lines[:i])
                
                # 使用标准化文本进行比较（更宽松的匹配）
                if content and len(content) > 8:
                    normalized_content = normalize_text(content)
                    normalized_previous = normalize_text(previous_text)
                    
                    # 如果标准化后的内容在前面出现过，说明是重复
                    if normalized_content and len(normalized_content) > 5 and normalized_content in normalized_previous:
                        # 标记这里开始是重复内容
                        duplicate_start_idx = min(duplicate_start_idx, i)
                    else:
                        # 找到了不重复的内容，停止检查
                        break
                else:
                    # 内容太短，继续检查
                    continue
            else:
                # 遇到非列表项，停止检查
                break
        
        # 如果找到了重复内容的起始位置，截取到那里
        if duplicate_start_idx <= last_valid_idx:
            # 往前找到最后一个有实质内容的行
            for i in range(duplicate_start_idx - 1, -1, -1):
                if lines[i].strip():
                    result_lines = lines[:i + 1]
                    return '\n'.join(result_lines).strip()
        
        return text
    
    def _clean_structure_content(self, text: str) -> str:
        """
        清理建议结构内容
        只保留到"合规提示"或"合规提醒"的完整段落，移除后续所有重复内容
        """
        # 策略：
        # 1. 找到合规提示的位置
        # 2. 从合规提示开始，找到下一个空行或分隔线
        # 3. 截取到那里，移除后续所有内容
        
        # 查找合规提示的位置（支持多种格式）
        compliance_patterns = [
            (r'\*\*合规[提示提醒注意事项]+[：:]\*\*[^\n]*', '**合规提示**'),  # **合规提示：**内容
            (r'###\s*合规[提示提醒注意事项]+[^\n]*', '### 合规提醒'),  # ### 合规提醒
            (r'##\s*⚠️\s*合规[提示提醒注意事项]+', '## ⚠️ 合规提示'),  # ## ⚠️ 合规提示
        ]
        
        for pattern, desc in compliance_patterns:
            match = re.search(pattern, text)
            if match:
                # 合规提示通常是一行完整说明；用户需求是“合规提示之后全部移除”
                # 这里按“合规提示所在段落”截断：优先截到段落结束（空行），否则截到该行结束
                compliance_start = match.start()
                compliance_end = match.end()

                # 找到合规提示所在行的行尾
                line_end_idx = text.find('\n', compliance_end)
                if line_end_idx == -1:
                    line_end_idx = len(text)

                # 尝试找到段落结束（合规提示后出现空行）
                paragraph_end_match = re.search(r'\n\s*\n', text[line_end_idx:])
                if paragraph_end_match:
                    end_idx = line_end_idx + paragraph_end_match.start()
                else:
                    end_idx = line_end_idx

                result = text[:end_idx].strip()
                result = re.sub(r'\n---+\s*$', '', result)
                return result
        
        # 如果没找到合规提示，检查是否有 "---" 分隔线，移除分隔线后的内容
        separator_match = re.search(r'\n---+\s*\n', text)
        if separator_match:
            return text[:separator_match.start()].strip()
        
        # 如果都没有，移除底部的重复总结
        return self._remove_duplicate_summary(text)

    def _remove_standalone_emoji_lines(self, text: str) -> str:
        """移除只有 emoji/符号的分隔行（如 💡、📋），避免出现在段尾。"""
        lines = text.split('\n')
        kept: List[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                kept.append(line)
                continue
            # 只包含 emoji/符号（不含字母数字汉字）
            if re.fullmatch(r'[\U0001F300-\U0001F9FF\u2600-\u27BF\W_]+', stripped):
                continue
            kept.append(line)
        return '\n'.join(kept).strip()

    def _normalize_line_for_dedupe(self, line: str) -> str:
        """归一化单行文本用于去重比较。"""
        s = line.strip()
        # 去掉列表/编号前缀
        s = re.sub(r'^[-•\*]\s+', '', s)
        s = re.sub(r'^\d+[\.\)]\s+', '', s)
        # 去掉 markdown 加粗
        s = s.replace('**', '')
        # 去掉引号与结尾冒号
        s = re.sub(r'^["“”\'‘’]+|["“”\'‘’]+$', '', s)
        s = re.sub(r'[：:]\s*$', '', s)
        # 压缩空白
        s = re.sub(r'\s+', '', s)
        # 去掉常见标点
        s = re.sub(r'[，。、；：”“‘’（）【】《》,.;:"\'()\[\]<>]', '', s)
        return s.lower()

    def _remove_redundant_tail_lines(self, text: str) -> str:
        """移除段尾重复行（包括非列表形式的重复加粗条目/纯文本条目）。

        仅从尾部向上清理：如果某行的归一化内容在该行之前已出现过，则认为是重复尾巴并移除。
        """
        lines = text.split('\n')
        if len(lines) <= 1:
            return text.strip()

        # 预计算归一化
        normalized = [self._normalize_line_for_dedupe(l) for l in lines]

        # 从尾部向上移除重复/空白
        cut_idx = len(lines)
        for i in range(len(lines) - 1, -1, -1):
            if not lines[i].strip():
                cut_idx = i
                continue
            n = normalized[i]
            if not n:
                cut_idx = i
                continue
            # 若该归一化内容在前面出现过，则认为尾部重复
            if n in set(normalized[:i]):
                cut_idx = i
                continue
            # 碰到第一个“非重复”的实质行则停止
            break

        result = '\n'.join(lines[:cut_idx]).strip()
        return result

    def _is_heading_line(self, line: str) -> bool:
        stripped = line.strip()
        return bool(re.match(r'^(#{1,6}\s+)', stripped))

    def _is_candidate_dedupe_line(self, line: str) -> bool:
        """判断该行是否适合参与“重复清理”。

        只清理“条目型”的行，避免误删正常段落：
        - 列表项
        - 以加粗开头的条目（**xxx**：...）
        - 含明显“条目结构”的冒号/百分比/数字
        """
        stripped = line.strip()
        if not stripped:
            return False
        if self._is_heading_line(stripped):
            return False
        # 列表项
        if re.match(r'^[-•\*]\s+', stripped) or re.match(r'^\d+[\.\)]\s+', stripped):
            return True
        # 加粗条目
        if stripped.startswith('**') and ('：' in stripped or ':' in stripped):
            return True
        # 看起来像条目但缺 marker（你反馈的“::marker 不显示”常见表现）
        if ('：' in stripped or ':' in stripped or '%' in stripped) and len(stripped) >= 12:
            return True
        return False

    def _dedupe_repeated_lines(self, text: str) -> str:
        """对整段做“候选行去重”：移除后续重复条目（包括无 marker 的重复行）。"""
        lines = text.split('\n')
        seen: set[str] = set()
        output: List[str] = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                output.append(line)
                continue

            if not self._is_candidate_dedupe_line(stripped):
                output.append(line)
                continue

            key = self._normalize_line_for_dedupe(stripped)
            # 太短的不参与去重，避免误删
            if len(key) < 12:
                output.append(line)
                continue

            if key in seen:
                continue

            seen.add(key)
            output.append(line)

        # 压缩多余空行
        result_lines: List[str] = []
        for line in output:
            if line.strip() == '' and (not result_lines or result_lines[-1].strip() == ''):
                continue
            result_lines.append(line)

        return '\n'.join(result_lines).strip()

    def _remove_empty_subsections(self, text: str) -> str:
        """移除内容为空的三级标题块（例如只剩 '### 心理情绪代价'）。"""
        lines = text.split('\n')
        result: List[str] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if re.match(r'^###\s+', line.strip()):
                header_idx = i
                j = i + 1
                # 收集直到下一个 ### 或结束
                block: List[str] = []
                while j < len(lines) and not re.match(r'^###\s+', lines[j].strip()):
                    block.append(lines[j])
                    j += 1
                # 判断 block 是否有实质内容（非空、非emoji）
                has_content = any(
                    b.strip() and not re.fullmatch(
                        r'[\U0001F300-\U0001F9FF\u2600-\u27BF\W_]+',
                        b.strip()
                    )
                    for b in block
                )
                if has_content:
                    result.append(lines[header_idx])
                    result.extend(block)
                i = j
                continue
            result.append(line)
            i += 1
        return '\n'.join(result).strip()

    def _remove_redundant_key_visual_section(self, text: str) -> str:
        """如果 '### 关键视觉元素' 段的内容大多是重复项，则移除整段。"""
        match = re.search(r'(^###\s*关键视觉元素\s*$)([\s\S]*?)(?=^###\s+|\Z)', text, re.MULTILINE)
        if not match:
            return text

        section_header = match.group(1)
        section_body = match.group(2)

        # 拿 section 之前的内容作为“已出现内容”
        prefix_text = text[:match.start()]
        prefix_lines = [self._normalize_line_for_dedupe(l) for l in prefix_text.split('\n') if l.strip()]
        prefix_set = set([l for l in prefix_lines if len(l) >= 12])

        body_lines_raw = [l for l in section_body.split('\n') if l.strip()]
        if not body_lines_raw:
            # 空段直接移除
            return (text[:match.start()] + text[match.end():]).strip()

        body_norm = [self._normalize_line_for_dedupe(l) for l in body_lines_raw]
        candidates = [n for n in body_norm if len(n) >= 12]
        if not candidates:
            return text

        dup_count = sum(1 for n in candidates if n in prefix_set)
        ratio = dup_count / max(1, len(candidates))

        # 超过 60% 认为是“重复输出”，移除该段
        if ratio >= 0.6:
            logger.info(
                "Removing redundant key visual section",
                duplicate_ratio=ratio,
                dup_count=dup_count,
                total=len(candidates),
            )
            return (text[:match.start()] + text[match.end():]).strip()

        return text
    
    def _remove_trailing_lists(self, text: str) -> str:
        """
        移除底部所有独立的列表项
        策略：从后往前找，如果遇到连续的列表项（没有标题或说明文字），全部移除
        """
        lines = text.split('\n')
        
        # 从后往前找，找到最后一个非列表、非空的实质性内容
        last_valid_idx = -1
        trailing_list_start = len(lines)
        
        for i in range(len(lines) - 1, -1, -1):
            line = lines[i].strip()
            
            if not line:
                # 空行，继续
                continue
            
            # 检查是否是列表项
            is_list = bool(re.match(r'^[-•\*\d+\.]\s+', line))
            
            if is_list:
                # 是列表项，继续往前找
                continue
            else:
                # 找到非列表项
                # 检查这是否是一个标题或说明（比如 "**数据支撑：**"）
                is_header = bool(re.match(r'^\*\*.*[：:]\*\*\s*$', line))
                
                if is_header:
                    # 这是一个标题，后面的列表是有意义的，保留
                    last_valid_idx = i
                    break
                else:
                    # 这是普通内容，后面的列表可能是重复的
                    # 检查后面有多少个连续的列表项
                    list_count = 0
                    for j in range(i + 1, len(lines)):
                        if lines[j].strip() and re.match(r'^[-•\*\d+\.]\s+', lines[j].strip()):
                            list_count += 1
                    
                    # 如果后面有2个以上的列表项，认为是重复的总结
                    if list_count >= 2:
                        last_valid_idx = i
                        trailing_list_start = i + 1
                    break
        
        # 如果找到了重复的列表，截取到那里
        if last_valid_idx >= 0 and trailing_list_start < len(lines):
            result_lines = lines[:trailing_list_start]
            # 移除末尾的空行
            while result_lines and not result_lines[-1].strip():
                result_lines.pop()
            return '\n'.join(result_lines).strip()
        
        return text
    
    def _extract_bullet_points(self, text: str) -> List[str]:
        """
        从文本中提取要点列表
        """
        items = []
        # 匹配以 -、•、* 或数字开头的行
        for line in text.split('\n'):
            line = line.strip()
            if re.match(r'^[•\-\*]\s+', line):
                items.append(re.sub(r'^[•\-\*]\s+', '', line))
            elif re.match(r'^\d+[\.\)]\s+', line):
                items.append(re.sub(r'^\d+[\.\)]\s+', '', line))
        return items


# 创建全局实例（延迟初始化，避免在导入时就要求环境变量）
coze_service: Optional[CozeService] = None

def get_coze_service() -> CozeService:
    """获取 Coze 服务实例（延迟初始化）"""
    global coze_service
    if coze_service is None:
        coze_service = CozeService()
    return coze_service

