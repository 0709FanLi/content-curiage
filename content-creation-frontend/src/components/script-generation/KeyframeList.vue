<template>
  <div
    class="keyframe-list-container"
    :class="{ 'kf-portrait': project_aspect_ratio === '9:16' }"
    :style="{
      '--kf-aspect-ratio': project_aspect_ratio === '9:16' ? '9 / 16' : '16 / 9',
      '--kf-grid-cols': project_aspect_ratio === '9:16' ? 5 : 4
    }"
  >
    <!-- Figma 24:236 顶部区域（页面内二级头） -->
    <div class="kf-page-header">
      <div class="kf-page-header-left">
        <div class="kf-page-title">AI关键帧生成</div>

        <el-dropdown
          trigger="click"
          :disabled="videoModels.length === 0"
          @command="(id: string) => (selectedVideoModel = id)"
        >
          <button
            class="kf-model-chip"
            type="button"
           
            :disabled="videoModels.length === 0"
            :title="current_video_model?.name || ''"
          >
            <span class="kf-model-chip-main">
              {{ current_video_model_short }}
            </span>
            <span class="kf-model-chip-sub">
              {{ current_video_model_sub }}
            </span>
            <el-icon class="kf-model-chip-icon"><ArrowDown /></el-icon>
          </button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item
                v-for="m in videoModels"
                :key="m.id"
                :command="m.id"
              >
                {{ m.name || m.id }}
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>

      <div class="kf-page-header-right">
        <el-button
          type="default"
          class="kf-btn kf-btn-ghost"
          :disabled="!canDownloadAllImages"
          @click="handleDownloadAllImages"
         
        >
          <el-icon><Download /></el-icon>
          下载全部图片
        </el-button>
        
        <el-button
          type="default"
          class="kf-btn kf-btn-ghost"
          @click="goToScriptPage"
         
        >
          <el-icon><Back /></el-icon>
          上一步（查看脚本）
        </el-button>
        
        <el-button
          type="primary"
          class="kf-btn kf-btn-primary"
          :disabled="!canConfirmKeyframes"
          @click="onGenerateVideo"
         
        >
          <el-icon><Check /></el-icon>
          关键帧确认
        </el-button>
        
        <el-button
          v-if="hasExistingVideos"
          type="success"
          class="kf-btn"
          @click="goToVideoPage"
        >
          下一步
        </el-button>
      </div>
    </div>

    <div class="keyframes-content">
    <!-- 首段关键帧（segment_0）确认提示 -->
      <div v-if="showFirstFrameConfirmation" class="first-frame-confirmation">
        <div class="frame0-banner">
          <div class="frame0-banner-inner">
            <div class="frame0-icon">
              <el-icon><SuccessFilled /></el-icon>
            </div>
            <div class="frame0-text">
              <div class="frame0-title">首段关键帧（segment_0）生成成功！</div>
              <div class="frame0-desc">
                该关键帧将作为后续关键帧生成与第一段视频生成的参考图（定调）。请仔细检查其效果，确认无误后，系统会继续生成其余关键帧。
            </div>
          </div>
            <el-button 
              type="primary" 
              class="frame0-confirm-btn"
              :loading="confirmingFirstFrame"
              @click="handleConfirmFirstFrame"
             
            >
              {{ confirmingFirstFrame ? '正在生成...' : '确认并继续生成' }}
            </el-button>
          </div>
        </div>
      </div>

      <div class="keyframe-grid">
        <div
          v-for="keyframe in sortedKeyframes"
          :key="keyframe.id"
          class="keyframe-card"
        >
          <div class="card-image-area">
            <div v-if="keyframe.imageUrl && keyframe.status === 'completed'" class="image-container">
              <img
                :src="keyframe.imageUrl"
                :alt="keyframe.segmentId"
                class="keyframe-image"
                @error="handleImageError(keyframe)"
              />

              <!-- 悬浮操作（预览 / 下载 / 编辑 / 重生 / 上传） -->
              <div class="img-actions">
              <el-button
                  class="img-action-btn"
                size="small"
                  circle
                  @click="open_image_preview(keyframe)"
                  title="预览"
                  style="margin-left: 12px;"
              >
                  <el-icon><ZoomIn /></el-icon>
              </el-button>
              <el-button
                  class="img-action-btn"
                size="small"
                circle
                  @click="handleDownloadImage(keyframe)"
                  title="下载"
                >
                  <el-icon><Download /></el-icon>
                </el-button>
                <el-button
                  class="img-action-btn"
                  size="small"
                  circle
                  @click="handleEditKeyframeDescription(keyframe)"
                  title="编辑并重新生成"
                >
                  <el-icon><Edit /></el-icon>
                </el-button>
                <el-button
                  class="img-action-btn"
                  size="small"
                  circle
                  @click="handleRefreshKeyframe(keyframe.id)"
                  title="重新生成"
              >
                  <el-icon><Refresh /></el-icon>
                </el-button>
                <el-button
                  class="img-action-btn"
                  size="small"
                  circle
                  @click="handleUploadImage(keyframe.id)"
                  title="上传替换"
                >
                  <el-icon><Upload /></el-icon>
              </el-button>
              </div>

              <div class="img-tag">
                {{ getKeyframeTitle(keyframe) }}
              </div>
            </div>
            
            <div v-else-if="keyframe.status === 'generating'" class="image-placeholder generating">
              <div class="loading-animation">
                <div class="loading-bar"></div>
              </div>
              <div class="loading-text">
                <span class="loading-icon">⏳</span>
                <span>AI 正在创作中...</span>
              </div>
              <!-- 不再显示重试状态和中断按钮 -->
            </div>
            
            <div v-else-if="keyframe.status === 'pending'" class="image-placeholder pending">
              <div class="pending-animation">
                <div class="pulse-circle"></div>
                <div class="pulse-circle delay-1"></div>
              </div>
              <div class="pending-text">
                <span class="pending-icon">⏱️</span>
                <span>等待生成中...</span>
              </div>
            </div>
            
            <div v-else-if="keyframe.status === 'failed'" class="image-placeholder failed">
              <div class="failed-icon">🔧</div>
              <div class="failed-text">模型维护中</div>
              <div class="error-detail">请稍后重试</div>
              <el-button
                class="retry-btn"
                size="small"
                type="primary"
                @click="handleRefreshKeyframe(keyframe.id)"
              >
                重试
              </el-button>
            </div>
            
            <div v-else class="image-placeholder">
              <div class="placeholder-icon">🖼️</div>
              <el-button
                class="upload-btn"
                size="small"
                @click="handleUploadImage(keyframe.id)"
              >
                上传图片
              </el-button>
            </div>
          </div>

          <div class="card-description">
            <p :title="keyframe.prompt">{{ keyframe.prompt }}</p>
          </div>
        </div>
      </div>
    </div>

    <input
      ref="imageUploadRef"
      type="file"
      accept="image/*"
      style="display: none"
      @change="handleImageSelected"
    />

    <!-- 编辑段落描述弹窗 -->
    <el-dialog
      v-model="editDescriptionDialogVisible"
      title="编辑段落描述"
      width="600px"
      :before-close="handleCancelEditDescription"
    >
      <div class="edit-description-content">
        <el-input
          v-model="editingDescription"
          type="textarea"
          :rows="8"
          placeholder="请输入段落描述..."
          maxlength="1000"
          show-word-limit
        />
      </div>
      <template #footer>
        <div class="dialog-footer">
          <el-select
            v-model="editingModel"
            placeholder="选择生成模型"
            class="model-select"
            style="width: 200px; margin-right: auto;"
          >
            <el-option
              v-for="model in imageModels"
              :key="model.id"
              :label="model.name"
              :value="model.id"
            />
          </el-select>
          <el-button @click="handleCancelEditDescription">取消</el-button>
          <el-button 
            type="primary" 
            @click="handleConfirmEditDescription"
            :disabled="!editingDescription.trim() || !editingModel"
            :loading="regeneratingFromEdit"
          >
            确定并生成新关键帧
          </el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 图片放大预览 -->
    <el-dialog
      v-model="previewVisible"
      :show-close="true"
      class="keyframe-preview-dialog"
      width="900px"
      align-center
      :append-to-body="true"
      :close-on-click-modal="true"
      :close-on-press-escape="true"
    >
      <div v-if="previewSrc" class="preview-body">
        <div class="preview-meta">
          <div class="preview-title">{{ previewTitle || '图片预览' }}</div>
        </div>
        <div class="preview-frame">
          <el-image :src="previewSrc" fit="contain" class="preview-image">
            <template #error>
              <div class="preview-error">图片加载失败</div>
            </template>
          </el-image>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElIcon } from 'element-plus'
