"""
系统配置服务
"""

import json
from typing import Optional, List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
import structlog

from ..models.tables.system_config import SystemConfig
from ..models.schemas.system_config import SystemConfigCreate, SystemConfigUpdate
from ..utils.exceptions import NotFoundError, ValidationError

logger = structlog.get_logger(__name__)

# 默认的脚本生成提示词（支持：联网开关驱动的智能数据校验 + 占位符注入策略上下文）
KF_VIDEO_RULES_BEGIN_MARKER = "<!--KF_VIDEO_RULES_BEGIN-->"
KF_VIDEO_RULES_END_MARKER = "<!--KF_VIDEO_RULES_END-->"

DEFAULT_SCRIPT_PROMPT = """你是一个专业的视频脚本创作专家。你的任务是根据用户的创意和风格要求，生成一个结构化的视频脚本。

*** 指导原则：**

1. 【🛡️ 智能逻辑判断：数据校验模块】(优先级：最高)
当前配置：
- 联网开关：{is_web_search_enabled} (由前端强制控制)
- 脚本风格名称：{style_name}
- 脚本风格说明：{style_description}
- 当前日期：{current_date} (例如: 2025年12月)

请根据联网开关的状态，直接执行对应指令：

### 👉 状态 A：联网已开启 (True)
1) 判断搜索策略 (根据风格自动分流)：
- IF {style_name} 是 全球简报型 × 科技快闪：
  - 关键词构造：必须包含 “{current_date_month}” 或 “上个月份”。
  - 示例：搜 \"2025年12月 抗衰突破\"，严禁搜宽泛的 \"2025 抗衰\"。
  - 筛选红线：仅采信 45天内 的信源。
  - 强制引用：必须在【场景环境】字段末尾标注 [Source: 媒体名, Date]。
- ELSE(通用科普/原理模式)：
  - 关键词构造：包含 “{current_date_year}” 即可。
  - 示例：搜 \"2025 胶原蛋白流失率 数据\"。
  - 筛选红线：统计数据不超过 2 年，经典原理不限。

2) 反幻觉指令：
- 如果限定时间内搜不到，请诚实降级：使用去年的数据，但口播必须说明年份（如“据2024年数据”），严禁伪装成最新。

### 👉 状态 B：联网已关闭 (False)
1) 数据引用优先级 (Data Hierarchy)：
- 优先级 1：最优先使用【科学支撑体系】中提供的具体数据（如果有）。
- 优先级 2：如果策略中没有数据，允许使用你作为大模型预训练时掌握的“公认医学通识”(General Medical Consensus)。
  - 允许：使用公认的生理机制（如：“皮质醇升高会导致胶原蛋白分解”、“胰岛素抵抗”）。
  - 禁止：引用具体的、时效性强的统计数据（如：“2024年某论文说发病率提升了 32.5%”）。

2) 反幻觉红线 (Anti-Hallucination)：
- 严禁捏造数值：在没有外部输入的情况下，绝对不要编造带有小数点的精确数字、年份或具体的论文出处。
- 处理方式：将“定量描述”降级为“定性描述”。
  - ❌ 错误写法：“根据哈佛研究，风险提升了 50%。”
  - ✅ 正确写法：“研究表明，风险会显著提升。”

---

2. 结构化与风格优先级：
- 默认参考【高转化内容架构】（钩子-痛点-解决-行动）。
- 例外情况：如果 {style_name} 中定义了特殊的结构（如“全球简报型”的清单结构），请优先遵循 {style_name} 中的结构要求。

3. 转化点控制：
- 忽略实体产品：即使策略提及面霜/补剂，也不要在脚本中直接推荐购买。
- 重定向目标：将解决方案核心锁定为 “AI 智能诊断” 或 “获取独家资料”。
- 利用策略亮点：借用【转化策略亮点】中的紧迫感（如“寒冬”）来论证为何现在需要测一测。

4. 合规性：严格遵守策略中提到的【合规性预警】，避免夸大宣称。

【核心策略输入】(必须严格基于以下信息创作)
以下信息来自市场策略中心，是脚本的灵魂，请务必融入：
{strategy_context}

脚本要求：
1. 视频总时长：{total_duration}秒
2. 单个片段时长：{segment_duration}秒
3. 片段数量：{segment_count}个
4. 脚本风格（必须严格遵守）：{style_name}
   - 风格说明：{style_description}
   - ⚠️ 这是最重要的要求！整个脚本的内容、结构、表达方式都必须完全符合这个风格的特点

默认内容结构（仅当 {style_name} 未指定特殊结构时使用）
“3 秒钩子 + 20% 痛点共鸣 + 50% 解决方案 + 10% 行动指令”
1. 钩子：①痛点提问 ②数据冲击 ③悬念故事
2. 痛点共鸣（≈20%时长）：把症状场景化、画面化，最好配特写镜头
3. 解决方案（≈50%时长）：给出可复制的“自救动作”或“AI 智能诊断/资料获取”路径
4. 行动指令（≈10%时长）：限时福利/负面警示/互动提问

脚本格式要求（必须严格遵守）：
1. 片段结构（从 segment_0 开始，不要输出“第0帧/开场画面”段落）：
   - 必须按照以下字段结构输出，不要省略任何字段：
   
(开始秒数-结束秒数s)
""" + KF_VIDEO_RULES_BEGIN_MARKER + """
关键帧：(必须包含以下要素的详细描述，至少60字)
  - 主体描述：人物/物体的外观、姿态、表情、服装、动作状态等具体特征
  - 场景环境：室内/室外、空间布局、背景元素、道具细节、环境氛围
  - 光影效果：光线来源、方向、强度、色温、明暗对比、光影层次
  - 构图视角：镜头角度（平视/俯视/仰视/侧面）、景别（特写/中景/全景）、画面重心
  - 色彩风格：主色调、辅助色、配色方案、色彩情绪、整体视觉风格
  - 质感细节：材质、纹理、装饰元素、细节特写
  - 重要：画面中不能出现任何中文文字（例如：毛笔字、标语、招牌、包装中文、字幕、UI文字等）。如果需要表达概念，请用“无文字”的视觉隐喻/符号/图形来表达。
视频：(必须包含以下要素的详细描述，至少50字)
  - 主体动作：具体的动作变化、运动轨迹、动作幅度、速度节奏、肢体语言
  - 镜头运动：推拉摇移跟升降等运镜方式、运动速度、运动轨迹
  - 画面转场：与前一帧的自然衔接方式、过渡效果
  - 视觉节奏：动作的快慢变化、画面的韵律感、张弛有度
  - 情绪氛围：通过动作和画面传达的情感、氛围营造
  - 重要：画面中不能出现任何中文文字（例如：字幕、中文标牌、包装中文、屏幕中文UI等），避免描述“出现中文文字/浮现汉字/写着中文”等内容。
""" + KF_VIDEO_RULES_END_MARKER + """
音色：(全局统一、唯一的、详细的中文声音描述，例如：知性女声，声音温暖，专业且富有磁性)
口播文案：(适配{segment_duration}秒语速，约{content_length_min}-{content_length_max}个汉字)

3. 时间格式：
   - 必须严格使用 (0-{segment_duration}s), ({segment_duration}-{segment_duration * 2}s) 等格式。

4. 详细要求：
   - 关键帧：必须详尽描述（至少60字），像电影分镜脚本一样精确，让图片生成AI能准确理解每个视觉元素。
   - 画面质量：避免描述会导致“水印/文字/扭曲肢体/模糊/低画质”等不良输出的倾向性内容。
   - 视频：必须详细描述动态过程（至少50字），包含镜头语言、动作细节、情绪表达，让视频生成AI能准确呈现动态效果。
   - 音色：所有片段必须保持完全一致的音色描述。
   - 口播文案：严格控制字数，语言风格符合设定的脚本风格。
   - 一致性：同一角色、物品在所有片段中必须保持完全一致（外观、服装、特征等）。

请直接输出脚本内容，不要添加任何解释或说明。"""


