<template>
  <div
    class="script-optimization"
    :class="{ 'script-optimization--inspiration': is_inspiration_mode }"
  >
    <div class="script-optimization-card">
      <!-- 输入框区域 -->
      <div class="input-section">
        <el-input
          v-model="inputContent"
          type="textarea"
          :placeholder="placeholder"
          :maxlength="3000"
          :rows="8"
          :autosize="{ minRows: 8, maxRows: 20 }"
          class="script-input"
          @focus="handleFocus"
          @blur="handleBlur"
        />
      </div>

      <!-- 控制面板 -->
      <div class="control-panel">
        <!-- 第一行：配置项和辅助按钮 -->
        <div class="control-row control-row-first">
          <!-- 参考图按钮 -->
          <el-button
            type="default"
            class="reference-button"
            @click="showReferenceDialog"
          >
            <el-icon><Picture /></el-icon>
            参考图 ({{ referenceImages.length }}/5)
          </el-button>

          <!-- 选择脚本风格 -->
          <el-select
            v-model="formData.style"
            placeholder="选择脚本风格"
            class="control-select"
            clearable
          >
            <el-option
              v-for="style in scriptStyles"
              :key="style.id"
              :label="style.name"
              :value="style.id"
            >
              <el-tooltip
                v-if="style.usage"
                :content="style.usage"
                placement="right"
                effect="dark"
                :show-after="300"
                :teleported="false"
              >
                <template #default>
                  <span>{{ style.name }}</span>
                </template>
              </el-tooltip>
              <span v-else>{{ style.name }}</span>
            </el-option>
          </el-select>

          <!-- 视频总时长 -->
          <el-input-number
            v-model="formData.totalDuration"
            :min="8"
            :max="3600"
            :step="1"
            placeholder="视频总时长"
            class="control-input"
            :controls="false"
          >
            <template #append>秒</template>
          </el-input-number>

          <!-- 单个视频时长 - 已隐藏,固定为8秒 -->
          <!-- <el-input-number
            v-model="formData.segmentDuration"
            :min="5"
            :max="300"
            :step="1"
            placeholder="单个视频时长"
            class="control-input"
            :controls="false"
          >
            <template #append>秒</template>
          </el-input-number> -->

          <!-- 选择模型 -->
          <ModelSelect
            v-model="formData.model"
            type="script"
            placeholder="选择模型"
            class="control-select"
            clearable
            :allowed-model-ids="allowedScriptModelIds"
            @change="handleModelChange"
          />

          <!-- 辅助按钮 -->
          <el-button
            type="default"
            class="style-button"
            @click="showStyleDialog"
          >
            风格
          </el-button>
          <el-button
            type="default"
            class="prompt-button"
            @click="showPromptDialog"
          >
            提示词
          </el-button>

          <!-- 手动执行“关键帧/视频提示词迭代”（默认隐藏，仅本地开关启用；不要上生产） -->
          <el-tooltip
            v-if="showManualRulesAuditButton"
            effect="dark"
            content="手动触发：用 Gemini 审查当前脚本的关键帧/视频描述倾向，并仅更新“画面不出现中文文字”相关规则片段。"
            placement="top"
          >
            <el-button
              type="default"
              class="prompt-button"
              :loading="auditingRules"
              :disabled="auditingRules"
              @click="handleManualRulesAudit"
            >
              迭代提示词
            </el-button>
          </el-tooltip>

          <!-- 联网搜索开关（在“提示词”按钮右侧） -->
          <el-tooltip
            effect="dark"
            :content="webSearchTooltip"
            placement="top"
            v-if="webSearchForced"
          >
            <div class="web-search-toggle">
              <span class="web-search-label">联网</span>
              <el-switch
                v-model="formData.enableSearch"
                :disabled="webSearchForced || !supportsWebSearch"
                active-text=""
                inactive-text=""
              />
            </div>
          </el-tooltip>

          <div class="web-search-toggle" v-else>
              <span class="web-search-label">联网</span>
              <el-switch
                v-model="formData.enableSearch"
                :disabled="webSearchForced || !supportsWebSearch"
                active-text=""
                inactive-text=""
              />
            </div>
        </div>

        <!-- 第二行：生成按钮 -->
        <div class="control-row control-row-second">
          <el-button
            type="primary"
            :loading="loading"
            :disabled="loading"
            class="action-button"
            @click="handleSubmit"
          >
            {{ buttonText }}
          </el-button>
          <el-button
            type="warning"
            :loading="oneClickLoading"
            :disabled="oneClickLoading || loading"
            class="one-click-button"
            @click="handleOneClickGenerate"
          >
            <el-icon><MagicStick /></el-icon>
            一键生成
          </el-button>
        </div>
      </div>

      <!-- 错误提示 -->
      <div v-if="errorMessage" class="error-message">
        <el-alert
          :title="errorMessage"
          type="error"
          :closable="false"
          show-icon
        />
      </div>
    </div>

    <!-- 提示词编辑弹窗 -->
    <el-dialog
      v-model="promptDialogVisible"
      title="编辑脚本生成提示词"
      width="70%"
      :close-on-click-modal="false"
      class="prompt-dialog"
    >
      <div class="prompt-dialog-content">
        <el-input
          v-model="promptContent"
          type="textarea"
          :rows="20"
          placeholder="请输入提示词模板..."
          class="prompt-textarea"
        />
        <div class="prompt-tips">
          <el-alert
            title="提示词支持以下变量（使用 {变量名} 格式）："
            type="info"
            :closable="false"
          >
            <template #default>
              <ul class="variable-list">
                <li><code>{total_duration}</code> - 视频总时长（秒）</li>
                <li><code>{segment_duration}</code> - 单个片段时长（秒）</li>
                <li><code>{segment_count}</code> - 片段数量</li>
                <li><code>{style}</code> - 脚本风格（兼容字段，通常等于风格说明）</li>
                <li><code>{style_name}</code> - 风格名称（用于逻辑判断/展示）</li>
                <li><code>{style_description}</code> - 风格说明（用于指导生成）</li>
                <li><code>{strategy_context}</code> - 核心策略输入（市场策略中心内容）</li>
                <li><code>{is_web_search_enabled}</code> - 联网开关 True/False（由前端强制控制）</li>
                <li><code>{current_date}</code> - 当前日期（如 2025年12月）</li>
                <li><code>{current_date_month}</code> - 当前月份（如 2025年12月）</li>
                <li><code>{current_date_year}</code> - 当前年份（如 2025）</li>
                <li><code>{content_length_min}</code> - 最小内容长度</li>
                <li><code>{content_length_max}</code> - 最大内容长度</li>
              </ul>
            </template>
          </el-alert>
        </div>
      </div>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="promptDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="savingPrompt" @click="savePrompt">
            保存
          </el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 风格编辑弹窗 -->
    <el-dialog
      v-model="styleDialogVisible"
      title="编辑脚本风格"
      width="70%"
      :close-on-click-modal="false"
      class="style-dialog"
    >
      <div class="style-dialog-content">
        <div class="style-list-header">
          <el-button
            type="primary"
            size="small"
            @click="addNewStyle"
          >
            <el-icon><Plus /></el-icon>
            新增风格
          </el-button>
        </div>
        <div class="style-list">
          <div
            v-for="(style, index) in editableStyles"
            :key="style.id"
            class="style-item"
          >
            <div class="style-item-header">
              <el-input
                v-model="style.name"
                placeholder="风格名称"
                class="style-name-input"
              />
              <el-button
                type="danger"
                size="small"
                :icon="Delete"
                circle
                @click="deleteStyle(index)"
                :disabled="editableStyles.length <= 1"
              />
            </div>
            <el-input
              v-model="style.description"
              type="textarea"
              :rows="4"
              placeholder="风格描述"
              class="style-description-input"
            />
            <el-input
              v-model="style.usage"
              type="textarea"
              :rows="2"
              placeholder="用途说明（可选，例如：适用场景：症状自查、红黑榜、避坑指南、食谱）"
              class="style-usage-input"
            />
          </div>
        </div>
        <div class="style-tips">
          <el-alert
            title="提示："
            type="info"
            :closable="false"
          >
            <template #default>
              <ul>
                <li>编辑风格的描述将影响脚本生成的方式，请确保描述清晰明确</li>
                <li>至少保留一个风格</li>
              </ul>
            </template>
          </el-alert>
        </div>
      </div>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="styleDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="savingStyle" @click="saveStyles">
            保存
          </el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 参考图管理弹窗 -->
    <el-dialog
      v-model="referenceDialogVisible"
      title="管理参考图"
      width="70%"
      height="800"
      :close-on-click-modal="false"
      class="reference-dialog"
    >
      <div class="reference-dialog-content">
        <el-alert
          title="参考图说明"
          type="info"
          :closable="false"
          class="reference-tips"
        >
          <template #default>
            <ul>
              <li>参考图将用于生成首段关键帧（segment_0），帮助AI理解您想要的画面风格</li>
              <li>最多可上传5张参考图，支持 JPG、PNG、WEBP 格式</li>
              <li>建议上传与您期望的视频风格相近的图片</li>
            </ul>
          </template>
        </el-alert>
        
        <ReferenceImageManager
          v-model="referenceImages"
          :max-images="5"
          button-text="上传参考图"
        />
      </div>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="referenceDialogVisible = false">关闭</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElLoading, ElMessageBox } from 'element-plus'