import { ArrowDown, Back, Download, Edit, Refresh, SuccessFilled, Check, ZoomIn, Upload } from '@element-plus/icons-vue'
import { keyframeApi, videoApi, modelApi, projectApi, scriptApi } from '@/api'
import { useProjectStore } from '@/stores'
import type { Keyframe } from '@/types'
import JSZip from 'jszip'

const previewVisible = ref(false)
const previewSrc = ref('')
const previewTitle = ref('')

const open_image_preview = (keyframe: any) => {
  const src = keyframe?.imageUrl
  if (!src) return
  previewSrc.value = String(src)
  previewTitle.value = String(getKeyframeTitle(keyframe) || '图片预览')
  previewVisible.value = true
}

const props = defineProps<{
  projectId: number | null
}>()

const emit = defineEmits(['generate-video'])
const router = useRouter()
const projectStore = useProjectStore()

const project_aspect_ratio = computed<'9:16' | '16:9'>(() => {
  const raw = String((projectStore.currentProject as any)?.aspectRatio || '')
  return raw === '9:16' ? '9:16' : '16:9'
})

// 状态
const keyframes = ref<Keyframe[]>([])
const generating = ref(false)
const confirmingFirstFrame = ref(false)
const imageUploadRef = ref<HTMLInputElement | null>(null)
const currentUploadKeyframeId = ref<number | null>(null)
const hasExistingVideos = ref(false)
const completion_loading = ref(false)
let pollingTimer: ReturnType<typeof setInterval> | null = null