def _extract_kf_video_rules_snippet(prompt: str) -> Optional[str]:
    """从完整脚本提示词中提取关键帧/视频规则片段.

    Args:
        prompt: 完整脚本提示词

    Returns:
        规则片段（不包含 begin/end marker），若无法解析返回 None
    """
    if KF_VIDEO_RULES_BEGIN_MARKER in prompt and KF_VIDEO_RULES_END_MARKER in prompt:
        start = prompt.index(KF_VIDEO_RULES_BEGIN_MARKER) + len(KF_VIDEO_RULES_BEGIN_MARKER)
        end = prompt.index(KF_VIDEO_RULES_END_MARKER)
        return prompt[start:end].strip("\n")

    # 兼容旧版：没有 marker 时，尝试用字段锚点抽取（尽量保守）
    start_anchor = "\n关键帧："
    end_anchor = "\n音色："
    start = prompt.find(start_anchor)
    end = prompt.find(end_anchor)
    if start == -1 or end == -1 or end <= start:
        return None
    return prompt[start:end].strip("\n")


def _replace_kf_video_rules_snippet(prompt: str, new_snippet: str) -> str:
    """替换完整脚本提示词中的关键帧/视频规则片段.

    Args:
        prompt: 原始完整提示词
        new_snippet: 新的规则片段（不包含 begin/end marker）

    Returns:
        替换后的完整提示词
    """
    if KF_VIDEO_RULES_BEGIN_MARKER in prompt and KF_VIDEO_RULES_END_MARKER in prompt:
        before, rest = prompt.split(KF_VIDEO_RULES_BEGIN_MARKER, 1)
        _, after = rest.split(KF_VIDEO_RULES_END_MARKER, 1)
        return (
            before
            + KF_VIDEO_RULES_BEGIN_MARKER
            + "\n"
            + new_snippet.strip("\n")
            + "\n"
            + KF_VIDEO_RULES_END_MARKER
            + after
        )

    # 旧版无 marker：尝试用锚点替换，并补齐 marker，确保后续稳定
    start_anchor = "\n关键帧："
    end_anchor = "\n音色："
    start = prompt.find(start_anchor)
    end = prompt.find(end_anchor)
    if start == -1 or end == -1 or end <= start:
        # 无法定位：直接在 (开始秒数-结束秒数s) 后插入新片段
        insert_anchor = "\n(开始秒数-结束秒数s)\n"
        if insert_anchor in prompt:
            return prompt.replace(
                insert_anchor,
                insert_anchor
                + KF_VIDEO_RULES_BEGIN_MARKER
                + "\n"
                + new_snippet.strip("\n")
                + "\n"
                + KF_VIDEO_RULES_END_MARKER
                + "\n",
                1,
            )
        return (
            prompt
            + "\n"
            + KF_VIDEO_RULES_BEGIN_MARKER
            + "\n"
            + new_snippet.strip("\n")
            + "\n"
            + KF_VIDEO_RULES_END_MARKER
            + "\n"
        )

    before = prompt[:start]
    after = prompt[end:]
    return (
        before
        + "\n"
        + KF_VIDEO_RULES_BEGIN_MARKER
        + "\n"
        + new_snippet.strip("\n")
        + "\n"
        + KF_VIDEO_RULES_END_MARKER
        + "\n"
        + after.lstrip("\n")
    )