import { MagicStick, Plus, Delete, Picture } from '@element-plus/icons-vue'
import { scriptApi, modelApi, projectApi, configApi } from '@/api'
import { useProjectStore } from '@/stores'
import type { GenerateScriptRequest } from '@/types'
import ModelSelect from './ModelSelect.vue'
import ReferenceImageManager from '@/components/script-generation/ReferenceImageManager.vue'

interface Props {
  /** 输入框占位符 */
  placeholder: string
  /** 按钮文字 */
  buttonText: string
  /** 模式：inspiration（从灵感开始）或 script（从脚本开始） */
  mode: 'inspiration' | 'script'
  /** 初始内容（用于编辑场景） */
  initialContent?: string
}

const props = withDefaults(defineProps<Props>(), {
  initialContent: ''
})

const is_inspiration_mode = computed((): boolean => props.mode === 'inspiration')

const emit = defineEmits<{
  success: [data: any]
  error: [error: string]
}>()

const router = useRouter()
const route = useRoute()
const projectStore = useProjectStore()

// 表单数据
const inputContent = ref(props.initialContent)
const formData = ref<{
  style: string
  totalDuration: number | null
  segmentDuration: number | null
  model: string
  enableSearch: boolean
}>({
  style: '',
  totalDuration: null,
  segmentDuration: 4, // 默认4秒（与当前全局分段默认保持一致，已隐藏输入框）
  model: '', // 默认模型
  enableSearch: false
})