// 视频模型
const videoModels = ref<any[]>([])
// 默认不写死模型：等加载到可用模型列表后，自动选择列表第一个
const selectedVideoModel = ref<string>('')

const ALLOWED_ASPECT_RATIOS = ['9:16', '16:9'] as const
const normalize_aspect_ratio = (ratio?: string): string => {
  const r = String(ratio || '')
  return (ALLOWED_ASPECT_RATIOS as unknown as string[]).includes(r) ? r : '16:9'
}

// 编辑相关
const editDescriptionDialogVisible = ref(false)
const editingDescription = ref('')
const editingKeyframe = ref<Keyframe | null>(null)
const editingModel = ref('')
const regeneratingFromEdit = ref(false)
const imageModels = ref<any[]>([]) // 用于编辑弹窗

// 计算属性
const sortedKeyframes = computed(() => {
  return [...keyframes.value].sort((a, b) => {
    const getOrder = (segmentId: string) => {
      // 全局移除第0帧后：按 segment 数字排序。
      // 兼容历史 _first_frame：若存在则视为 segment_0 排序。
      if (segmentId.includes('_first_frame')) return 0
      const segNum = parseInt(segmentId.match(/segment_(\d+)/)?.[1] || '0')
      return segNum * 1000
    }
    return getOrder(a.segmentId) - getOrder(b.segmentId)
  })
})

const showFirstFrameConfirmation = computed(() => {
  if (keyframes.value.length === 0) return false
  // 首段确认：优先 segment_0；兼容历史仅有 _first_frame 的情况
  const firstFrame =
    keyframes.value.find(k => k.segmentId === 'segment_0') ||
    keyframes.value.find(k => k.segmentId.includes('_first_frame'))
  if (!firstFrame) return false
  
  const firstFrameCompleted = firstFrame.status === 'completed' && firstFrame.imageUrl
  // 仅在“其余关键帧尚未开始生成（仍为 pending）”时展示确认按钮。
  // 避免点击确认后，其他帧进入 generating 但仍无 imageUrl 时 banner 继续出现造成误导。
  const otherFramesNotStarted = keyframes.value
    .filter(k => k.segmentId !== firstFrame.segmentId && !k.segmentId.includes('_first_frame'))
    .every(k => !k.imageUrl && String(k.status).toLowerCase() === 'pending')
  
  return firstFrameCompleted && otherFramesNotStarted
})

const allKeyframesCompleted = computed(() => {
  if (keyframes.value.length === 0) return false
  return keyframes.value.every(k => {
    if (k.imageUrl) return true
    return ['completed', 'failed'].includes(k.status)
  })
})

const is_completed_status = computed(() => projectStore.projectCompletionStatus === 'completed')

const canDownloadAllImages = computed(() => {
  return Boolean(allKeyframesCompleted.value)
})

const canConfirmKeyframes = computed(() => {
  return (
    !is_completed_status.value &&
    !completion_loading.value &&
    !hasExistingVideos.value &&
    allKeyframesCompleted.value &&
    selectedVideoModel.value &&
    videoModels.value.length > 0
  )
})

const hydrate_completion_status = async () => {
  const script_id = Number(projectStore.currentScript?.id || 0)
  const project_id = Number(props.projectId || projectStore.currentProject?.id || 0)
  if (!script_id || !project_id) return

  completion_loading.value = true
  try {
    const script = await scriptApi.getScript(script_id)
    const exported_url = String((script as any)?.exportedVideoUrl || '').trim()
    projectStore.set_project_exported_video_url(project_id, exported_url)
  } catch (e) {
    // 不阻断页面，只是无法识别 completed
    console.warn('hydrate completion status failed:', e)
  } finally {
    completion_loading.value = false
  }
}