# 默认的脚本风格配置
DEFAULT_SCRIPT_STYLES = [
    {
        "id": "storytelling",
        "name": "故事化叙事风格",
        "description": "将创意扩展为一个完整的故事，通过一个具体的故事或场景引入理论或知识的科普。脚本结构：开端（问题）：展示一个普通人或企业面临的困境。发展（引入理论知识）：科学理论如何介入，解决问题。高潮（价值升华）：展示问题解决后的美好结果。结尾（呼吁）：点明主题，如'xxx生活习惯，让你更年轻'。每一段片段开头强调这是一个写实场景，用写实画面表现。"
    },
    {
        "id": "visual_animation",
        "name": "可视化动画/图形动画风格",
        "description": "将创意扩展为一个完整的科普动画，通过一个具体的故事或场景引入理论或知识的科普。脚本结构：开端（问题）：展示一个普通人或企业面临的困境。发展（引入理论知识）：科学理论如何介入，解决问题。高潮（价值升华）：展示问题解决后的美好结果。结尾（呼吁）：点明主题，如'xxx生活习惯，让你更年轻'。每一段片段开头强调这是一个写实场景，用写实画面表现。特点：用生动的动画、MG（Motion Graphics）来解释抽象的医学概念（如神经网络）,必须保证所有的描述风格统一。脚本结构：提出概念：'什么是抗炎？'比喻解释：用动画过程，类比细胞抵抗炎症的过程。步骤拆解：分解为几个可视化步骤。每一段片段开头强调这是一个动画非真实场景，用动画表现。"
    }
]