// 状态
const loading = ref(false)
const oneClickLoading = ref(false)
const errorMessage = ref('')
const promptDialogVisible = ref(false)
const promptContent = ref('')
const savingPrompt = ref(false)
const auditingRules = ref(false)
const isFocused = ref(false)
const styleDialogVisible = ref(false)
const savingStyle = ref(false)
const editableStyles = ref<{ id: string; name: string; description: string; usage?: string }[]>([])

// 参考图相关
const referenceDialogVisible = ref(false)
// 从store中获取参考图数据
const referenceImages = computed(() => {
  return projectStore.referenceImageUrls.map(url => ({
    url,
    filename: '',
    size: 0
  }))
})

// 加载进度相关
const loadingProgress = ref(0)
const loadingText = ref('正在生成脚本...')
const loadingTip = ref('AI正在分析您的创意')

// 选项数据
const scriptStyles = ref<{ id: string; name: string; description: string; usage?: string }[]>([])
const scriptModels = ref<Array<{ id: string; name: string; supports_web_search?: boolean; supportsWebSearch?: boolean }>>([])

const FORCED_MODEL_IDS = ['deepseek-reasoner', 'kimi-k2-thinking']

const selectedStyle = computed(() => {
  return scriptStyles.value.find(s => s.id === formData.value.style)
})

const isNewsStyle = computed(() => selectedStyle.value?.name.includes('全球简报型'))

const webSearchForced = computed(() => isNewsStyle.value)

const webSearchTooltip = computed(() => {
  if (webSearchForced.value) return '新闻风格需依赖实时联网'
})

const allowedScriptModelIds = computed(() => {
  return isNewsStyle.value ? FORCED_MODEL_IDS : []
})

const supportsWebSearch = computed(() => {
  const id = formData.value.model
  const m = scriptModels.value.find(x => x.id === id)
  return Boolean(m?.supportsWebSearch ?? m?.supports_web_search)
})

const showManualRulesAuditButton = computed(() => {
  return import.meta.env.VITE_ENABLE_MANUAL_RULES_AUDIT === 'true'
})

const loadScriptModels = async () => {
  try {
    const response = await modelApi.getScriptModels()
    scriptModels.value = Array.isArray(response) ? response : (response?.data || [])
  } catch (e) {
    console.error('加载脚本模型失败:', e)
  }
}

// 加载脚本风格选项
const loadScriptStyles = async () => {
  try {
    const response = await modelApi.getScriptStyles()
    // request拦截器已经返回了data部分，所以response就是data数组
    scriptStyles.value = Array.isArray(response) ? response : (response?.data || [])
  } catch (error) {
    console.error('加载脚本风格失败:', error)
  }
}

// 模型变化处理
const handleModelChange = (modelId: string) => {
  formData.value.model = modelId
  // 切换到不支持联网搜索的模型时，自动关闭开关，避免误导
  if (!supportsWebSearch.value) {
    formData.value.enableSearch = false
  }
}

// 风格联动规则：全球简报型 × 科技快闪
watch(
  () => isNewsStyle.value,
  (on) => {
    if (on) {
      // 强制开启联网、并锁定模型范围
      formData.value.enableSearch = true
      if (!FORCED_MODEL_IDS.includes(formData.value.model)) {
        formData.value.model = FORCED_MODEL_IDS[0]
      }
    }
  },
  { immediate: true }
)

// 监听视频总时长和单个视频时长变化，验证总时长必须大于单个视频时长
watch(
  [() => formData.value.totalDuration, () => formData.value.segmentDuration],
  ([totalDuration, segmentDuration]) => {
    if (totalDuration && segmentDuration && totalDuration <= segmentDuration) {
      errorMessage.value = `视频总时长必须大于单个视频时长（${segmentDuration}秒）`
    } else {
      errorMessage.value = ''
    }
  }
)

// 输入框聚焦处理
const handleFocus = () => {
  isFocused.value = true
  errorMessage.value = ''
}

// 输入框失焦处理
const handleBlur = () => {
  isFocused.value = false
}

// 表单验证
const validateForm = (): boolean => {
  errorMessage.value = ''

  // 验证输入内容
  if (!inputContent.value || inputContent.value.trim().length === 0) {
    errorMessage.value = props.mode === 'inspiration'
      ? '请输入创意描述'
      : '请输入脚本内容'
    return false
  }

  // 验证脚本风格
  if (!formData.value.style) {
    errorMessage.value = '请选择脚本风格'
    return false
  }

  // 验证视频总时长
  if (!formData.value.totalDuration || formData.value.totalDuration <= 0) {
    errorMessage.value = '请输入视频总时长'
    return false
  }

  // 验证单个视频时长
  if (!formData.value.segmentDuration || formData.value.segmentDuration <= 0) {
    errorMessage.value = '请输入单个视频时长'
    return false
  }

  // 验证视频总时长必须大于单个视频时长
  if (formData.value.totalDuration <= formData.value.segmentDuration) {
    errorMessage.value = `视频总时长必须大于单个视频时长（${formData.value.segmentDuration}秒）`
    return false
  }

  // 验证模型选择
  if (!formData.value.model) {
    errorMessage.value = '请选择模型'
    return false
  }

  return true
}

// 提交处理
// 模拟进度更新
const simulateProgress = () => {
  const tips = [
    'AI正在分析您的创意',
    '正在构思脚本结构',
    '正在生成分镜内容',
    '正在优化脚本细节',
    '即将完成...'
  ]
  
  let progress = 0
  let tipIndex = 0
  
  const interval = setInterval(() => {
    if (progress < 90) {
      // 前90%模拟进度
      const increment = Math.random() * 15 + 5
      progress = Math.min(progress + increment, 90)
      loadingProgress.value = Math.floor(progress)
      
      // 更新提示文字
      const newTipIndex = Math.floor(progress / 20)
      if (newTipIndex !== tipIndex && newTipIndex < tips.length) {
        tipIndex = newTipIndex
        loadingTip.value = tips[tipIndex]
      }
    }
  }, 800)
  
  return interval
}