const current_video_model = computed(() => {
  return videoModels.value.find(m => m.id === selectedVideoModel.value) || null
})

const current_video_model_short = computed(() => {
  const idx = videoModels.value.findIndex(m => m.id === selectedVideoModel.value)
  if (idx >= 0) {
    const letter = String.fromCharCode(65 + Math.min(idx, 25))
    return `Model ${letter}`
  }
  return 'Model'
})

const current_video_model_sub = computed(() => {
  const name = String(current_video_model.value?.name || '')
  const bracket = name.match(/\[(.*?)\]/)
  if (bracket?.[1]) return `(${bracket[1]})`
  const first = name.split('，')[0] || name
  return first ? `(${first})` : '(默认)'
})

// 方法
const getKeyframeTitle = (keyframe: Keyframe) => {
  if (keyframe.segmentId === 'segment_0') return '首段关键帧 (segment_0)'
  if (keyframe.segmentId.includes('_first_frame')) return '历史首帧 (兼容)'
  return keyframe.segmentId
}

const checkExistingVideos = async () => {
  const scriptId = projectStore.currentScript?.id
  if (!scriptId) return
  
  try {
    const response = await videoApi.getVideoSegmentsByScript(scriptId)
    hasExistingVideos.value = (response.videoSegments || []).length > 0
  } catch (error) {
    console.error('检查视频失败:', error)
    hasExistingVideos.value = false
  }
}

const goToScriptPage = () => {
  if (props.projectId) {
    router.push(`/project/${props.projectId}/script`)
    return
  }
  router.back()
}

const loadKeyframes = async () => {
  const scriptId = projectStore.currentScript?.id
  if (!scriptId) {
    // 如果store没有，尝试重新加载store (防止刷新页面丢失)
    if (props.projectId && !projectStore.currentProject) {
        await projectStore.loadRecentProjects()
        const project = await projectApi.getProject(props.projectId)
        projectStore.setCurrentProject(project as any)
    }
    // 如果还是没有，那可能是真没有
    if (!projectStore.currentScript?.id) return
  }

  try {
    const response = await keyframeApi.getKeyframesByScript(projectStore.currentScript!.id)
    keyframes.value = response.keyframes || []
    
    const hasGenerating = keyframes.value.some(k =>
      ['generating', 'pending'].includes(k.status)
    )
    
    if (hasGenerating) {
      generating.value = true
      startPolling()
    } else {
      generating.value = false
      stopPolling()
    }
    // 同步到store
    projectStore.updateKeyframes(keyframes.value)
  } catch (error) {
    console.error('加载关键帧失败', error)
    stopPolling()
  }
}

const startPolling = () => {
  if (pollingTimer) return
  pollingTimer = setInterval(async () => {
    await loadKeyframes()
    const allFinished = keyframes.value.every(k =>
      ['completed', 'failed'].includes(k.status)
    )
    if (allFinished) {
      stopPolling()
      generating.value = false
    }
  }, 3000)
}

const stopPolling = () => {
  if (pollingTimer) {
    clearInterval(pollingTimer)
    pollingTimer = null
  }
}

const handleConfirmFirstFrame = async () => {
  const scriptId = projectStore.currentScript?.id
  if (!scriptId) return
  confirmingFirstFrame.value = true
  try {
    // 使用store中的项目配置
    const project = projectStore.currentProject as any
    
    // 确保模型存在
    let model = project?.imageModel
    
    // 如果store中没有模型信息，尝试重新从API获取最新的项目信息
    if (!model && props.projectId) {
      try {
        const latestProject = await projectApi.getProject(props.projectId)
        if (latestProject) {
          projectStore.setCurrentProject(latestProject as any)
          model = (latestProject as any).imageModel
        }
      } catch (e) {
        console.error('重新加载项目信息失败', e)
      }
    }
    
    if (!model) {
      ElMessage.error('无法获取生成模型配置，请返回上一步重新选择')
      confirmingFirstFrame.value = false
      return
    }

    const request: any = {
      script_id: scriptId,
      model: model,
      aspect_ratio: normalize_aspect_ratio(project?.aspectRatio)
    }
    if (project?.quality) request.quality = project.quality
    
    await keyframeApi.continueGenerateKeyframes(scriptId, request)
    ElMessage.success('开始生成其余关键帧')
    startPolling()
  } catch (error: any) {
    ElMessage.error(error?.message || '继续生成失败')
  } finally {
    confirmingFirstFrame.value = false
  }
}

