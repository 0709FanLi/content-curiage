<template>
  <div class="script-editor figma-script">
    <div class="content">
      <div class="content-inner">
        <!-- 用户输入卡片（默认折叠） -->
        <div class="user-input-row">
          <div class="user-input-card">
            <div class="user-input-text" :class="{ collapsed: user_input_collapsed }">
              {{ latest_user_message?.content || '' }}
            </div>
            <button
              class="collapse-btn"
              type="button"
              :title="user_input_collapsed ? '展开' : '收起'"
              @click="user_input_collapsed = !user_input_collapsed"
            >
              <img :src="user_input_collapsed ? arrowDownIcon : arrowUpIcon" alt="" />
            </button>
              </div>
              </div>

        <!-- 顶部操作：重新生成 / 编辑（位置按 Figma 9:794） -->
        <div class="top-actions">
          <button
            class="text-action"
            type="button"
            @click="handleRegenerate"
            :disabled="regenerating || optimizing || is_completed_status"
          >
            <el-icon><Refresh /></el-icon>
            <span>重新生成</span>
          </button>
          <button
            v-if="!isEditingScript"
            class="text-action"
            type="button"
            @click="startEdit"
            :disabled="optimizing || is_completed_status"
          >
            <el-icon><Edit /></el-icon>
            <span>编辑</span>
          </button>
          <template v-else>
            <button class="text-action danger" type="button" @click="cancelEdit">
              <span>取消</span>
            </button>
            <button class="text-action primary" type="button" @click="saveEdit">
              <span>保存</span>
            </button>
          </template>
        </div>

        <!-- 脚本展示（可折叠/展开，由 ScriptPrettyView 内部实现） -->
        <div class="script-blocks">
          <div v-if="latest_ai_message?.isGenerating" class="loading-card">
            {{ latest_ai_message.content }}
                </div>
                <template v-else>
                  <textarea
              v-if="isEditingScript"
                    v-model="editingScriptContent"
              class="script-edit-textarea"
                    placeholder="编辑脚本内容..."
                    @input="adjustEditTextareaHeight"
                    ref="editTextareaRef"
                  />
                    <ScriptPrettyView
              v-else-if="latest_ai_message && looksLikeScript(latest_ai_message.content)"
              :content="latest_ai_message.content"
                    />
            <div v-else class="empty-script">暂无脚本内容</div>
                </template>
                  </div>

        <!-- DEV 可观测：参考图是否参与脚本生成（视觉解析注入） -->
        <div
          v-if="isDev && vision_analysis_meta"
          class="vision-observe"
        >
          <span class="label">参考图解析：</span>
          <span
            class="status"
            :class="vision_analysis_meta.status"
          >
            {{ vision_analysis_label }}
          </span>
          <span class="extra" v-if="typeof vision_analysis_meta.guidanceLength === 'number'">
            （guidanceLen={{ vision_analysis_meta.guidanceLength }}）
          </span>
          <span class="extra" v-if="vision_analysis_meta.errorMessage">
            原因：{{ vision_analysis_meta.errorMessage }}
          </span>
        </div>

        <!-- 生成关键帧区域（位置按 Figma 9:873） -->
        <div
          v-if="!isEditingScript"
          class="keyframe-panel"
         
        >
          <div class="keyframe-panel-row">
            <el-select
              v-model="selectedModel"
              placeholder="选择模型"
              class="keyframe-select"
              @change="handleModelChange"
            >
              <el-option
                v-for="model in imageModels"
                :key="model.id"
                :label="model.name"
                :value="model.id"
              />
            </el-select>

            <button
                v-for="ratio in aspectRatios"
                :key="ratio"
              class="pill"
              type="button"
              :class="{ active: selectedAspectRatio === ratio }"
              @click="selectedAspectRatio = ratio"
            >
              {{ ratio }}
            </button>

            <button
              v-for="q in (imageModels.find(m => m.id === selectedModel)?.has_quality_selector ? qualities : [])"
              :key="q"
              class="pill"
              type="button"
              :class="{ active: selectedQuality === q }"
              @click="selectedQuality = q"
            >
              {{ q }}
            </button>
          </div>
          <button
            class="generate-keyframes-btn"
            type="button"
           
              :disabled="!canGenerateKeyframes"
              @click="onGenerateKeyframes"
            >
              生成关键帧
          </button>
          <button
              v-if="hasKeyframes"
            class="next-step-btn"
            type="button"
              @click="goToKeyframesPage"
            >
              下一步
          </button>
          </div>
        </div>
    </div>

    <!-- 底部消息输入（发送消息重新生成脚本） -->
        <div class="chat-input">
      <div class="chat-input-inner">
          <el-input
            v-model="optimizationInput"
            type="textarea"
          placeholder="输入你的消息..."
          class="chat-textarea"
            :rows="2"
            :maxlength="3000"
          @keyup.ctrl.enter="() => handleOptimize()"
          :disabled="is_completed_status"
          />
        <button
          class="send-btn"
          type="button"
            :disabled="is_completed_status || !optimizationInput.trim() || !selectedOptimizeModel || optimizing"
            @click="() => handleOptimize()"
          >
          <img :src="sendIcon" alt="" />
        </button>
      </div>
    </div>

    <!-- 参考图管理弹窗 -->
    <el-dialog
      v-model="referenceDialogVisible"
      title="管理参考图"
      width="70%"
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
import { ref, computed, watch, nextTick, onMounted, onUpdated, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElIcon } from 'element-plus'
import { Close, Check, Edit, Refresh } from '@element-plus/icons-vue'
import { modelApi, scriptApi, projectApi, keyframeApi } from '@/api'
import { useProjectStore } from '@/stores'
import ReferenceImageManager from '@/components/script-generation/ReferenceImageManager.vue'
import ScriptPrettyView from '@/components/common/ScriptPrettyView.vue'