// 进度弹框相关
let progressDialogElement: HTMLElement | null = null
let progressInterval: number | null = null
let currentProgress = 0

const showProgressDialog = () => {
  // 创建进度弹框元素
  progressDialogElement = document.createElement('div')
  progressDialogElement.className = 'progress-dialog-overlay'
  progressDialogElement.innerHTML = `
    <div class="progress-dialog">
      <div class="progress-icon">
        <svg class="circular" viewBox="0 0 50 50">
          <circle class="path" cx="25" cy="25" r="20" fill="none"></circle>
        </svg>
      </div>
      <div class="progress-title">正在生成脚本</div>
      <div class="progress-bar-container">
        <div class="progress-bar-bg">
          <div class="progress-bar-fill"></div>
        </div>
        <div class="progress-percentage">0%</div>
      </div>
      <div class="progress-tip">AI 正在为您创作精彩内容...</div>
    </div>
  `
  document.body.appendChild(progressDialogElement)
  
  // 启动进度动画
  currentProgress = 0
  progressInterval = window.setInterval(() => {
    if (currentProgress < 90) {
      currentProgress += Math.random() * 3
      if (currentProgress > 90) currentProgress = 90
      updateProgress(currentProgress)
    }
  }, 500)
}

const updateProgress = (percentage: number) => {
  if (!progressDialogElement) return
  const fillBar = progressDialogElement.querySelector('.progress-bar-fill') as HTMLElement
  const percentText = progressDialogElement.querySelector('.progress-percentage') as HTMLElement
  if (fillBar) fillBar.style.width = `${percentage}%`
  if (percentText) percentText.textContent = `${Math.round(percentage)}%`
}

const hideProgressDialog = () => {
  if (progressInterval) {
    clearInterval(progressInterval)
    progressInterval = null
  }
  
  // 完成动画
  if (progressDialogElement) {
    updateProgress(100)
    setTimeout(() => {
      if (progressDialogElement) {
        progressDialogElement.classList.add('fade-out')
        setTimeout(() => {
          progressDialogElement?.remove()
          progressDialogElement = null
        }, 300)
      }
    }, 300)
  }
}

// 显示提示词弹窗
const showPromptDialog = async () => {
  try {
    // 响应拦截器已经返回 data.data，所以这里直接是 { prompt: "..." }
    const response = await configApi.getScriptPrompt()
    if (response && response.prompt) {
      promptContent.value = response.prompt
      promptDialogVisible.value = true
    } else {
      ElMessage.error('获取提示词失败')
    }
  } catch (error: any) {
    console.error('获取提示词失败:', error)
    ElMessage.error('获取提示词失败，请重试')
  }
}

// 显示风格编辑弹窗
const showStyleDialog = () => {
  // 深拷贝当前风格列表以便编辑
  editableStyles.value = JSON.parse(JSON.stringify(scriptStyles.value))
  styleDialogVisible.value = true
}

// 显示参考图对话框
const showReferenceDialog = () => {
  referenceDialogVisible.value = true
}

// 新增风格
const addNewStyle = () => {
  // 生成唯一的ID（使用时间戳）
  const timestamp = Date.now()
  const newStyle = {
    id: `custom_style_${timestamp}`,
    name: '',
    description: '',
    usage: ''
  }
  editableStyles.value.push(newStyle)
  ElMessage.success('已添加新风格，请编辑后保存')
}