const handleRefreshKeyframe = async (keyframeId: number) => {
  const project = projectStore.currentProject as any
  try {
    await keyframeApi.regenerateKeyframe(
      keyframeId,
      project?.imageModel || 'imagen-3',
      normalize_aspect_ratio(project?.aspectRatio),
      project?.quality
    )
    ElMessage.success('开始重新生成')
    await loadKeyframes()
    startPolling()
  } catch (error: any) {
    ElMessage.error(error?.message || '重试失败')
  }
}

const handleCancelKeyframe = async (keyframe: Keyframe) => {
  try {
    await keyframeApi.updateKeyframe(keyframe.id, { status: 'failed', errorMessage: '用户中断重试' })
    ElMessage.info('已请求中断')
    await loadKeyframes()
  } catch (error: any) {
    ElMessage.error(error?.message || '中断失败')
  }
}

const handleUploadImage = (keyframeId: number) => {
  currentUploadKeyframeId.value = keyframeId
  imageUploadRef.value?.click()
}

const handleImageSelected = async (event: Event) => {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file || !currentUploadKeyframeId.value) return
  try {
    await keyframeApi.uploadKeyframeImage(currentUploadKeyframeId.value, file)
    ElMessage.success('上传成功')
    await loadKeyframes()
  } catch (error: any) {
    ElMessage.error(error?.message || '上传失败')
  } finally {
    currentUploadKeyframeId.value = null
    target.value = ''
  }
}

// 编辑相关
const handleEditKeyframeDescription = async (keyframe: Keyframe) => {
  editingKeyframe.value = keyframe
  editingDescription.value = keyframe.prompt || ''
  // 加载模型列表如果还没加载
  if (imageModels.value.length === 0) {
      const res = await modelApi.getImageModels()
      imageModels.value = Array.isArray(res) ? res : (res?.data || [])
  }
  editingModel.value = (projectStore.currentProject as any)?.imageModel || imageModels.value[0]?.id
  editDescriptionDialogVisible.value = true
}

const handleConfirmEditDescription = async () => {
  if (!editingKeyframe.value) return
  regeneratingFromEdit.value = true
  try {
    await keyframeApi.updateKeyframe(editingKeyframe.value.id, { prompt: editingDescription.value.trim() })
    const project = projectStore.currentProject as any
    await keyframeApi.regenerateKeyframe(
      editingKeyframe.value.id,
      editingModel.value,
      normalize_aspect_ratio(project?.aspectRatio),
      project?.quality
    )
    ElMessage.success('已开始重新生成')
    editDescriptionDialogVisible.value = false
    await loadKeyframes()
    startPolling()
  } catch (error: any) {
    ElMessage.error(error?.message || '编辑失败')
  } finally {
    regeneratingFromEdit.value = false
  }
}

const handleCancelEditDescription = () => {
    editDescriptionDialogVisible.value = false
}

const onGenerateVideo = () => {
  emit('generate-video', {
    videoModel: selectedVideoModel.value
  })
}

const goToVideoPage = () => {
  if (props.projectId) {
    router.push(`/project/${props.projectId}/video`)
  }
}

const loadVideoModels = async () => {
  try {
    const res = await videoApi.getVideoModels()
    // 处理不同格式
    let models: any[] = []
    if (Array.isArray(res)) models = res
    else if (res && (res as any).models) models = (res as any).models
    
    videoModels.value = models.length > 0 ? models : [
      { id: 'veo3.1-fast-ref', name: '用户状态展示，适合拍人 [效果见证/情绪渲染]' },
      { id: 'sora-2', name: '黑科技原理大片，适合拍物 [功效可视化/卖点证明]' },
      { id: 'doubao-seedance-1-5-pro-251215', name: '豆包-影视级运动/情绪大片 [镜头语言/情绪张力]' },
      { id: 'jimeng_i2v_first_v30_1080', name: '即梦-效果演变/对比模式 [Before & After/过程演示]' }
    ]
    // 如果当前选中不在列表中（或为空），自动选择第一个
    if (
      videoModels.value.length > 0 &&
      (!selectedVideoModel.value ||
        !videoModels.value.some(m => m.id === selectedVideoModel.value))
    ) {
      selectedVideoModel.value = videoModels.value[0].id
    }
  } catch (e) {
    videoModels.value = [
      { id: 'veo3.1-fast-ref', name: '用户状态展示，适合拍人 [效果见证/情绪渲染]' },
      { id: 'sora-2', name: '黑科技原理大片，适合拍物 [功效可视化/卖点证明]' },
      { id: 'doubao-seedance-1-5-pro-251215', name: '豆包-影视级运动/情绪大片 [镜头语言/情绪张力]' },
      { id: 'jimeng_i2v_first_v30_1080', name: '即梦-效果演变/对比模式 [Before & After/过程演示]' }
    ]
    if (
      videoModels.value.length > 0 &&
      (!selectedVideoModel.value ||
        !videoModels.value.some(m => m.id === selectedVideoModel.value))
    ) {
      selectedVideoModel.value = videoModels.value[0].id
    }
  }
}