class SystemConfigService:
    """系统配置服务类"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_config(self, config_key: str) -> Optional[SystemConfig]:
        """
        获取配置
        
        Args:
            config_key: 配置键
            
        Returns:
            配置对象，如果不存在返回None
        """
        result = await self.db.execute(
            select(SystemConfig).where(SystemConfig.config_key == config_key)
        )
        return result.scalar_one_or_none()
    
    async def get_config_value(self, config_key: str, default: Optional[str] = None) -> Optional[str]:
        """
        获取配置值
        
        Args:
            config_key: 配置键
            default: 默认值
            
        Returns:
            配置值，如果不存在返回默认值
        """
        config = await self.get_config(config_key)
        return config.config_value if config else default
    
    async def create_config(self, config_data: SystemConfigCreate) -> SystemConfig:
        """
        创建配置
        
        Args:
            config_data: 配置数据
            
        Returns:
            创建的配置对象
            
        Raises:
            ValidationError: 配置键已存在
        """
        try:
            config = SystemConfig(**config_data.model_dump())
            self.db.add(config)
            await self.db.commit()
            await self.db.refresh(config)
            
            logger.info(
                "System config created",
                config_key=config.config_key
            )
            
            return config
        except IntegrityError:
            await self.db.rollback()
            raise ValidationError(f"配置键已存在: {config_data.config_key}")
    
    async def update_config(self, config_key: str, config_data: SystemConfigUpdate) -> SystemConfig:
        """
        更新配置
        
        Args:
            config_key: 配置键
            config_data: 配置数据
            
        Returns:
            更新后的配置对象
            
        Raises:
            NotFoundError: 配置不存在
        """
        config = await self.get_config(config_key)
        if not config:
            raise NotFoundError(f"配置不存在: {config_key}")
        
        # 更新字段
        for field, value in config_data.model_dump(exclude_unset=True).items():
            setattr(config, field, value)
        
        await self.db.commit()
        await self.db.refresh(config)
        
        logger.info(
            "System config updated",
            config_key=config_key
        )
        
        return config
    
    async def get_or_create_config(
        self,
        config_key: str,
        default_value: str,
        description: Optional[str] = None
    ) -> SystemConfig:
        """
        获取或创建配置
        
        Args:
            config_key: 配置键
            default_value: 默认值
            description: 描述
            
        Returns:
            配置对象
        """
        config = await self.get_config(config_key)
        if config:
            return config
        
        # 创建新配置
        config_data = SystemConfigCreate(
            config_key=config_key,
            config_value=default_value,
            description=description
        )
        return await self.create_config(config_data)
    
    async def get_script_prompt(self) -> str:
        """
        获取脚本生成提示词
        
        Returns:
            提示词内容
        """
        config = await self.get_or_create_config(
            config_key="script_generation_prompt",
            default_value=DEFAULT_SCRIPT_PROMPT,
            description="脚本生成提示词模板"
        )
        return config.config_value

    async def get_kf_video_rules_snippet(self) -> str:
        """获取当前脚本提示词中的关键帧/视频规则片段.

        Returns:
            规则片段（不包含 marker）

        Raises:
            ValidationError: 无法解析规则片段
        """
        prompt = await self.get_script_prompt()
        snippet = _extract_kf_video_rules_snippet(prompt)
        if not snippet:
            raise ValidationError("无法从脚本提示词中解析关键帧/视频规则片段")
        return snippet

    async def update_kf_video_rules_snippet(self, new_snippet: str) -> SystemConfig:
        """更新脚本提示词中的关键帧/视频规则片段（全局生效）.

        Args:
            new_snippet: 新规则片段（不包含 marker）

        Returns:
            更新后的系统配置对象（script_generation_prompt）
        """
        if not new_snippet or not new_snippet.strip():
            raise ValidationError("规则片段不能为空")

        # 轻量结构校验：必须包含关键字段锚点，避免 Gemini 乱输出
        required_anchors = ["关键帧", "视频"]
        for anchor in required_anchors:
            if anchor not in new_snippet:
                raise ValidationError(f"规则片段缺少必要字段: {anchor}")

        prompt = await self.get_script_prompt()
        updated_prompt = _replace_kf_video_rules_snippet(prompt, new_snippet)
        return await self.update_script_prompt(updated_prompt)
    
    async def update_script_prompt(self, prompt: str) -> SystemConfig:
        """
        更新脚本生成提示词
        
        Args:
            prompt: 新的提示词
            
        Returns:
            更新后的配置对象
        """
        # 确保配置存在
        await self.get_or_create_config(
            config_key="script_generation_prompt",
            default_value=DEFAULT_SCRIPT_PROMPT,
            description="脚本生成提示词模板"
        )
        
        # 更新配置
        config_data = SystemConfigUpdate(
            config_value=prompt,
            description="脚本生成提示词模板"
        )
        return await self.update_config("script_generation_prompt", config_data)
    
    async def get_script_styles(self) -> List[Dict]:
        """
        获取脚本风格配置
        
        Returns:
            风格列表
        """
        config = await self.get_or_create_config(
            config_key="script_styles",
            default_value=json.dumps(DEFAULT_SCRIPT_STYLES, ensure_ascii=False),
            description="脚本风格配置"
        )
        
        try:
            return json.loads(config.config_value)
        except json.JSONDecodeError:
            logger.error("Failed to parse script styles config", value=config.config_value)
            return DEFAULT_SCRIPT_STYLES
    
    async def update_script_styles(self, styles: List[Dict]) -> SystemConfig:
        """
        更新脚本风格配置
        
        Args:
            styles: 新的风格列表
            
        Returns:
            更新后的配置对象
        """
        # 验证风格数据
        for style in styles:
            if not all(key in style for key in ["id", "name", "description"]):
                raise ValidationError("风格数据必须包含 id、name 和 description 字段")
        
        # 确保配置存在
        await self.get_or_create_config(
            config_key="script_styles",
            default_value=json.dumps(DEFAULT_SCRIPT_STYLES, ensure_ascii=False),
            description="脚本风格配置"
        )
        
        # 更新配置
        config_data = SystemConfigUpdate(
            config_value=json.dumps(styles, ensure_ascii=False),
            description="脚本风格配置"
        )
        return await self.update_config("script_styles", config_data)