// 删除风格
const deleteStyle = async (index: number) => {
  if (editableStyles.value.length <= 1) {
    ElMessage.warning('至少需要保留一个风格')
    return
  }

  try {
    await ElMessageBox.confirm(
      '确定要删除这个风格吗？删除后无法恢复。',
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    editableStyles.value.splice(index, 1)
    ElMessage.success('风格已删除，请点击保存按钮确认')
  } catch {
    // 用户取消删除
  }
}

// 保存风格
const saveStyles = async () => {
  // 验证风格数据
  for (const style of editableStyles.value) {
    if (!style.name || !style.name.trim()) {
      ElMessage.warning('风格名称不能为空')
      return
    }
    if (!style.description || !style.description.trim()) {
      ElMessage.warning('风格描述不能为空')
      return
    }
  }

  savingStyle.value = true
  try {
    // 调用API保存风格
    await modelApi.updateScriptStyles(editableStyles.value)
    
    // 更新本地风格列表
    scriptStyles.value = JSON.parse(JSON.stringify(editableStyles.value))
    
    ElMessage.success('风格保存成功')
    styleDialogVisible.value = false
  } catch (error: any) {
    console.error('保存风格失败:', error)
    ElMessage.error('保存风格失败，请重试')
  } finally {
    savingStyle.value = false
  }
}

// 保存提示词
const savePrompt = async () => {
  if (!promptContent.value.trim()) {
    ElMessage.warning('提示词不能为空')
    return
  }

  savingPrompt.value = true
  try {
    // 响应拦截器已经返回 data.data
    const response = await configApi.updateScriptPrompt(promptContent.value)
    if (response) {
      ElMessage.success('提示词保存成功')
      promptDialogVisible.value = false
    } else {
      ElMessage.error('保存失败')
    }
  } catch (error: any) {
    console.error('保存提示词失败:', error)
    ElMessage.error('保存提示词失败，请重试')
  } finally {
    savingPrompt.value = false
  }
}

const handleManualRulesAudit = async () => {
  const resolve_script_id = async (): Promise<number | null> => {
    // 1) 优先从 store 的 script 取
    const from_store = (projectStore.currentProject as any)?.script?.id
    if (from_store) return Number(from_store)

    // 2) 兼容：有些接口会返回 scripts 数组
    const from_scripts_array = (projectStore.currentProject as any)?.scripts?.[0]?.id
    if (from_scripts_array) return Number(from_scripts_array)

    // 3) 兼容：如果页面是通过 /projects/:id 进入但 store 丢失（刷新/直达），尝试回拉项目
    const project_id_param = (route.params as any)?.projectId
    const project_id = project_id_param ? Number(project_id_param) : NaN
    if (!Number.isNaN(project_id) && project_id > 0) {
      try {
        const project = await projectApi.getProject(project_id)
        const project_any = project as any
        if (project_any?.scripts?.length && !project_any?.script) {
          project_any.script = project_any.scripts[0]
        }
        projectStore.setCurrentProject(project_any)
        const from_fetched = (project_any as any)?.script?.id || (project_any as any)?.scripts?.[0]?.id
        if (from_fetched) return Number(from_fetched)
      } catch (e) {
        console.error('回拉项目失败，无法执行迭代:', e)
      }
    }

    return null
  }

  const script_id = await resolve_script_id()
  if (!script_id) {
    ElMessage.warning('当前页面未加载脚本：请先生成脚本，或从项目列表进入一个已有脚本的项目')
    return
  }

  auditingRules.value = true
  try {
    const res = await configApi.auditKfVideoRulesSnippet(Number(script_id))
    if (res?.changed) {
      ElMessage.success('提示词规则已迭代更新（后续生成会生效）')
    } else {
      ElMessage.success('审查完成：无需调整规则')
    }
  } catch (e: any) {
    console.error('手动迭代提示词失败:', e)
    ElMessage.error(e?.message || '手动迭代提示词失败')
  } finally {
    auditingRules.value = false
  }
}

const handleSubmit = async () => {
  if (!validateForm()) {
    return
  }

  loading.value = true
  errorMessage.value = ''
  loadingProgress.value = 0
  loadingText.value = '正在生成脚本...'
  loadingTip.value = 'AI正在分析您的创意'
  
  // 启动进度模拟
  const simInterval = simulateProgress()

  // 显示进度弹框
  showProgressDialog()

  try {
    const requestData: GenerateScriptRequest = {
      inspiration: inputContent.value.trim(),
      style: formData.value.style,
      totalDuration: formData.value.totalDuration!,
      segmentDuration: formData.value.segmentDuration!,
      enableSearch: formData.value.enableSearch
    }

    // 注意：生成新脚本时，不传递项目ID，让后端自动创建新项目
    // 这样可以确保每次生成脚本都会创建新项目，而不是在现有项目中创建新脚本
    // 如果需要在现有项目中创建新脚本，应该使用优化脚本功能

    // 生成脚本前，清空当前项目和脚本（避免显示旧数据）
    projectStore.setCurrentProject(null)
    
    // 调用脚本生成API，后端会自动创建项目和脚本
    const script = await scriptApi.generateScript(requestData, formData.value.model)
    // request 拦截器已经返回了 data.data，所以 script 就是 Script 对象

    // 从后端获取完整的项目信息（包含脚本）
    if (script?.projectId) {
      try {
        const project = await projectApi.getProject(script.projectId)
        // request拦截器已经返回了data部分，所以project就是项目对象
        
        // 处理脚本数据：如果返回的是 scripts 数组，取第一个作为 script
        const projectWithScript = project as any
        if (projectWithScript.scripts && Array.isArray(projectWithScript.scripts) && projectWithScript.scripts.length > 0) {
          projectWithScript.script = projectWithScript.scripts[0]
        } else if (!projectWithScript.script && script) {
          // 如果没有 script 字段，使用返回的脚本数据
          projectWithScript.script = script
        }
        
        projectStore.setCurrentProject(projectWithScript)
        projectStore.addProject(projectWithScript) // 添加到项目列表
        
        // 更新最近项目列表
        try {
          const response = await projectApi.getProjects({ page: 1, pageSize: 10 })
          projectStore.setProjects(response.items || [])
        } catch (error) {
          console.error('获取最近项目列表失败:', error)
        }
      } catch (error) {
        console.error('获取项目信息失败:', error)
        // 如果获取项目失败，使用脚本信息构建项目对象作为后备方案
        const projectName = inputContent.value.trim()
        const displayName = projectName.length > 10 ? projectName.substring(0, 10) + '...' : projectName
        const fallbackProject = {
          id: script.projectId,
          name: displayName || '未命名项目',
          description: inputContent.value.trim().substring(0, 500),
          status: 'script_generated' as const,
          conversationContent: inputContent.value.trim(),
          script: script,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString()
        }
        projectStore.setCurrentProject(fallbackProject)
        projectStore.addProject(fallbackProject as any)
      }
    }

    // 确保脚本内容正确更新到 store（强制更新，避免缓存问题）
    if (script && projectStore.currentProject) {
      // 强制更新脚本内容
      projectStore.updateScript(script)
      await nextTick()
    }

    // 完成进度到100%
    clearInterval(simInterval)
    loadingProgress.value = 100
    loadingTip.value = '生成完成!'
    
    // 隐藏进度弹框
    hideProgressDialog()
    
    // 短暂延迟后再跳转
    await new Promise(resolve => setTimeout(resolve, 500))

    ElMessage.success('脚本生成成功')
    emit('success', script)

    // 跳转到脚本生成页面，传递项目ID作为路由参数
    // 等待 store 更新完成
    await nextTick()
    await nextTick()
    
    // 额外等待，确保项目列表更新完成
    await new Promise(resolve => setTimeout(resolve, 100))
    
    const newProjectId = projectStore.currentProject?.id
    
    // 传递项目ID作为路由参数，确保页面正确加载新项目的数据
    if (newProjectId) {
      await router.push({ 
        name: 'ScriptGenerationStep',
        params: { projectId: newProjectId.toString() }
      })
    } else {
      // 如果没有项目ID，仍然跳转但不传递参数（后备方案）
      await router.push({ name: 'ScriptStart' }) // 或者其他合适的默认页
    }
  } catch (error: any) {
    // 隐藏进度弹框
    hideProgressDialog()
    
    console.error('生成脚本失败:', error)
    console.error('错误详情:', {
      message: error?.message,
      response: error?.response,
      data: error?.response?.data,
      detail: error?.response?.data?.detail
    })
    
    // 优先显示后端返回的详细错误信息
    let errorMsg = '操作失败，请重试'
    if (error?.response?.data?.detail) {
      errorMsg = error.response.data.detail
    } else if (error?.response?.data?.message) {
      errorMsg = error.response.data.message
    } else if (error?.message) {
      errorMsg = error.message
    }
    
    errorMessage.value = errorMsg
    ElMessage.error(errorMsg)
    emit('error', errorMsg)
  } finally {
    // 清理进度定时器
    clearInterval(simInterval)
    loading.value = false
    loadingProgress.value = 0
  }
}

// 一键生成处理
const handleOneClickGenerate = async () => {
  if (!validateForm()) {
    return
  }

  oneClickLoading.value = true
  errorMessage.value = ''

  try {
    // 清空当前项目
    projectStore.setCurrentProject(null)

    // 参考图已经在store中，不需要再次设置

    // 立即跳转到一键生成页面，使用特殊的 projectId 'new' 表示新建
    await router.push({
      name: 'OneClickGenerate',
      params: { projectId: 'new' },  // 使用 'new' 作为占位符
      query: { 
        inspiration: inputContent.value.trim(),
        style: formData.value.style,
        totalDuration: formData.value.totalDuration?.toString(),
        segmentDuration: formData.value.segmentDuration?.toString(),
        model: formData.value.model,
        enableSearch: formData.value.enableSearch ? 'true' : 'false',
        autoStart: 'true'  // 标记自动开始生成
      }
    })
  } catch (error: any) {
    console.error('跳转失败:', error)
    ElMessage.error('跳转失败，请重试')
  } finally {
    oneClickLoading.value = false
  }
}

// 监听 initialContent 的变化
watch(() => props.initialContent, (newValue) => {
  if (newValue) {
    inputContent.value = newValue
  }
})

// 初始化
onMounted(() => {
  loadScriptStyles()
  loadScriptModels()
})
</script>

<style>
/* 进度弹框样式 */
.progress-dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 9999;
  animation: fadeIn 0.3s ease-out;
  backdrop-filter: blur(4px);
}