const handleImageError = (keyframe: Keyframe) => {
    setTimeout(() => loadKeyframes(), 2000)
}

// 下载单个图片
const handleDownloadImage = (keyframe: Keyframe) => {
  if (!keyframe.imageUrl) {
    ElMessage.warning('图片地址不存在')
    return
  }
  
  try {
    // 直接使用 a 标签下载，不使用 fetch（避免CORS问题）
    const link = document.createElement('a')
    link.href = keyframe.imageUrl
    link.download = `keyframe_${keyframe.segmentId}.png`
    // 不设置 target，让浏览器决定行为
    // 如果是同源，会下载；如果跨域，浏览器会尝试下载或打开
    link.style.display = 'none'
    document.body.appendChild(link)
    link.click()
    
    // 清理
    setTimeout(() => {
      document.body.removeChild(link)
    }, 100)
    
    ElMessage.success('开始下载图片')
  } catch (error) {
    console.error('下载图片失败:', error)
    ElMessage.error('下载图片失败，请重试')
  }
}

// 下载全部图片（打包成ZIP）
const handleDownloadAllImages = async () => {
  const completedKeyframes = keyframes.value.filter(k => 
    k.imageUrl && k.status === 'completed'
  )
  
  if (completedKeyframes.length === 0) {
    ElMessage.warning('没有可下载的图片')
    return
  }
  
  const loadingMsg = ElMessage.info({
    message: `正在打包 ${completedKeyframes.length} 张图片...`,
    duration: 0
  })
  
  try {
    const zip = new JSZip()
    const folder = zip.folder('keyframes')
    
    // 使用后端代理下载图片，避免CORS问题
    const downloadPromises = completedKeyframes.map(async (keyframe, index) => {
      try {
        // 使用后端代理API
        const proxyUrl = `/api/files/proxy?url=${encodeURIComponent(keyframe.imageUrl!)}`
        const response = await fetch(proxyUrl)
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }
        const blob = await response.blob()
        const filename = `keyframe_${String(index + 1).padStart(2, '0')}_segment_${keyframe.segmentId}.png`
        return { filename, blob }
      } catch (error) {
        console.error(`下载图片失败 (segment ${keyframe.segmentId}):`, error)
        return null
      }
    })
    
    // 等待所有图片下载完成
    const results = await Promise.all(downloadPromises)
    
    // 将成功下载的图片添加到ZIP
    let successCount = 0
    results.forEach(result => {
      if (result) {
        folder!.file(result.filename, result.blob)
        successCount++
      }
    })
    
    if (successCount === 0) {
      throw new Error('所有图片下载失败')
    }
    
    // 生成ZIP文件
    const zipBlob = await zip.generateAsync({ 
      type: 'blob',
      compression: 'DEFLATE',
      compressionOptions: { level: 6 }
    })
    
    // 下载ZIP文件
    const url = window.URL.createObjectURL(zipBlob)
    const link = document.createElement('a')
    link.href = url
    link.download = `keyframes_${new Date().getTime()}.zip`
    link.style.display = 'none'
    document.body.appendChild(link)
    link.click()
    
    // 清理
    setTimeout(() => {
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
    }, 100)
    
    loadingMsg.close()
    
    if (successCount < completedKeyframes.length) {
      ElMessage.warning(`成功打包 ${successCount}/${completedKeyframes.length} 张图片`)
    } else {
      ElMessage.success(`成功打包下载 ${successCount} 张图片`)
    }
  } catch (error) {
    loadingMsg.close()
    console.error('打包下载失败:', error)
    ElMessage.error('打包下载失败，请重试')
  }
}

onMounted(async () => {
  await loadVideoModels()
  await loadKeyframes()
  await checkExistingVideos()
  await hydrate_completion_status()
})

onUnmounted(() => {
  stopPolling()
})

watch(() => props.projectId, async (newVal) => {
  if (newVal) {
    stopPolling()
    keyframes.value = []
    await checkExistingVideos()
    await loadKeyframes()
    await hydrate_completion_status()
  }
})
</script>

<style scoped>
.keyframe-list-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f3f4f6;
  overflow: hidden;
}

.panel-header {
  padding: 20px;
  border-bottom: 1px solid #e8e8e8;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: #fff;
}

.panel-title {
  font-size: 18px;
  font-weight: 600;
  color: #333;
}