import arrowDownIcon from '@/assets/icons/arrow-bottom.png'
import arrowUpIcon from '@/assets/icons/arrow-top.png'
import sendIcon from '@/assets/icons/send.png'

const looksLikeScript = (text: string) => {
  if (!text) return false
  // 全局移除“第0帧”后：脚本通常包含时间段与结构化字段（关键帧/视频/口播文案）。
  // 兼容历史脚本仍可能包含“第0帧（已废弃文本）”，但不再作为强制条件。
  const hasTime = /\(\s*\d+\s*-\s*\d+\s*s\s*\)/.test(text)
  const hasFields = /(关键帧|视频|口播文案)[:：]/.test(text)
  return hasTime || hasFields
}

const props = defineProps<{
  projectId: number | null
}>()

const emit = defineEmits(['generate-keyframes'])

const router = useRouter()
const projectStore = useProjectStore()
const is_completed_status = computed(() => projectStore.projectCompletionStatus === 'completed')

const user_input_collapsed = ref<boolean>(true)

const latest_user_message = computed(() => {
  const userMsgs = messages.value.filter(m => m.role === 'user')
  return userMsgs.length ? userMsgs[userMsgs.length - 1] : null
})

const latest_ai_message = computed(() => {
  const aiMsgs = messages.value.filter(m => m.role === 'ai')
  return aiMsgs.length ? aiMsgs[aiMsgs.length - 1] : null
})

// 进度条相关状态
const loading = ref(false)
const loadingProgress = ref(0)
const loadingText = ref('正在生成脚本...')
const loadingTip = ref('AI正在分析您的创意')
let progressDialogElement: HTMLElement | null = null
let progressInterval: ReturnType<typeof setInterval> | null = null
let simInterval: ReturnType<typeof setInterval> | null = null

// 进度条方法
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
      const increment = Math.random() * 15 + 5
      progress = Math.min(progress + increment, 90)
      loadingProgress.value = Math.floor(progress)
      
      const newTipIndex = Math.floor(progress / 20)
      if (newTipIndex !== tipIndex && newTipIndex < tips.length) {
        tipIndex = newTipIndex
        loadingTip.value = tips[tipIndex]
      }
    }
  }, 800)
  
  return interval
}