.progress-dialog-overlay.fade-out {
  animation: fadeOut 0.3s ease-out;
  opacity: 0;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes fadeOut {
  from {
    opacity: 1;
  }
  to {
    opacity: 0;
  }
}

.progress-dialog {
  background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
  border-radius: 16px;
  padding: 40px 50px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  min-width: 400px;
  text-align: center;
  animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
  from {
    transform: translateY(-30px) scale(0.9);
    opacity: 0;
  }
  to {
    transform: translateY(0) scale(1);
    opacity: 1;
  }
}

.progress-icon {
  width: 60px;
  height: 60px;
  margin: 0 auto 20px;
}

.circular {
  width: 100%;
  height: 100%;
  animation: rotate 2s linear infinite;
}

@keyframes rotate {
  100% {
    transform: rotate(360deg);
  }
}

.path {
  stroke-dasharray: 90, 150;
  stroke-dashoffset: 0;
  stroke: #409eff;
  stroke-width: 2;
  stroke-linecap: round;
  animation: dash 1.5s ease-in-out infinite;
}

@keyframes dash {
  0% {
    stroke-dasharray: 1, 150;
    stroke-dashoffset: 0;
  }
  50% {
    stroke-dasharray: 90, 150;
    stroke-dashoffset: -35;
  }
  100% {
    stroke-dasharray: 90, 150;
    stroke-dashoffset: -124;
  }
}

.progress-title {
  font-size: 20px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 24px;
}

.progress-bar-container {
  margin-bottom: 16px;
}

.progress-bar-bg {
  width: 100%;
  height: 8px;
  background: #e4e7ed;
  border-radius: 4px;
  overflow: hidden;
  position: relative;
  margin-bottom: 8px;
}

.progress-bar-fill {
  height: 100%;
  width: 0%;
  background: linear-gradient(90deg, #409eff 0%, #67c23a 100%);
  border-radius: 4px;
  transition: width 0.5s ease-out;
  position: relative;
  overflow: hidden;
}

.progress-bar-fill::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.3),
    transparent
  );
  animation: shimmer 1.5s infinite;
}

@keyframes shimmer {
  0% {
    transform: translateX(-100%);
  }
  100% {
    transform: translateX(100%);
  }
}

.progress-percentage {
  font-size: 14px;
  color: #606266;
  font-weight: 500;
}