.header-controls {
  display: flex;
  gap: 12px;
  align-items: center;
}

.video-model-select {
  min-width: 240px;
}

.keyframes-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px 24px 24px 24px;
  box-sizing: border-box;
}

.keyframe-grid {
  display: grid;
  /* 16:9 -> 4 列；9:16 -> 5 列 */
  grid-template-columns: repeat(var(--kf-grid-cols, 4), minmax(0, 1fr));
  gap: 20px;
  align-items: start;
  justify-content: start;
}

.keyframe-card {
  background-color: #fff;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid #e5e7eb;
  box-shadow: none;
  display: flex;
  flex-direction: column;
}

.card-header {
  padding: 12px 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #e8e8e8;
}

.card-title {
  font-size: 14px;
  font-weight: 500;
  margin: 0;
}

.card-actions {
  display: flex;
  gap: 8px;
}

.action-icon {
  cursor: pointer;
  font-size: 16px;
  color: #666;
}

.action-icon:hover { color: #00aaaa; }

.card-image-area {
  position: relative;
  width: 100%;
  aspect-ratio: var(--kf-aspect-ratio, 16 / 9);
  background: #000;
}

.image-container, .image-placeholder {
  position: absolute;
  top: 0; left: 0; width: 100%; height: 100%;
}

.keyframe-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: #000;
}

.upload-overlay-btn {
  position: absolute;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  opacity: 0;
  transition: opacity 0.3s;
}

.image-container:hover .upload-overlay-btn { opacity: 1; }

.preview-overlay-btn {
  position: absolute;
  right: 10px;
  bottom: 10px;
  opacity: 0;
  transition: opacity 0.3s;
}

.image-container:hover .preview-overlay-btn { opacity: 1; }