const showProgressDialog = () => {
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
  
  let currentProgress = 0
  progressInterval = setInterval(() => {
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

onUnmounted(() => {
  if (progressInterval) clearInterval(progressInterval)
  if (simInterval) clearInterval(simInterval)
  if (progressDialogElement) progressDialogElement.remove()
})


// 消息类型定义
interface Message {
  id: string
  role: 'user' | 'ai'
  content: string
  isGenerating?: boolean
  isCollapsed?: boolean
  isOverflow?: boolean
  height?: number
  collapseInitialized?: boolean
}

const COLLAPSE_HEIGHT_PX = 200

// 消息列表
const messages = ref<Message[]>([])

const update_message_overflow = (msg: Message): void => {
  if (msg.isGenerating) return
  const container = document.getElementById(`msg-${msg.id}`)
  if (!container) return

  // 以 message-body 的真实高度作为判定标准（包含 padding）
  const contentHeight = container.scrollHeight
  msg.height = contentHeight
  msg.isOverflow = contentHeight > COLLAPSE_HEIGHT_PX

  // 默认策略：首次初始化时，超过阈值才折叠；否则展开
  // 一旦用户手动展开/收起，不再强制覆盖
  if (!msg.collapseInitialized) {
    msg.isCollapsed = Boolean(msg.isOverflow)
    msg.collapseInitialized = true
  } else if (!msg.isOverflow) {
    // 内容不溢出时始终展开并隐藏按钮
    msg.isCollapsed = false
  }
}

// 监听消息列表变化，计算高度和滚动
watch(messages, () => {
  nextTick(() => {
    messages.value.forEach(msg => {
      update_message_overflow(msg)
    })
    scrollToBottom()
  })
}, { deep: true })

const scrollToBottom = () => {
  setTimeout(() => {
    const conversationArea = document.querySelector('.conversation-area')
    if (conversationArea) {
      conversationArea.scrollTop = conversationArea.scrollHeight
    }
  }, 100)
}

// 消息内容 (保留 scriptContent 用于兼容 store 和 edit)
const scriptContent = computed(() => {
  const aiMsgs = messages.value.filter(m => m.role === 'ai' && !m.isGenerating)
  return aiMsgs.length > 0 ? aiMsgs[aiMsgs.length - 1].content : ''
})
const userInputMessage = computed(() => {
  const userMsgs = messages.value.filter(m => m.role === 'user')
  return userMsgs.length > 0 ? userMsgs[0].content : ''
})

const optimizationInputFocused = ref<boolean>(false)

// 编辑状态 (针对最后一条 AI 消息)
const isEditingScript = ref<boolean>(false)
const editingScriptContent = ref<string>('')
const editTextareaRef = ref<HTMLTextAreaElement | null>(null)
const regenerating = ref<boolean>(false)

// 模型相关
const selectedModel = ref<string>('')
const imageModels = ref<any[]>([])
const selectedAspectRatio = ref<string>('')
const selectedQuality = ref<string>('')
const aspectRatios = ref<string[]>([])
const qualities = ref<string[]>([])

const isDev = import.meta.env.DEV
const vision_analysis_meta = computed<any>(() => {
  return (projectStore.currentScript as any)?.visionAnalysis || null
})
const vision_analysis_label = computed(() => {
  const m = vision_analysis_meta.value
  if (!m) return ''
  const status = String(m.status || '')
  if (status === 'skipped') return '未启用（未上传参考图）'
  if (status === 'success') return '已使用（已注入脚本生成）'
  if (status === 'empty') return '解析为空（未注入）'
  if (status === 'failed') return '解析失败（未注入）'
  return status
})

const ALLOWED_ASPECT_RATIOS = ['9:16', '16:9'] as const

const filter_aspect_ratios = (ratios: string[] = []): string[] => {
  const allow = new Set<string>(ALLOWED_ASPECT_RATIOS as unknown as string[])
  return ratios.filter(r => allow.has(r))
}

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

// 优化输入
const optimizationInput = ref<string>('')
const selectedOptimizeModel = ref<string>('')
const optimizing = ref<boolean>(false)
const enableSearchOptimize = ref<boolean>(false)
const scriptModels = ref<Array<{ id: string; name: string; supports_web_search?: boolean; supportsWebSearch?: boolean }>>([])

const supportsWebSearchOptimize = computed(() => {
  const id = selectedOptimizeModel.value
  const m = scriptModels.value.find(x => x.id === id)
  return Boolean(m?.supportsWebSearch ?? m?.supports_web_search)
})

const canGenerateKeyframes = computed(() => {
  // 只有“最终成片已生成(completed)”才锁定生成关键帧，避免覆盖已完成项目
  if (is_completed_status.value) return false
  if (!selectedModel.value || !selectedAspectRatio.value || !scriptContent.value.trim()) {
    return false
  }
  const currentModel = imageModels.value.find(m => m.id === selectedModel.value)
  if (currentModel?.has_quality_selector && !selectedQuality.value) {
    return false
  }
  return true
})

// 方法
const calculateMessageHeight = () => {
  nextTick(() => {
    messages.value.forEach(msg => {
      update_message_overflow(msg)
    })
  })
}

const adjustEditTextareaHeight = () => {
  nextTick(() => {
    if (editTextareaRef.value) {
      // 先重置高度以获取准确的 scrollHeight
      editTextareaRef.value.style.height = '0'
      // 计算内容高度，至少保持 400px 以保证编辑体验
      const contentHeight = Math.max(editTextareaRef.value.scrollHeight, 400)
      editTextareaRef.value.style.height = `${contentHeight}px`
    }
  })
}

const startEdit = () => {
  if (is_completed_status.value) {
    ElMessage.warning('当前项目已完成（completed），脚本不可修改')
    return
  }
  isEditingScript.value = true
  editingScriptContent.value = scriptContent.value
  
  // 展开当前正在编辑的消息
  const lastAiMsg = messages.value.filter(m => m.role === 'ai' && !m.isGenerating).pop()
  if (lastAiMsg) {
    const msg = messages.value.find(m => m.id === lastAiMsg.id)
    if (msg) {
      msg.isCollapsed = false
    }
  }

  nextTick(() => {
    adjustEditTextareaHeight()
    const focus = () => editTextareaRef.value?.focus()
    focus()
    // 多次尝试聚焦，确保在动画或渲染完成后生效
    setTimeout(focus, 50)
    setTimeout(focus, 100)
    setTimeout(focus, 200)
  })
}

const cancelEdit = () => {
  isEditingScript.value = false
  editingScriptContent.value = ''
}

const saveEdit = async () => {
  if (is_completed_status.value) {
    ElMessage.warning('当前项目已完成（completed），脚本不可修改')
    return
  }
  if (!editingScriptContent.value.trim()) {
    ElMessage.warning('脚本内容不能为空')
    return
  }
  
  try {
    const scriptId = projectStore.currentScript?.id
    if (scriptId) {
      await scriptApi.updateScript(scriptId, { content: editingScriptContent.value })
      
      // 更新最后一条 AI 消息
      const aiMsgs = messages.value.filter(m => m.role === 'ai' && !m.isGenerating)
      if (aiMsgs.length > 0) {
        const lastMsg = aiMsgs[aiMsgs.length - 1]
        const index = messages.value.findIndex(m => m.id === lastMsg.id)
        if (index !== -1) {
          messages.value[index].content = editingScriptContent.value
        }
      }
      
      if (projectStore.currentScript) {
         projectStore.currentScript.content = editingScriptContent.value
      }
      
      ElMessage.success('脚本已更新')
    }
    isEditingScript.value = false
    editingScriptContent.value = ''
    calculateMessageHeight()
  } catch (error: any) {
    ElMessage.error(error?.message || '保存失败')
  }
}

const handleRegenerate = async () => {
  // 重新生成基于最后一条用户的输入
  const userMsgs = messages.value.filter(m => m.role === 'user')
  const lastUserMsg = userMsgs.length > 0 ? userMsgs[userMsgs.length - 1].content : ''
  
  if (!lastUserMsg || !selectedOptimizeModel.value) {
    ElMessage.warning('无法重新生成，缺少创意描述或模型')
    return
  }
  
  // 获取原始参数
  const script = projectStore.currentScript
  const style = script?.style || ''
  const totalDuration = script?.totalDuration
  const segmentDuration = script?.segmentDuration
  
  // 构建Prompt
  let prompt = `${lastUserMsg}`
  const constraints = []
  if (style) constraints.push(`风格：${style}`)
  if (totalDuration) constraints.push(`总时长：${totalDuration}秒`)
  if (segmentDuration) constraints.push(`单片段时长：${segmentDuration}秒`)
  
  if (constraints.length > 0) {
    prompt += `\n\n(重新生成要求：${constraints.join('，')})`
  }
  
  regenerating.value = true
  try {
    await handleOptimize(prompt)
  } finally {
    regenerating.value = false
  }
}

const loadImageModels = async () => {
  try {
    const response = await modelApi.getImageModels()
    const models = Array.isArray(response) ? response : (response?.data || [])
    imageModels.value = models
    if (models.length > 0) {
      // 检查当前选中的模型是否有效（必须在可用模型列表中）
      const currentModelValid = selectedModel.value && models.some(m => m.id === selectedModel.value)
      
      if (!currentModelValid) {
        // 当前模型无效，选择默认模型
        // 优先 Seedream 4.5（火山方舟），否则回退到第一个模型（后端已排好序）
        const seedream = models.find(m => m.id === 'doubao-seedream-4-5-251128')
        selectedModel.value = (seedream?.id || models[0].id) as string
      }

      // 无论是否切换模型，都需要根据“已选模型”刷新比例/清晰度选项
      // 否则在从关键帧页返回脚本页时，selectedModel 有效但 aspectRatios 仍为空，导致比例按钮不显示
        await handleModelChange()
    }
  } catch (error) {
    console.error('加载图片模型列表失败:', error)
    ElMessage.error('加载模型列表失败')
  }
}

const handleModelChange = async () => {
  const modelId = selectedModel.value
  if (!modelId) {
    aspectRatios.value = []
    qualities.value = []
    selectedAspectRatio.value = ''
    selectedQuality.value = ''
    return
  }
  const model = imageModels.value.find(m => m.id === modelId)
  if (model) {
    aspectRatios.value = filter_aspect_ratios(model.aspect_ratios || [])
    qualities.value = model.qualities || []
    if (!selectedAspectRatio.value || !aspectRatios.value.includes(selectedAspectRatio.value)) {
      selectedAspectRatio.value = aspectRatios.value[0] || ''
    }
    if (qualities.value.length > 0 && !selectedQuality.value) selectedQuality.value = qualities.value[0]
  }
}

const hasKeyframes = computed(() => {
  return projectStore.currentKeyframes && projectStore.currentKeyframes.length > 0
})

const goToKeyframesPage = () => {
  if (props.projectId) {
    router.push({
      name: 'KeyframeGeneration',
      params: { projectId: props.projectId.toString() }
    })
  }
}

const handleOptimize = async (manualContent?: string) => {
  const contentToUse = typeof manualContent === 'string' ? manualContent : optimizationInput.value
  
  if (!contentToUse.trim() && !selectedOptimizeModel.value) {
    ElMessage.warning('请选择模型并输入创意描述')
    return
  }
  if (!projectStore.currentScript?.id) {
    ElMessage.warning('请先创建脚本')
    return
  }
  
  optimizing.value = true
  
  // 添加用户消息（默认折叠）
  if (contentToUse.trim()) {
    messages.value.push({
      id: `user-${Date.now()}`,
      role: 'user',
      content: contentToUse,
      isCollapsed: true
    })
  }

  // 添加AI Loading消息
  const loadingMsgId = `ai-loading-${Date.now()}`
  messages.value.push({
    id: loadingMsgId,
    role: 'ai',
    content: '正在生成脚本...',
    isGenerating: true,
    isCollapsed: false
  })
  
  scrollToBottom()

  try {
    const creativeText = contentToUse
    
    // 如果已有脚本内容，先保存
    const lastAiMsg = messages.value.slice().reverse().find(m => m.role === 'ai' && !m.isGenerating && m.id !== loadingMsgId)
    if (lastAiMsg && projectStore.currentScript?.id) {
      await scriptApi.updateScript(projectStore.currentScript.id, { content: lastAiMsg.content })
    }
    
    // 调用优化API
    const response = await scriptApi.optimizeScript(
      projectStore.currentScript!.id,
      creativeText,
      selectedOptimizeModel.value,
      enableSearchOptimize.value
    )
    const optimizedContent = response?.content
    
    // 更新 loading 消息为实际内容（默认折叠）
    const loadingMsgIndex = messages.value.findIndex(m => m.id === loadingMsgId)
    if (loadingMsgIndex !== -1 && optimizedContent) {
      messages.value[loadingMsgIndex] = {
        ...messages.value[loadingMsgIndex],
        content: optimizedContent,
        isGenerating: false,
        isCollapsed: true,
        id: `ai-${Date.now()}`
      }
    } else if (loadingMsgIndex !== -1) {
        messages.value.splice(loadingMsgIndex, 1)
        ElMessage.warning('生成内容为空')
    }
    
    // 更新 Store
    if (optimizedContent && projectStore.currentScript) {
      projectStore.currentScript.content = optimizedContent
    }
    
    // 保存到项目设置
    const currentProjectId = projectStore.currentProject?.id
    if (currentProjectId) {
      await projectApi.updateProject(currentProjectId, {
        imageModel: selectedModel.value,
        aspectRatio: selectedAspectRatio.value,
        quality: selectedQuality.value,
        conversationContent: JSON.stringify(messages.value.reduce((acc: any[], msg) => {
            if (msg.role === 'user') {
                acc.push({ userInput: msg.content })
            } else if (msg.role === 'ai' && !msg.isGenerating) {
                if (acc.length > 0 && !acc[acc.length-1].script) {
                    acc[acc.length-1].script = msg.content
                } else {
                    acc.push({ userInput: '', script: msg.content })
                }
            }
            return acc
        }, []))
      } as any)
    }
    
    if (!manualContent) {
      optimizationInput.value = ''
    }

    ElMessage.success('脚本生成成功')
    
    await nextTick()
    calculateMessageHeight()
    scrollToBottom()
  } catch (error: any) {
    const loadingMsgIndex = messages.value.findIndex(m => m.id === loadingMsgId)
    if (loadingMsgIndex !== -1) {
      messages.value.splice(loadingMsgIndex, 1)
    }
    ElMessage.error(error?.message || '生成失败')
  } finally {
    optimizing.value = false
    scrollToBottom()
  }
}

const onGenerateKeyframes = async () => {
  // 触发父组件事件，传递生成参数
  // 保存设置
  if (projectStore.currentProject?.id) {
    await projectApi.updateProject(projectStore.currentProject.id, {
      imageModel: selectedModel.value,
      aspectRatio: selectedAspectRatio.value,
      quality: selectedQuality.value
    } as any)

    // 同步更新本地 store，避免后续页面（关键帧页 continue）读取到旧的 aspectRatio
    projectStore.updateCurrentProject({
      imageModel: selectedModel.value,
      aspectRatio: selectedAspectRatio.value,
      quality: selectedQuality.value
    } as any)
  }
  
  // 参考图已经在store中，不需要再次设置
  
  emit('generate-keyframes', {
    model: selectedModel.value,
    aspectRatio: selectedAspectRatio.value,
    quality: selectedQuality.value
  })
}

// 显示参考图对话框
const showReferenceDialog = () => {
  referenceDialogVisible.value = true
}

// 初始化
const initData = async () => {
  const script = projectStore.currentScript
  const project = projectStore.currentProject
  
  messages.value = []

  // 尝试从conversationContent中恢复对话历史
  let hasConversationHistory = false
  if (project) {
    const projectData = project as any
    if (projectData.conversationContent) {
      try {
        const conversations = JSON.parse(projectData.conversationContent)
        if (Array.isArray(conversations) && conversations.length > 0) {
          conversations.forEach((conv: any, index: number) => {
            // User Message
            // 只有当有明确的userInput，或者作为第一条消息且能找到合适的替代内容时才添加
            if (conv.userInput || index === 0) {
               let content = conv.userInput
               if (!content && index === 0) {
                   // 尝试从 description 或 name 恢复
                   // 检查 description 是否疑似脚本(包含特定关键词或过长)，如果是则避开
                   const desc = projectData.description || ''
                   const isDescScript = desc.includes('第1段') || desc.includes('关键帧') || desc.includes('画面：') || desc.length > 800
                   
                   if (!isDescScript && desc) {
                       content = desc
                   } else {
                       content = projectData.name || '药食同源'
                   }
               } else if (!content) {
                   content = '优化请求'
               }

               messages.value.push({
                 id: `user-${Date.now()}-${index}`,
                 role: 'user',
                 content: content,
                 isCollapsed: true
               })
            }
            
            // AI Message
            if (conv.script) {
              messages.value.push({
                id: `ai-${Date.now()}-${index}`,
                role: 'ai',
                content: conv.script,
                isCollapsed: true // 历史消息默认折叠
              })
            }
          })
          hasConversationHistory = true
        }
      } catch (e) {
        // 解析失败，可能是纯文本，将在下面处理
      }
    }
  }

  // 如果没有历史或解析失败，使用当前 scriptContent 和 userInput 构建初始状态
  if (!hasConversationHistory) {
    // User Message
    let initialUserContent = '药食同源'
    if (project) {
       const projectData = project as any
       // 优先使用 conversationContent (如果是非JSON字符串)
       if (typeof projectData.conversationContent === 'string' && projectData.conversationContent.trim() && !projectData.conversationContent.trim().startsWith('[')) {
           initialUserContent = projectData.conversationContent
       } else {
           // 同样的检查逻辑
           const desc = projectData.description || ''
           const isDescScript = desc.includes('第1段') || desc.includes('关键帧') || desc.includes('画面：') || desc.length > 800
           if (!isDescScript && desc) {
               initialUserContent = desc
           } else {
               initialUserContent = projectData.name || '药食同源'
           }
       }
    }
    
    messages.value.push({
      id: `user-${Date.now()}-init`,
      role: 'user',
      content: initialUserContent,
      isCollapsed: true
    })

    // AI Message
    if (script?.content) {
      messages.value.push({
        id: `ai-${Date.now()}-init`,
        role: 'ai',
        content: script.content,
        isCollapsed: true
      })
    }
  }
  
  // 注意：不再强制展开最后一条消息，交由“高度>200px”规则决定初始折叠状态

  // 尝试加载关键帧数据
  if (script?.id) {
    try {
      const response = await keyframeApi.getKeyframesByScript(script.id)
      const keyframes = response.keyframes || []
      if (keyframes.length > 0) {
        projectStore.updateKeyframes(keyframes)
      }
    } catch (e) {
      console.log('加载关键帧失败或暂无关键帧', e)
    }
  }
  
  // 尝试加载模型设置
  if (project) {
    const projectData = project as any
    if (projectData.imageModel) {
      selectedModel.value = projectData.imageModel
      selectedAspectRatio.value = projectData.aspectRatio || ''
      selectedQuality.value = projectData.quality || ''
    }
  }

  // 兜底检查：确保至少有一条用户消息（作为第一条）
  if (messages.value.length === 0 || messages.value[0].role !== 'user') {
    let fallbackContent = '药食同源'
    if (project) {
       const projectData = project as any
       // 同样的逻辑：优先取 conversationContent
       if (typeof projectData.conversationContent === 'string' && projectData.conversationContent.trim() && !projectData.conversationContent.trim().startsWith('[')) {
           fallbackContent = projectData.conversationContent
       } else {
           const desc = projectData.description || ''
           const isDescScript = desc.includes('第1段') || desc.includes('关键帧') || desc.includes('画面：') || desc.length > 800
           if (!isDescScript && desc) {
               fallbackContent = desc
           } else {
               fallbackContent = projectData.name || '药食同源'
           }
       }
    }
    messages.value.unshift({
      id: `user-${Date.now()}-fallback`,
      role: 'user',
      content: fallbackContent,
      isCollapsed: true
    })
  }
  
  // 兜底检查：如果只有用户消息且有 scriptContent，补上 AI 消息
  if (messages.value.length === 1 && messages.value[0].role === 'user' && script?.content) {
      messages.value.push({
        id: `ai-${Date.now()}-fallback`,
        role: 'ai',
        content: script.content,
        isCollapsed: false
      })
  }
  
  calculateMessageHeight()
}

onMounted(async () => {
  // 先初始化数据（加载项目设置，包括旧的模型选择）
  await initData()
  // 然后加载模型列表，并验证/纠正模型选择
  await loadImageModels()
  // 加载脚本模型能力（用于联网搜索开关）
  try {
    const resp = await modelApi.getScriptModels()
    scriptModels.value = Array.isArray(resp) ? resp : (resp?.data || [])
    if (!selectedOptimizeModel.value && scriptModels.value.length > 0) {
      selectedOptimizeModel.value = scriptModels.value[0].id
    }
  } catch (e) {
    console.error('加载脚本模型列表失败:', e)
  }
})

watch(() => selectedOptimizeModel.value, () => {
  if (!supportsWebSearchOptimize.value) {
    enableSearchOptimize.value = false
  }
})

onUpdated(() => {
  calculateMessageHeight()
})

// 只监听项目 ID 变化，避免深层监听导致无限循环
watch(() => projectStore.currentProject?.id, async (newId, oldId) => {
  if (newId && newId !== oldId) {
    await initData()
    await loadImageModels()  // 验证/纠正模型选择
  }
})

watch(() => scriptContent.value, () => {
  calculateMessageHeight()
})
</script>

<style>
.script-editor .el-button+.el-button{
  margin-left: 0;
}

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

.vision-observe {
  margin: 10px 0 14px;
  padding: 10px 12px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 10px;
  background: rgba(245, 247, 250, 0.8);
  font-size: 13px;
  color: #303133;
}
.vision-observe .label {
  font-weight: 600;
}
.vision-observe .status {
  margin-left: 6px;
  font-weight: 600;
}
.vision-observe .status.success {
  color: #67c23a;
}
.vision-observe .status.failed {
  color: #f56c6c;
}
.vision-observe .status.empty {
  color: #e6a23c;
}
.vision-observe .status.skipped {
  color: #909399;
}
.vision-observe .extra {
  margin-left: 6px;
  color: #606266;
}
</style>

<style scoped>
.script-editor {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  position: relative;
}

.conversation-area {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  padding-bottom: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.message-bubble {
  display: flex;
  flex-direction: column;
  gap: 3px;
  width: 70%;
}

.user-bubble {
  align-self: flex-end;
  width: auto;
  max-width: 70%;
}

.ai-bubble {
  align-self: flex-start;
}

.message-with-avatar {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.user-bubble .message-with-avatar {
  flex-direction: row-reverse;
}

.avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.user-avatar {
  background: linear-gradient(135deg, #00aaaa 0%, #00d4d4 100%);
  color: #fff;
}

.ai-avatar {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
}

.message-content-wrapper {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  flex: 1;
}

.message-body {
  flex: 1;
  width: 100%;
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  transition: max-height 0.3s ease;
  position: relative;
}

.message-body.collapsed {
  overflow: hidden;
  position: relative;
}

.message-body.collapsed .message-text {
  display: block;
  max-height: 200px;
  overflow: hidden;
}

.message-content-container,
.message-body-container {
  position: relative;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.collapse-toggle-outside {
  position: absolute;
  bottom: 0;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background-color: #fff;
  border-radius: 50%;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
  cursor: pointer;
  transition: all 0.3s ease;
  color: #606266;
}

.collapse-toggle-outside:hover {
  background-color: #f5f7fa;
  color: #409eff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  transform: translateY(-1px);
}

.collapse-toggle-outside .el-button {
  padding: 0 !important;
  width: 100%;
  height: 100%;
  min-height: unset;
  border-radius: 50%;
}

.user-toggle {
  left: -32px;
}

.ai-toggle {
  right: -32px;
}

.message-body.collapsed::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 40px;
  background: linear-gradient(to bottom, transparent, #fff 80%);
}

.message-body.generating {
  padding: 12px 16px;
  min-height: 40px;
  display: flex;
  align-items: center;
}

.typing-indicator {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #666;
  font-size: 14px;
}

.typing-indicator .dots {
  display: flex;
  gap: 3px;
  margin-left: 2px;
}

.typing-indicator .dot {
  width: 4px;
  height: 4px;
  background-color: #666;
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
}

.typing-indicator .dot:nth-child(1) {
  animation-delay: -0.32s;
}

.typing-indicator .dot:nth-child(2) {
  animation-delay: -0.16s;
}

@keyframes bounce {
  0%, 80%, 100% { 
    transform: scale(0);
  } 40% { 
    transform: scale(1);
  }
}

.message-body.editing {
  padding: 0;
}

.message-text {
  font-size: 15px;
  line-height: 1.6;
  color: #333;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.message-text-editable {
  display: block;
  width: 100%;
  min-width: 100%;
  min-height: 400px;
  padding: 16px;
  font-size: 15px;
  line-height: 1.6;
  color: #333;
  border: none;
  outline: none;
  font-family: inherit;
  resize: none;
  box-sizing: border-box;
  background: transparent;
  white-space: pre-wrap;
  word-wrap: break-word;
  overflow-y: auto;
}

.message-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 16px;
  flex-shrink: 0;
  align-items: center;
}

.keyframe-controls {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: nowrap;
  max-width: calc(100% - 86px);
  margin-left: 52px;
}

.control-select {
  max-width: 160px;
}

.reference-button {
  min-width: 120px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.generate-button {
  margin-left: auto;
}

.action-section {
  position: sticky;
  bottom: 0;
  left: 0;
  right: 0;
  background: #3f3f3f;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  padding: 20px;
  z-index: 10;
}

.optimization-section {
  width: 100%;
}

.optimization-input-wrapper {
  display: flex;
  align-items: flex-end;
  background-color: #fff;
  border: 1px solid #797979;
  border-radius: 10px;
  padding: 20px;
  transition: border-color 0.3s;
  gap: 10px;
}

.optimization-input-wrapper.has-focus {
  border-color: #00aaaa;
}

.optimization-input {
  flex: 1;
}

.optimization-input :deep(.el-textarea__inner) {
  border: none;
  box-shadow: none;
  resize: none;
  padding: 0;
  font-size: 15px;
}

.optimization-model-select {
  width: 140px;
  flex-shrink: 0;
}

.opt-web-search-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  padding: 0 10px;
  border: 1px solid #cccccc;
  border-radius: 8px;
  background: #ffffff;
  flex-shrink: 0;
}

.opt-web-search-label {
  font-size: 12px;
  color: #666666;
  line-height: 1;
}

.opt-web-search-toggle :deep(.el-switch) {
  --el-switch-on-color: #00aaaa;
}

.optimization-button {
  width: 49px;
  height: 26px;
  border-radius: 15px;
  background-color: #00aaaa;
  border: none;
  display: flex;
  justify-content: center;
  align-items: center;
}

/* =========================
   Figma: 脚本页（9:611）
   ========================= */
.script-editor.figma-script {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f3f4f6;
}

.figma-script .content {
  flex: 1 1 auto;
  min-height: 0;
  overflow: auto;
  padding: 24px;
}

.figma-script .content-inner {
  width: 100%;
}

.figma-script .user-input-row {
  display: flex;
  justify-content: flex-end;
}

.figma-script .user-input-card {
  width: 501px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06);
  padding: 17px;
  display: flex;
  gap: 12px;
  align-items: flex-start;
  position: relative;
}

.figma-script .user-input-text {
  font-size: 14px;
  line-height: 22.75px;
  color: #1e2939;
  letter-spacing: -0.1504px;
  flex: 1;
  white-space: pre-wrap;
  word-break: break-word;
}

.figma-script .user-input-text.collapsed {
  max-height: 23px;
  overflow: hidden;
}

.figma-script .collapse-btn {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  border: none;
  background: transparent;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.figma-script .collapse-btn img {
  width: 16px;
  height: 16px;
}

.figma-script .top-actions {
  margin-top: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  height: 32px;
}

.figma-script .text-action {
  height: 32px;
  border: none;
  background: transparent;
  border-radius: 8px;
  padding: 0 10px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: #4a5565;
  font-size: 12px;
  line-height: 16px;
}

.figma-script .text-action:hover {
  background: rgba(255, 255, 255, 0.6);
}

.figma-script .text-action:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.figma-script .text-action.primary {
  background: linear-gradient(180deg, #2b7fff 0%, #00b8db 100%);
  color: #fff;
}

.figma-script .text-action.primary:hover {
  background: linear-gradient(180deg, #1f66ff 0%, #00a8c8 100%);
}

.figma-script .text-action.danger {
  background: #fee2e2;
  color: #b91c1c;
}

.figma-script .script-blocks {
  margin-top: 8px;
}

.figma-script .loading-card,
.figma-script .empty-script {
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  padding: 16px;
  color: #4a5565;
}

.figma-script .script-edit-textarea {
  width: 100%;
  min-height: 420px;
  border: 1px solid #d1d5dc;
  border-radius: 10px;
  padding: 12px 14px;
  font-size: 14px;
  line-height: 22px;
  box-sizing: border-box;
  resize: vertical;
  outline: none;
}

.figma-script .keyframe-panel {
  margin-top: 16px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 17px;
  /* 与脚本文案卡片宽度对齐（ScriptPrettyView.cards 为 75%） */
  width: 75%;
  max-width: 100%;
}

@media (max-width: 980px) {
  .figma-script .keyframe-panel {
    width: 100%;
  }
}

.figma-script .keyframe-panel-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.figma-script .keyframe-select {
  flex: 1 1 320px;
  min-width: 260px;
}

.figma-script .pill {
  height: 32px;
  border-radius: 8px;
  border: 1px solid #d1d5dc;
  background: #ffffff;
  padding: 0 13px;
  font-size: 14px;
  line-height: 20px;
  color: #101828;
  cursor: pointer;
}

.figma-script .pill.active {
  background: #e5e7eb;
  border-color: #d1d5dc;
}

.figma-script .generate-keyframes-btn {
  width: 100%;
  height: 36px;
  margin-top: 12px;
  border-radius: 8px;
  border: none;
  cursor: pointer;
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  background: linear-gradient(180deg, #2b7fff 0%, #00b8db 100%);
}

.figma-script .generate-keyframes-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.figma-script .next-step-btn {
  width: 100%;
  height: 36px;
  margin-top: 8px;
  border-radius: 8px;
  border: 1px solid #d1d5dc;
  background: #ffffff;
  color: #101828;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
}

.figma-script .next-step-btn:hover {
  background: #f9fafb;
}

.figma-script .chat-input {
  flex: 0 0 auto;
  height: 77px;
  background: #f3f4f6;
  border-top: 1px solid #e5e7eb;
  padding: 17px 16px;
  box-sizing: border-box;
}

.figma-script .chat-input-inner {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  height: 44px;
}

.figma-script .chat-textarea {
  flex: 1 1 auto;
}

.figma-script .chat-textarea :deep(textarea) {
  height: 44px !important;
  resize: none;
  border-radius: 8px;
  border: 1px solid #d1d5dc;
  background: #f3f3f5;
  padding: 8px 12px;
  font-size: 14px;
  line-height: 20px;
}

.figma-script .send-btn {
  width: 40px;
  height: 44px;
  border-radius: 8px;
  border: none;
  cursor: pointer;
  background: linear-gradient(180deg, #2b7fff 0%, #00b8db 100%);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.figma-script .send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.figma-script .send-btn img {
  width: 16px;
  height: 16px;
}
</style>