.progress-tip {
  font-size: 14px;
  color: #909399;
  font-style: italic;
}
</style>

<style scoped>
.script-optimization {
  width: 100%;
  height: 100%;
  background-color: #3f3f3f;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 0;
  margin: 0;
}

.script-optimization--inspiration {
  height: auto;
  background-color: transparent;
  justify-content: flex-start;
  align-items: stretch;
}

.script-optimization-card {
  width: 1000px;
  min-height: 270px;
  background-color: #ffffff;
  border: 1px solid #cccccc;
  border-radius: 10px;
  padding: 0;
  position: relative;
  display: flex;
  flex-direction: column;
  overflow: visible;
}

.script-optimization--inspiration .script-optimization-card {
  width: 100%;
  max-width: none;
}

.input-section {
  flex: 1;
  padding: 24px 24px 16px 24px;
  display: flex;
  align-items: flex-start;
  min-height: 180px;
}

.script-input {
  width: 100%;
  height: 100%;
}

.script-input :deep(.el-textarea) {
  height: 100%;
}

.script-input :deep(.el-textarea__inner) {
  font-family: 'PingFangSC-Regular', 'PingFang SC', sans-serif;
  font-size: 14px;
  line-height: 1.6;
  border: none;
  background: transparent;
  padding: 0;
  color: #333333;
  resize: none;
  box-shadow: none;
  height: 100% !important;
  min-height: auto;
}

.script-input :deep(.el-textarea__inner)::placeholder {
  color: #cccccc;
  font-family: 'PingFangSC-Regular', 'PingFang SC', sans-serif;
}

.script-input :deep(.el-textarea__inner):focus {
  border: none;
  box-shadow: none;
  outline: none;
}

.script-input :deep(.el-input__count) {
  display: none;
}

.control-panel {
  padding: 0 24px 24px 24px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.control-row {
  display: flex;
  gap: 10px;
  align-items: center;
}

.control-row-first {
  justify-content: flex-start;
  flex-wrap: wrap;
}

.control-row-second {
  justify-content: flex-end;
}

.control-select {
  height: 32px;
  flex-shrink: 0;
  width: 150px; /* 默认宽度 */
}

/* 脚本风格选择器 - 第一个select */
.control-row > .control-select:nth-of-type(1) {
  width: 150px;
}

/* 视频总时长输入框 - 第二个元素 */
.control-row > .control-input:nth-of-type(1) {
  width: 130px;
}

/* 模型选择器 - 第三个select */
.control-row > .control-select:nth-of-type(2) {
  width: 120px;
}

.control-select :deep(.el-input__wrapper) {
  background-color: #f5f5f5;
  border: 1px solid #cccccc;
  border-radius: 4px;
  box-shadow: none;
  padding: 0 11px;
  height: 32px;
}

.control-select :deep(.el-input__wrapper.is-disabled) {
  background-color: #f5f5f5;
  border-color: #cccccc;
  cursor: not-allowed;
}

.control-select :deep(.el-input__inner.is-disabled) {
  color: #666666;
  -webkit-text-fill-color: #666666;
}

.control-select :deep(.el-input__inner) {
  font-family: 'PingFangSC-Regular', 'PingFang SC', sans-serif;
  font-size: 12px;
  color: #999999;
  height: 32px;
  line-height: 32px;
}

.control-select :deep(.el-input__inner)::placeholder {
  color: #cccccc;
}

.control-select :deep(.el-input__suffix) {
  height: 32px;
  line-height: 32px;
}

.control-select :deep(.el-select__caret) {
  color: #cccccc;
  font-size: 12px;
}

.control-input {
  height: 32px;
  width: 100px;
  flex-shrink: 0;
}

.control-input :deep(.el-input__wrapper) {
  background-color: #ffffff;
  border: 1px solid #cccccc;
  border-radius: 4px;
  box-shadow: none !important;
  padding: 0 11px;
  height: 32px;
}

.control-input :deep(.el-input__wrapper.is-focus) {
  box-shadow: none !important;
  border-color: #cccccc;
}

.control-input :deep(.el-input__wrapper:hover) {
  box-shadow: none !important;
}

.control-input :deep(.el-input__inner) {
  font-family: 'PingFangSC-Regular', 'PingFang SC', sans-serif;
  font-size: 12px;
  color: #333333;
  height: 32px;
  line-height: 32px;
  text-align: left;
  box-shadow: none !important;
}

.control-input :deep(.el-input__inner:focus) {
  box-shadow: none !important;
  outline: none !important;
}

.control-input :deep(.el-input__inner)::placeholder {
  color: #cccccc;
}

.control-input :deep(.el-input-group__append) {
  background-color: #ffffff;
  border: none;
  border-left: 1px solid #cccccc;
  color: #666666;
  font-size: 12px;
  padding: 0 11px;
  font-family: 'PingFangSC-Regular', 'PingFang SC', sans-serif;
}

.prompt-button {
  width: 80px;
  height: 32px;
  background-color: #ffffff;
  border: 1px solid #cccccc;
  border-radius: 4px;
  font-family: 'PingFangSC-Regular', 'PingFang SC', sans-serif;
  font-size: 12px;
  font-weight: 400;
  color: #666666;
  padding: 0;
  flex-shrink: 0;
  transition: all 0.3s;
}

.prompt-button:hover {
  border-color: #00aaaa;
  color: #00aaaa;
}

.web-search-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  padding: 0 8px;
  border: 1px solid #cccccc;
  border-radius: 4px;
  background: #ffffff;
  flex-shrink: 0;
}