.image-placeholder {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  color: #fff;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.image-placeholder.generating { background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); }
.image-placeholder.failed { background: linear-gradient(135deg, #ff6b6b 0%, #ee5a6f 100%); }

.failed-icon {
  font-size: 32px;
  margin-bottom: 8px;
}

.failed-text {
  font-size: 14px;
  margin-bottom: 8px;
  font-weight: 500;
}

.error-detail {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.9);
  margin-bottom: 12px;
  padding: 0 12px;
  text-align: center;
  line-height: 1.4;
  display: -webkit-box;
  line-clamp: 3;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.retry-btn {
  margin-top: 4px;
}

.loading-animation {
    width: 60%; height: 4px; background: rgba(255,255,255,0.2); border-radius: 2px; overflow: hidden; margin-bottom: 10px;
}

.retry-status {
  font-size: 12px;
  color: rgba(255,255,255,0.9);
  margin: 5px 0;
  text-align: center;
  padding: 0 10px;
  line-height: 1.3;
}

.cancel-btn {
  margin-top: 5px;
  color: #ffeded !important;
  font-size: 12px;
}
.cancel-btn:hover {
  color: #ff4d4f !important;
  text-decoration: underline;
}

.loading-bar {
    width: 30%; height: 100%; background: #fff; animation: loading-slide 1.5s infinite;
}
@keyframes loading-slide {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(400%); }
}

.card-description {
  padding: 12px;
  font-size: 12px;
  color: #6a7282;
  line-height: 19.5px;
  height: 73px;
  overflow: hidden;
}
.card-description p{
  /* 最多两行 */
  display: -webkit-box;
  line-clamp: 2;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
}

.first-frame-confirmation {
  margin-bottom: 20px;
}

.confirmation-card {
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e4e7ed;
  overflow: hidden;
}

.confirmation-header {
  padding: 16px;
  background: linear-gradient(135deg, #409eff 0%, #67c23a 100%);
  display: flex;
  align-items: center;
  gap: 12px;
  color: #fff;
}

.success-badge {
  width: 40px; height: 40px; background: rgba(255,255,255,0.9); border-radius: 50%;
  display: flex; justify-content: center; align-items: center; color: #67c23a;
}

.confirmation-message { padding: 16px; font-size: 14px; color: #606266; }
.confirmation-actions { padding: 16px; text-align: center; }

.edit-description-content { padding: 10px 0; }
.dialog-footer { display: flex; align-items: center; gap: 12px; }

/* Figma 24:236 顶部区域（页面内二级头） */
.kf-page-header {
  height: 69px;
  flex: 0 0 69px;
  background: #ffffff;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  box-sizing: border-box;
}

.kf-page-header-left {
  display: flex;
  align-items: center;
  gap: 16px;
  min-width: 0;
}

.kf-page-title {
  font-size: 18px;
  font-weight: 600;
  color: #1e2939;
  line-height: 28px;
  white-space: nowrap;
}

.kf-model-chip {
  height: 36px;
  border: none;
  border-radius: 10px;
  padding: 0 16px;
  cursor: pointer;
  background: linear-gradient(180deg, #2b7fff 0%, #00b8db 100%);
  color: #ffffff;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.kf-model-chip:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.kf-model-chip-main {
  font-size: 14px;
  font-weight: 500;
  line-height: 20px;
  white-space: nowrap;
}

.kf-model-chip-sub {
  font-size: 14px;
  font-weight: 500;
  line-height: 20px;
  color: rgba(255, 255, 255, 0.8);
  white-space: nowrap;
}

.kf-model-chip-icon {
  font-size: 16px;
  color: #ffffff;
}

.kf-page-header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.kf-btn {
  height: 36px;
  border-radius: 8px;
}

.kf-btn.kf-btn-ghost {
  background: #ffffff;
  border: 1px solid #d1d5dc;
  color: #0a0a0a;
}

.kf-btn.kf-btn-primary {
  background: linear-gradient(180deg, #2b7fff 0%, #00b8db 100%);
  border: none;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1),
    0 2px 4px -2px rgba(0, 0, 0, 0.1);
}

/* 图片悬浮操作 */
.img-actions {
  position: absolute;
  top: 12px;
  right: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  opacity: 0;
  transition: opacity 0.15s ease;
}

.image-container:hover .img-actions {
  opacity: 1;
}

.img-action-btn {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(229, 231, 235, 0.6);
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1),
    0 2px 4px -2px rgba(0, 0, 0, 0.1);
}

.img-tag {
  position: absolute;
  left: 12px;
  bottom: 12px;
  height: 23px;
  padding: 4px 12px;
  border-radius: 999px;
  background: linear-gradient(180deg, #2b7fff 0%, #00b8db 100%);
  color: #ffffff;
  font-size: 12px;
  font-weight: 500;
  line-height: 16px;
  display: inline-flex;
  align-items: center;
  white-space: nowrap;
  max-width: calc(100% - 24px);
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 首段关键帧确认横幅（Figma 24:262） */
.frame0-banner {
  background: #ffffff;
  border-bottom: 1px solid #e5e7eb;
  padding: 16px 0;
}

.frame0-banner-inner {
  border: 1px solid rgba(43, 127, 255, 0.3);
  border-radius: 10px;
  padding: 17px;
  background: linear-gradient(
    176deg,
    rgba(43, 127, 255, 0.15) 0%,
    rgba(0, 184, 219, 0.15) 100%
  );
  display: flex;
  align-items: center;
  gap: 16px;
}

.frame0-icon {
  width: 32px;
  height: 32px;
  border-radius: 999px;
  background: linear-gradient(135deg, #2b7fff 0%, #00b8db 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  flex: 0 0 32px;
}

.frame0-text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.frame0-title {
  font-size: 16px;
  font-weight: 600;
  line-height: 24px;
  background: linear-gradient(90deg, #2b7fff 0%, #00b8db 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.frame0-desc {
  font-size: 14px;
  line-height: 20px;
  color: #6a7282;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.frame0-confirm-btn {
  height: 36px;
  border: none;
  border-radius: 10px;
  padding: 0 24px;
  background: linear-gradient(166deg, #2b7fff 0%, #00b8db 100%);
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1),
    0 2px 4px -2px rgba(0, 0, 0, 0.1);
}

/* 预览弹窗（UI 自由发挥） */
.keyframe-preview-dialog :deep(.el-dialog) {
  border-radius: 14px;
  overflow: hidden;
}

.preview-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.preview-title {
  font-size: 14px;
  font-weight: 600;
  color: #1e2939;
}

.preview-frame {
  background: #0b0f1a;
  border-radius: 12px;
  overflow: hidden;
  height: 520px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.preview-image {
  width: 100%;
  height: 100%;
}

@media (max-width: 1400px) {
  .keyframe-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  /* 需求：9:16 在 <1400px 也保持每行 5 个 */
  .kf-portrait .keyframe-grid {
    grid-template-columns: repeat(5, minmax(0, 1fr));
  }
}

@media (max-width: 1100px) {
  .keyframe-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  /* 需求：9:16 在 <1100px 也保持每行 5 个（<=900px 仍会降到 1 列） */
  .kf-portrait .keyframe-grid {
    grid-template-columns: repeat(5, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .kf-page-header {
    flex-wrap: wrap;
    height: auto;
    gap: 12px;
    padding: 12px 16px;
  }
  .keyframes-content {
    padding: 16px;
  }
  .keyframe-grid {
    grid-template-columns: 1fr;
  }
}
</style>