.web-search-label {
  font-size: 12px;
  color: #666666;
  line-height: 1;
}

.web-search-toggle :deep(.el-switch) {
  --el-switch-on-color: #00aaaa;
}

.reference-button {
  min-width: 120px;
  height: 32px;
  background-color: #ffffff;
  border: 1px solid #cccccc;
  border-radius: 4px;
  font-family: 'PingFangSC-Regular', 'PingFang SC', sans-serif;
  font-size: 12px;
  color: #333333;
  padding: 0 12px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 6px;
}

.reference-button:hover {
  border-color: #00aaaa;
  color: #00aaaa;
}

.style-button {
  width: 80px;
  height: 32px;
  background-color: #ffffff;
  border: 1px solid #cccccc;
  border-radius: 4px;
  font-family: 'PingFangSC-Regular', 'PingFang SC', sans-serif;
  font-size: 12px;
  font-weight: 400;
  color: #666666;
  padding: 0;
  flex-shrink: 0;
  transition: all 0.3s;
}

.style-button:hover {
  border-color: #00aaaa;
  color: #00aaaa;
}

.action-button {
  width: 100px;
  height: 32px;
  background-color: #00aaaa;
  border: none;
  border-radius: 4px;
  font-family: 'PingFangSC-Regular', 'PingFang SC', sans-serif;
  font-size: 12px;
  font-weight: 400;
  color: #ffffff;
  padding: 0;
  flex-shrink: 0;
  transition: background-color 0.3s;
}

.action-button:hover:not(:disabled) {
  background-color: #009999;
}

.action-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.one-click-button {
  height: 32px;
  background: linear-gradient(135deg, #ff9500 0%, #ff5e00 100%);
  border: none;
  border-radius: 4px;
  font-family: 'PingFangSC-Regular', 'PingFang SC', sans-serif;
  font-size: 12px;
  font-weight: 400;
  color: #ffffff;
  padding: 0 16px;
  flex-shrink: 0;
  transition: all 0.3s;
  display: flex;
  align-items: center;
  gap: 6px;
}

.one-click-button:hover:not(:disabled) {
  background: linear-gradient(135deg, #ffaa33 0%, #ff7733 100%);
}

.one-click-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.error-message {
  padding: 0 24px 12px 24px;
}

.error-message :deep(.el-alert) {
  border-radius: 4px;
  font-size: 12px;
}

/* 下拉选项样式 */
:deep(.el-select-dropdown__item) {
  font-family: 'PingFangSC-Regular', 'PingFang SC', sans-serif;
  font-size: 12px;
  color: #333333;
}

:deep(.el-select-dropdown__item:hover) {
  background-color: #f5f7fa;
}

:deep(.el-select-dropdown__item.is-selected) {
  color: #00aaaa;
  background-color: #e6f7f7;
}

/* 响应式设计 */
@media (max-width: 1200px) {
  .script-optimization-card {
    width: 90%;
    max-width: 800px;
  }
}

@media (max-width: 768px) {
  .script-optimization-card {
    width: 95%;
    min-height: auto;
  }

  .input-section {
    min-height: 150px;
  }

  .control-row {
    flex-wrap: wrap;
    gap: 8px;
  }

  .control-row-first {
    justify-content: flex-start;
    flex-wrap: wrap;
  }

  .control-row-second {
    justify-content: flex-end;
  }

  .control-select,
  .control-input {
    width: calc(50% - 4px);
  }

  .prompt-button {
    width: calc(50% - 4px);
    margin-left: 0;
    margin-right: 0;
  }

  .action-button {
    width: calc(50% - 4px);
    margin-left: 0;
  }
}

/* 提示词弹窗样式 */
.prompt-dialog :deep(.el-dialog__body) {
  padding: 20px;
}

.prompt-dialog-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.prompt-textarea :deep(.el-textarea__inner) {
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.6;
  resize: vertical;
}

.prompt-tips {
  margin-top: 8px;
}

.variable-list {
  margin: 8px 0 0 0;
  padding-left: 20px;
  list-style: disc;
}

.variable-list li {
  margin: 4px 0;
  font-size: 13px;
  line-height: 1.6;
}

.variable-list code {
  background-color: #f5f5f5;
  padding: 2px 6px;
  border-radius: 3px;
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: 12px;
  color: #e83e8c;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

/* 风格编辑弹窗样式 */
.style-dialog :deep(.el-dialog__body) {
  padding: 20px;
}

.style-dialog-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.style-list-header {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 12px;
}

.style-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
  max-height: 500px;
  overflow-y: auto;
  padding: 10px;
}

.style-item {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 16px;
  background-color: #f9f9f9;
  transition: all 0.3s;
}

.style-item:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.style-item-header {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 12px;
}

.style-name-input {
  flex: 1;
}

.style-name-input :deep(.el-input__wrapper) {
  font-weight: 600;
  font-size: 14px;
}

.style-description-input {
  margin-top: 12px;
}

.style-usage-input {
  margin-top: 12px;
}

.style-description-input :deep(.el-textarea__inner) {
  font-family: 'PingFangSC-Regular', 'PingFang SC', sans-serif;
  font-size: 13px;
  line-height: 1.6;
  resize: vertical;
}

.style-tips {
  margin-top: 8px;
}

.style-tips ul {
  margin: 8px 0 0 0;
  padding-left: 20px;
  list-style: disc;
}

.style-tips li {
  margin: 4px 0;
  font-size: 13px;
  line-height: 1.6;
}

/* 全屏加载遮罩 */
/* 全屏 loading 样式已移除，只保留顶部进度条 */
</style>

