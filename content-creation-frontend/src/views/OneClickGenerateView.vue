<template>
  <div class="one-click-generate">
    <!-- 二级头（位于内容区顶部，Header/Sidebar 由 MainContent 统一提供） -->
    <div class="oc-topbar">
      <div class="oc-topbar-left">
        <el-button text :icon="ArrowLeft" @click="handleBack" class="oc-back-btn">
          返回
        </el-button>
        <span class="oc-topbar-divider" />
        <h1 class="oc-title">一键生成</h1>
      </div>
      <div class="oc-topbar-right">
        <el-button
          type="default"
          class="oc-btn oc-btn-ghost"
          @click="goToOneStep"
        >
          一步生成
        </el-button>

        <!-- 设计图里的“继续”改为“重试”，忽略“完整脚本”按钮 -->
        <el-button 
          v-if="canRetry"
          type="default"
          class="oc-btn oc-btn-ghost"
          :loading="isRetrying"
          @click="handleRetry"
        >
          <el-icon><Refresh /></el-icon>
          重试
        </el-button>

        <el-button
          v-if="isCompleted && exportUrl"
          type="primary"
          class="oc-btn oc-btn-primary"
          @click="handleDownload"
        >
          <el-icon><Download /></el-icon>
          下载视频
        </el-button>

        <el-button
          v-if="isGenerating"
          type="danger"
          class="oc-btn oc-btn-danger"
          :loading="cancelLoading"
          @click="handleCancelGeneration"
        >
          {{ cancelLoading ? '正在终止...' : '终止生成' }}
        </el-button>
      </div>
    </div>

    <!-- 主内容区域 -->
    <div class="main-content oc-layout">
      <!-- 左侧进度面板 -->
      <div class="progress-panel">
        <div class="progress-header">
          <div class="progress-title">
            <h2>生成进度</h2>
            <span class="total-progress">{{ Math.round(totalProgress) }}%</span>
          </div>
        </div>

        <div class="oc-overall-progress" aria-label="总体进度条">
          <div
            class="oc-overall-progress-inner"
            :style="{ width: `${Math.max(0, Math.min(100, Math.round(totalProgress)))}%` }"
          />
        </div>
        
        <div class="progress-steps">
          <!-- 脚本生成步骤 -->
          <div
            class="step"
            :class="[getStepClass('script'), { active: activeStep === 'script' }]"
            role="button"
            tabindex="0"
            @click="set_active_step('script')"
            @keydown.enter.prevent="set_active_step('script')"
          >
            <div class="step-icon">
              <el-icon v-if="steps.script.status === 'completed'" class="success"><Check /></el-icon>
              <el-icon
                v-else-if="steps.script.status === 'failed' && is_maintenance_message(steps.script.message)"
                class="maintenance"
              ><Tools /></el-icon>
              <el-icon v-else-if="steps.script.status === 'failed'" class="error"><Close /></el-icon>
              <el-icon v-else-if="steps.script.status === 'processing'" class="processing"><Loading /></el-icon>
              <span v-else class="step-number">1</span>
            </div>
            <div class="step-content">
              <div class="step-title">脚本生成</div>
              <div class="step-desc">{{ steps.script.message }}</div>
              <el-progress 
                v-if="steps.script.status === 'processing'" 
                :percentage="steps.script.progress" 
                :show-text="false"
                :stroke-width="4"
              />
            </div>
          </div>

          <!-- 关键帧生成步骤 -->
          <div
            class="step"
            :class="[getStepClass('keyframes'), { active: activeStep === 'keyframes' }]"
            role="button"
            tabindex="0"
            @click="set_active_step('keyframes')"
            @keydown.enter.prevent="set_active_step('keyframes')"
          >
            <div class="step-icon">
              <el-icon v-if="steps.keyframes.status === 'completed'" class="success"><Check /></el-icon>
              <el-icon
                v-else-if="steps.keyframes.status === 'failed' && is_cancelled_message(steps.keyframes.message)"
                class="cancelled"
              ><Close /></el-icon>
              <el-icon
                v-else-if="steps.keyframes.status === 'failed' && is_maintenance_message(steps.keyframes.message)"
                class="maintenance"
              ><Tools /></el-icon>
              <el-icon v-else-if="steps.keyframes.status === 'failed'" class="error"><Close /></el-icon>
              <el-icon v-else-if="steps.keyframes.status === 'processing'" class="processing"><Loading /></el-icon>
              <span v-else class="step-number">2</span>
            </div>
            <div class="step-content">
              <div class="step-title">关键帧生成</div>
              <div class="step-desc">{{ steps.keyframes.message }}</div>
              <div v-if="steps.keyframes.status === 'processing'" class="step-detail">
                {{ steps.keyframes.current }} / {{ steps.keyframes.total }}
              </div>
              <el-progress 
                v-if="steps.keyframes.status === 'processing'" 
                :percentage="steps.keyframes.progress" 
                :show-text="false"
                :stroke-width="4"
              />
            </div>
          </div>

          <!-- 视频生成步骤 -->
          <div
            class="step"
            :class="[getStepClass('videos'), { active: activeStep === 'videos' }]"
            role="button"
            tabindex="0"
            @click="set_active_step('videos')"
            @keydown.enter.prevent="set_active_step('videos')"
          >
            <div class="step-icon">
              <el-icon v-if="steps.videos.status === 'completed'" class="success"><Check /></el-icon>
              <el-icon
                v-else-if="steps.videos.status === 'failed' && is_cancelled_message(steps.videos.message)"
                class="cancelled"
              ><Close /></el-icon>
              <el-icon
                v-else-if="steps.videos.status === 'failed' && is_maintenance_message(steps.videos.message)"
                class="maintenance"
              ><Tools /></el-icon>
              <el-icon v-else-if="steps.videos.status === 'failed'" class="error"><Close /></el-icon>
              <el-icon v-else-if="steps.videos.status === 'processing'" class="processing"><Loading /></el-icon>
              <span v-else class="step-number">3</span>
            </div>
            <div class="step-content">
              <div class="step-title">视频生成</div>
              <div class="step-desc">{{ steps.videos.message }}</div>
              <div v-if="steps.videos.status === 'processing'" class="step-detail">
                {{ steps.videos.current }} / {{ steps.videos.total }}
              </div>
              <el-progress 
                v-if="steps.videos.status === 'processing'" 
                :percentage="steps.videos.progress" 
                :show-text="false"
                :stroke-width="4"
              />
            </div>
          </div>

          <!-- 音频合成步骤 -->
          <div
            class="step"
            :class="[getStepClass('audio'), { active: activeStep === 'audio' }]"
            role="button"
            tabindex="0"
            @click="set_active_step('audio')"
            @keydown.enter.prevent="set_active_step('audio')"
          >
            <div class="step-icon">
              <el-icon v-if="steps.audio.status === 'completed'" class="success"><Check /></el-icon>
              <el-icon
                v-else-if="steps.audio.status === 'failed' && is_cancelled_message(steps.audio.message)"
                class="cancelled"
              ><Close /></el-icon>
              <el-icon
                v-else-if="steps.audio.status === 'failed' && is_maintenance_message(steps.audio.message)"
                class="maintenance"
              ><Tools /></el-icon>
              <el-icon v-else-if="steps.audio.status === 'failed'" class="error"><Close /></el-icon>
              <el-icon v-else-if="steps.audio.status === 'processing'" class="processing"><Loading /></el-icon>
              <span v-else class="step-number">4</span>
            </div>
            <div class="step-content">
              <div class="step-title">音频合成</div>
              <div class="step-desc">{{ steps.audio.message }}</div>
              <div v-if="steps.audio.status === 'processing'" class="step-detail">
                {{ steps.audio.current }} / {{ steps.audio.total }}
              </div>
              <el-progress 
                v-if="steps.audio.status === 'processing'" 
                :percentage="steps.audio.progress" 
                :show-text="false"
                :stroke-width="4"
              />
            </div>
          </div>

          <!-- 视频合成步骤 -->
          <div
            class="step"
            :class="[getStepClass('export'), { active: activeStep === 'export' }]"
            role="button"
            tabindex="0"
            @click="set_active_step('export')"
            @keydown.enter.prevent="set_active_step('export')"
          >
            <div class="step-icon">
              <el-icon v-if="steps.export.status === 'completed'" class="success"><Check /></el-icon>
              <el-icon
                v-else-if="steps.export.status === 'failed' && is_cancelled_message(steps.export.message)"
                class="cancelled"
              ><Close /></el-icon>
              <el-icon
                v-else-if="steps.export.status === 'failed' && is_maintenance_message(steps.export.message)"
                class="maintenance"
              ><Tools /></el-icon>
              <el-icon v-else-if="steps.export.status === 'failed'" class="error"><Close /></el-icon>
              <el-icon v-else-if="steps.export.status === 'processing'" class="processing"><Loading /></el-icon>
              <span v-else class="step-number">5</span>
            </div>
            <div class="step-content">
              <div class="step-title">视频合成导出</div>
              <div class="step-desc">{{ steps.export.message }}</div>
              <el-progress 
                v-if="steps.export.status === 'processing'" 
                :percentage="steps.export.progress" 
                :show-text="false"
                :stroke-width="4"
              />
            </div>
          </div>
        </div>

        <!-- 设计图不包含这里的底部按钮（已移动到顶部二级头），保留占位避免布局跳变 -->
      </div>

      <!-- 右侧预览面板 -->
      <div class="preview-panel">
        <div class="preview-header">
          <h2>实时预览</h2>
        </div>

        <div class="preview-content">
          <!-- 脚本预览 -->
          <div v-if="activeStep === 'script'" class="script-preview">
            <div v-if="scriptContent" class="script-text">
              <ScriptPrettyView :content="scriptContent" />
            </div>
            <div v-else class="empty-state">
              <el-icon :size="48"><Document /></el-icon>
              <p>等待脚本生成...</p>
            </div>
          </div>

          <!-- 关键帧预览 -->
          <div v-if="activeStep === 'keyframes'" class="keyframes-preview">
            <div v-if="keyframes.length > 0">
              <div class="preview-actions">
                <el-button 
                  v-if="completedKeyframes.length > 0"
                  type="primary" 
                  size="small"
                  @click="handleDownloadAllKeyframes"
                >
                  <el-icon><Download /></el-icon>
                  下载全部图片 ({{ completedKeyframes.length }})
                </el-button>
              </div>
              <div class="keyframes-grid">
                <div 
                  v-for="(kf, index) in keyframes" 
                  :key="kf.id" 
                  class="keyframe-item"
                  :style="preview_card_style"
                  :class="{ 
                    'generating': kf.status?.toLowerCase() === 'generating', 
                    'failed': kf.status?.toLowerCase() === 'failed',
                    'completed': kf.status?.toLowerCase() === 'completed'
                  }"
                >
                  <div class="keyframe-index">{{ `第${index + 1}段` }}</div>
                  <div v-if="kf.imageUrl || kf.image_url" class="keyframe-image-container">
                    <img
                      :src="kf.imageUrl || kf.image_url"
                      :alt="`关键帧 ${index}`"
                    />
                    <div class="keyframe-overlay">
                      <el-button
                        size="small"
                        circle
                        @click="openImagePreview(kf, index)"
                        title="放大预览"
                      >
                        <el-icon><ZoomIn /></el-icon>
                      </el-button>
                      <el-button 
                        size="small" 
                        circle
                        @click="handleDownloadKeyframe(kf)"
                      >
                        <el-icon><Download /></el-icon>
                      </el-button>
                    </div>
                  </div>
                  <div v-else-if="kf.status?.toLowerCase() === 'generating'" class="keyframe-loading">
                    <el-icon class="is-loading"><Loading /></el-icon>
                    <span>生成中...</span>
                  </div>
                  <div v-else-if="kf.status?.toLowerCase() === 'failed'" class="keyframe-failed">
                  <template v-if="cancelled_by_user || is_cancelled_message(kf.errorMessage)">
                    <el-icon class="cancel-icon"><CircleCloseFilled /></el-icon>
                    <span class="cancel-text">已取消</span>
                    <span class="cancel-sub">已按你的操作终止生成</span>
                  </template>
                  <template v-else>
                    <div class="failed-icon">🔧</div>
                    <span class="failed-text">模型维护中</span>
                    <span class="failed-sub">请稍后重试</span>
                  </template>
                  </div>
                  <div v-else class="keyframe-pending">
                    <span>{{ cancelled_by_user ? '已取消' : '等待中...' }}</span>
                  </div>
                </div>
              </div>
            </div>
            <div v-else class="empty-state">
              <el-icon :size="48"><Picture /></el-icon>
              <p>等待关键帧生成...</p>
            </div>
          </div>

          <!-- 视频预览 -->
          <div v-if="activeStep === 'videos'" class="videos-preview">
            <div v-if="videos.length > 0" class="videos-grid">
              <div 
                v-for="(video, index) in videos" 
                :key="video.id" 
                class="video-item"
                :style="preview_card_style"
                :class="{ 
                  'generating': video.status?.toLowerCase() === 'generating', 
                  'failed': video.status?.toLowerCase() === 'failed',
                  'completed': video.status?.toLowerCase() === 'completed'
                }"
              >
                <div class="video-header">
                  <div class="video-index">{{ index + 1 }}</div>
                  <div v-if="video.videoUrl || video.video_url" class="video-header-actions">
                  <el-button 
                      size="small"
                      circle
                      @click="openVideoPreview(video, index)"
                      title="放大预览"
                      class="download-btn"
                    >
                      <el-icon><ZoomIn /></el-icon>
                    </el-button>
                    <el-button 
                    size="small"
                    circle
                    @click="handleDownloadVideo(video)"
                    class="download-btn"
                      title="下载视频"
                  >
                    <el-icon><Download /></el-icon>
                  </el-button>
                  </div>
                </div>
                <video 
                  v-if="video.videoUrl || video.video_url" 
                  :src="video.videoUrl || video.video_url" 
                  controls 
                  muted
                  preload="metadata"
                />
                <div v-else-if="video.status?.toLowerCase() === 'generating'" class="video-loading">
                  <el-icon class="is-loading"><Loading /></el-icon>
                  <span>生成中...</span>
                  <!-- 视频重试过程中不展示“失败/重试”提示（避免用户误解为最终失败） -->
                </div>
                <div v-else-if="video.status?.toLowerCase() === 'failed'" class="video-failed">
                  <template v-if="cancelled_by_user || is_cancelled_message(video.errorMessage)">
                    <el-icon class="cancel-icon"><CircleCloseFilled /></el-icon>
                    <span class="cancel-text">已取消</span>
                    <span class="cancel-sub">已按你的操作终止生成</span>
                  </template>
                  <template v-else>
                    <div class="failed-icon">🔧</div>
                    <span class="failed-text">模型维护中</span>
                    <span class="failed-sub">请稍后重试</span>
                  </template>
                </div>
                <div v-else class="video-pending">
                  <span>{{ cancelled_by_user ? '已取消' : '等待中...' }}</span>
                </div>
              </div>
            </div>
            <div v-else class="empty-state">
              <el-icon :size="48"><VideoPlay /></el-icon>
              <p>等待视频生成...</p>
            </div>
          </div>

          <!-- 音频预览（自由发挥：主题一致 + 精致） -->
          <div v-if="activeStep === 'audio'" class="audio-preview">
            <div v-if="videos.length > 0" class="audio-grid">
              <div
                v-for="(v, idx) in videos"
                :key="v.id"
                class="audio-card"
              >
                <div class="audio-card-head">
                  <div class="audio-tag">{{ `第${idx + 1}段` }}</div>
                  <div class="audio-status" :class="`s-${String(v.audioStatus || v.audio_status || 'pending')}`">
                    {{ normalize_audio_status(v.audioStatus || v.audio_status) }}
                  </div>
                </div>

                <div class="audio-card-body">
                <div v-if="v.audioUrl || v.audio_url" class="audio-player">
                    <audio
                      controls
                      preload="metadata"
                      :src="`/api/files/proxy?url=${encodeURIComponent(v.audioUrl || v.audio_url)}`"
                    />
                </div>
                <div v-else class="audio-empty">
                    {{ cancelled_by_user ? '已取消' : '等待生成音频...' }}
                </div>
                <div v-if="v.audioErrorMessage || v.audio_error_message" class="audio-error">
                  {{ formatErrorMessage(v.audioErrorMessage || v.audio_error_message) }}
                  </div>
                </div>
              </div>
            </div>
            <div v-else class="empty-state">
              <p>等待视频生成后才能预览音频...</p>
            </div>
          </div>

          <!-- 合成导出预览：只在“视频合成导出”步骤显示最终视频 -->
          <div v-if="activeStep === 'export'" class="export-preview">
            <div v-if="exportUrl" class="final-video">
              <div class="final-video-header">
                <h3>最终合成视频</h3>
                <div class="final-video-actions">
                  <el-button
                    size="small"
                    @click="handleReExport"
                    :disabled="steps.export.status === 'processing'"
                  >
                    重新导出（修复字幕）
                  </el-button>
                <el-button
                  size="small"
                  circle
                  @click="openFinalVideoPreview"
                  title="放大预览"
                >
                  <el-icon><ZoomIn /></el-icon>
                </el-button>
                </div>
              </div>
              <video
                :src="exportUrl"
                controls
                class="final-video-player"
                preload="metadata"
              />
            </div>
            <div v-else class="empty-state">
              <p>等待视频合成导出...</p>
            </div>
          </div>
        </div>

        <!-- 图片预览弹窗 -->
        <el-dialog
          v-model="imagePreviewVisible"
          :show-close="true"
          class="media-preview-dialog"
          width="900px"
          align-center
          :append-to-body="true"
          :close-on-click-modal="true"
          :close-on-press-escape="true"
        >
          <div v-if="imagePreviewSrc" class="preview-body">
            <div class="preview-meta">
              <div class="preview-title">{{ imagePreviewTitle || '图片预览' }}</div>
            </div>
            <div class="preview-frame">
              <el-image :src="imagePreviewSrc" fit="contain" class="preview-image">
                <template #error>
                  <div class="preview-error">图片加载失败</div>
                </template>
              </el-image>
            </div>
          </div>
        </el-dialog>

        <!-- 视频预览弹窗 -->
        <el-dialog
          v-model="videoPreviewVisible"
          :show-close="true"
          class="media-preview-dialog"
          width="980px"
          align-center
          :append-to-body="true"
          :close-on-click-modal="true"
          :close-on-press-escape="true"
        >
          <div v-if="videoPreviewSrc" class="preview-body">
            <div class="preview-meta">
              <div class="preview-title">{{ videoPreviewTitle || '视频预览' }}</div>
            </div>
            <div class="preview-video-frame">
              <video
                :src="videoPreviewSrc"
                controls
                autoplay
                class="preview-video-player"
                preload="metadata"
              />
            </div>
          </div>
        </el-dialog>

      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  ArrowLeft, Check, Close, Loading, Download, 
  Document, Picture, VideoPlay, Warning, Tools, ZoomIn, Refresh, CircleCloseFilled
} from '@element-plus/icons-vue'
import { 
  scriptApi, keyframeApi, videoApi, projectApi, modelApi 
} from '@/api'
import { useProjectStore } from '@/stores'
import JSZip from 'jszip'
import ScriptPrettyView from '@/components/common/ScriptPrettyView.vue'

interface StepStatus {
  status: 'pending' | 'processing' | 'completed' | 'failed'
  message: string
  progress: number
  current?: number
  total?: number
  retryCount?: number
}

const route = useRoute()
const router = useRouter()
const projectStore = useProjectStore()

// 路由参数
const projectId = computed(() => {
  const id = route.params.projectId
  // 如果是 'new'，返回 null，表示需要创建新项目
  if (id === 'new') return null
  return id ? parseInt(id as string, 10) : null
})

const inspiration = computed(() => route.query.inspiration as string || '')

const query_aspect_ratio = computed(() => {
  const from_query = String(route.query.aspectRatio || route.query.aspect_ratio || '')
  return from_query ? normalize_aspect_ratio(from_query) : ''
})

const has_persisted_project_aspect_ratio = (p: any): boolean => {
  const v = String(p?.aspectRatio || p?.aspect_ratio || '').trim()
  return v === '9:16' || v === '16:9'
}

const infer_aspect_ratio_from_image_url = async (
  url: string,
): Promise<'9:16' | '16:9' | null> => {
  const src = `/api/files/proxy?url=${encodeURIComponent(String(url))}`
  return await new Promise((resolve) => {
    const img = new Image()
    img.onload = () => {
      const w = Number((img as any).naturalWidth || (img as any).width || 0)
      const h = Number((img as any).naturalHeight || (img as any).height || 0)
      if (!w || !h) return resolve(null)
      resolve(h >= w ? '9:16' : '16:9')
    }
    img.onerror = () => resolve(null)
    img.src = src
  })
}

const persist_project_aspect_ratio_if_needed = async (
  project: any,
  ratio: string,
): Promise<void> => {
  const desired = normalize_aspect_ratio(String(ratio || ''))
  if (!project?.id || !desired) return
  if (String(project?.aspectRatio || '').trim() === desired) return
  try {
    await projectApi.updateProject(Number(project.id), { aspectRatio: desired } as any)
    projectStore.updateCurrentProject({ aspectRatio: desired } as any)
  } catch (e) {
    console.warn('持久化项目比例失败:', e)
  }
}

const requested_aspect_ratio = computed(() => {
  if (query_aspect_ratio.value) return query_aspect_ratio.value
  const from_project = String((projectStore.currentProject as any)?.aspectRatio || '')
  return normalize_aspect_ratio(from_project || '16:9')
})

const project_aspect_ratio = computed(() => {
  return requested_aspect_ratio.value
})

const preview_card_style = computed(() => {
  // 适配 9:16 / 16:9：让卡片按项目比例自适应高度（与分步生成一致）
  const aspect = project_aspect_ratio.value === '9:16' ? '9 / 16' : '16 / 9'
  return {
    'aspect-ratio': aspect,
  } as Record<string, string>
})

const normalize_audio_status = (status: string | undefined): string => {
  const s = String(status || 'pending').toLowerCase()
  if (cancelled_by_user.value) return '已取消'
  if (s === 'completed' || s === 'succeeded') return '已完成'
  if (s === 'failed') return is_cancelled_message(status) ? '已取消' : '模型维护中'
  if (s === 'generating' || s === 'processing') return '生成中'
  return '等待中'
}

// 步骤状态
const steps = ref<{
  script: StepStatus
  keyframes: StepStatus
  videos: StepStatus
  audio: StepStatus
  export: StepStatus
}>({
  script: { status: 'pending', message: '等待开始', progress: 0 },
  keyframes: { status: 'pending', message: '等待脚本完成', progress: 0, current: 0, total: 0 },
  videos: { status: 'pending', message: '等待关键帧完成', progress: 0, current: 0, total: 0 },
  audio: { status: 'pending', message: '等待视频完成', progress: 0, current: 0, total: 0 },
  export: { status: 'pending', message: '等待视频完成', progress: 0 }
})

// 数据
const scriptContent = ref('')
const keyframes = ref<any[]>([])
const videos = ref<any[]>([])
const exportUrl = ref('')
const projectName = ref('')

const imagePreviewVisible = ref(false)
const imagePreviewSrc = ref('')
const imagePreviewTitle = ref('')

const videoPreviewVisible = ref(false)
const videoPreviewSrc = ref('')
const videoPreviewTitle = ref('')

const openImagePreview = (kf: any, index: number) => {
  const src = kf?.imageUrl || kf?.image_url
  if (!src) return
  imagePreviewSrc.value = String(src)
  imagePreviewTitle.value = `关键帧 ${index}`
  imagePreviewVisible.value = true
}

const openVideoPreview = (video: any, index: number) => {
  const src = video?.videoUrl || video?.video_url
  if (!src) return
  videoPreviewSrc.value = String(src)
  videoPreviewTitle.value = `第 ${index + 1} 段视频`
  videoPreviewVisible.value = true
}

const openFinalVideoPreview = () => {
  if (!exportUrl.value) return
  videoPreviewSrc.value = String(exportUrl.value)
  videoPreviewTitle.value = '最终合成视频'
  videoPreviewVisible.value = true
}

// 配置
const imageModel = ref('')
const aspectRatio = ref('16:9')
const quality = ref('')
const videoModel = ref('')

const ALLOWED_ASPECT_RATIOS = ['9:16', '16:9'] as const
const normalize_aspect_ratio = (ratio?: string): string => {
  const r = String(ratio || '')
  return (ALLOWED_ASPECT_RATIOS as unknown as string[]).includes(r) ? r : '16:9'
}
const pick_default_aspect_ratio = (ratios?: string[]): string => {
  const list = Array.isArray(ratios) ? ratios : []
  const allow = new Set<string>(ALLOWED_ASPECT_RATIOS as unknown as string[])
  const picked = list.find(r => allow.has(String(r)))
  return picked ? String(picked) : '16:9'
}

// 右侧预览由左侧步骤驱动（不再使用右上角 Tab）
type PreviewStep = 'script' | 'keyframes' | 'videos' | 'audio' | 'export'
const activeStep = ref<PreviewStep>('script')
const active_step_locked_by_user = ref(false)

const set_active_step = (step: PreviewStep) => {
  activeStep.value = step
  active_step_locked_by_user.value = true
}

const auto_set_active_step = (step: PreviewStep) => {
  if (!active_step_locked_by_user.value) {
    activeStep.value = step
  }
}

// 状态
const isRetrying = ref(false)
const isComponentMounted = ref(true) // 添加组件挂载状态标志
const pollingTimer = ref<ReturnType<typeof setTimeout> | null>(null) // 修改类型为 setTimeout 的返回值
const cancelLoading = ref(false) // 终止按钮加载状态
const auto_export_triggered = ref(false) // 防止进入页面后重复触发导出

// 计算属性
// 是否正在生成
const isGenerating = computed(() => {
  return steps.value.keyframes.status === 'processing' || 
         steps.value.videos.status === 'processing' ||
         steps.value.audio.status === 'processing' ||
         steps.value.export.status === 'processing'
})

const totalProgress = computed(() => {
  const weights = { script: 10, keyframes: 30, videos: 35, audio: 15, export: 10 }
  let progress = 0
  
  if (steps.value.script.status === 'completed') progress += weights.script
  else if (steps.value.script.status === 'processing') progress += (steps.value.script.progress / 100) * weights.script
  
  if (steps.value.keyframes.status === 'completed') progress += weights.keyframes
  else if (steps.value.keyframes.status === 'processing') progress += (steps.value.keyframes.progress / 100) * weights.keyframes
  
  if (steps.value.videos.status === 'completed') progress += weights.videos
  else if (steps.value.videos.status === 'processing') progress += (steps.value.videos.progress / 100) * weights.videos

  if (steps.value.audio.status === 'completed') progress += weights.audio
  else if (steps.value.audio.status === 'processing') progress += (steps.value.audio.progress / 100) * weights.audio
  
  if (steps.value.export.status === 'completed') progress += weights.export
  else if (steps.value.export.status === 'processing') progress += (steps.value.export.progress / 100) * weights.export
  
  return progress
})

const canRetry = computed(() => {
  // 如果流程已经全部完成（导出成功），则不再显示重试按钮，避免给用户造成困惑
  // 用户如果需要修复，应该使用分步生成模式或者重新生成
  if (isCompleted.value) return false

  // 导出失败也允许重试（仅重新触发 export）
  return steps.value.audio.status === 'failed' ||
         steps.value.export.status === 'failed' ||
         steps.value.keyframes.status === 'failed' || 
         steps.value.videos.status === 'failed' ||
         keyframes.value.some(k => k.status?.toLowerCase() === 'failed') ||
         videos.value.some(v => v.status?.toLowerCase() === 'failed')
})

const isCompleted = computed(() => {
  return steps.value.export.status === 'completed'
})

const completedKeyframes = computed(() => {
  return keyframes.value.filter(kf => 
    (kf.imageUrl || kf.image_url) && kf.status?.toLowerCase() === 'completed'
  )
})

// 方法
const getStepClass = (step: string) => {
  const s = steps.value[step as keyof typeof steps.value]
  return {
    'pending': s.status === 'pending',
    'processing': s.status === 'processing',
    'completed': s.status === 'completed',
    'failed': s.status === 'failed'
  }
}

// 下载单个关键帧
const handleDownloadKeyframe = (keyframe: any) => {
  const imageUrl = keyframe.imageUrl || keyframe.image_url
  if (!imageUrl) {
    ElMessage.warning('图片地址不存在')
    return
  }
  
  try {
    // 直接使用 a 标签下载，避免页面跳转和抖动
    const link = document.createElement('a')
    link.href = imageUrl
    link.download = `keyframe_${keyframe.segmentId || keyframe.id}.png`
    // 不设置 target，避免打开新页面
    link.style.display = 'none'  // 避免页面抖动
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

// 下载全部关键帧（打包成ZIP）
const handleDownloadAllKeyframes = async () => {
  const completed = completedKeyframes.value
  
  if (completed.length === 0) {
    ElMessage.warning('没有可下载的图片')
    return
  }
  
  const loadingMsg = ElMessage.info({
    message: `正在打包 ${completed.length} 张图片...`,
    duration: 0
  })
  
  try {
    const zip = new JSZip()
    const folder = zip.folder('keyframes')
    
    // 使用后端代理下载图片，避免CORS问题
    const downloadPromises = completed.map(async (keyframe, index) => {
      try {
        const imageUrl = keyframe.imageUrl || keyframe.image_url
        // 使用后端代理API
        const proxyUrl = `/api/files/proxy?url=${encodeURIComponent(imageUrl)}`
        const response = await fetch(proxyUrl)
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }
        const blob = await response.blob()
        const filename = `keyframe_${String(index + 1).padStart(2, '0')}_${keyframe.segmentId || keyframe.id}.png`
        return { filename, blob }
      } catch (error) {
        console.error(`下载图片失败:`, error)
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
    
    if (successCount < completed.length) {
      ElMessage.warning(`成功打包 ${successCount}/${completed.length} 张图片`)
    } else {
      ElMessage.success(`成功打包下载 ${successCount} 张图片`)
    }
  } catch (error) {
    loadingMsg.close()
    console.error('打包下载失败:', error)
    ElMessage.error('打包下载失败，请重试')
  }
}

// 下载单个视频
const handleDownloadVideo = async (video: any) => {
  const videoUrl = video.videoUrl || video.video_url
  if (!videoUrl) {
    ElMessage.warning('视频地址不存在')
    return
  }
  
  const loadingMsg = ElMessage.info({
    message: '正在下载视频...',
    duration: 0
  })
  
  try {
    // 使用后端代理API下载，设置正确的响应头强制下载
    const proxyUrl = `/api/files/proxy?url=${encodeURIComponent(videoUrl)}`
    const response = await fetch(proxyUrl)
    
    if (!response.ok) {
      throw new Error('下载失败')
    }
    
    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `video_segment_${video.segmentIndex !== undefined ? video.segmentIndex + 1 : video.id}.mp4`
    link.style.display = 'none'
    document.body.appendChild(link)
    link.click()
    
    // 清理
    setTimeout(() => {
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
    }, 100)
    
    loadingMsg.close()
    ElMessage.success('视频下载成功')
  } catch (error) {
    loadingMsg.close()
    console.error('下载视频失败:', error)
    ElMessage.error('下载视频失败，请重试')
  }
}

// 格式化错误信息（只保留中文部分，去掉详细的技术错误）
const formatErrorMessage = (errorMessage: string | undefined): string => {
  if (!errorMessage) return ''
  
  let result = errorMessage
  
  // 1. 识别常见英文错误模式，映射为中文
  const errorMappings = [
    // 用户取消（必须优先于“模型维护”归类）
    { pattern: /已取消后续生成/i, message: '已取消' },
    { pattern: /用户取消/i, message: '已取消' },
    { pattern: /用户中断/i, message: '已取消' },
    { pattern: /cancelled|canceled/i, message: '已取消' },

    // 模型维护/不可用（优先级最高：避免暴露技术错误）
    { pattern: /模型维护中/i, message: '模型维护中' },
    { pattern: /model maintenance/i, message: '模型维护中' },
    { pattern: /maintenance/i, message: '模型维护中' },
    // 429/限流：按你的要求统一归类为“模型维护中”（不暴露具体供应商与技术错误）
    { pattern: /\b429\b/i, message: '模型维护中' },
    { pattern: /too many requests/i, message: '模型维护中' },
    { pattern: /cvsync2asynctask/i, message: '模型维护中' },
    { pattern: /visual\.volcengineapi\.com/i, message: '模型维护中' },
    { pattern: /前序关键帧生成失败/i, message: '模型维护中' },
    { pattern: /首段关键帧生成失败/i, message: '模型维护中' },
    { pattern: /jimeng/i, message: '模型维护中' },
    { pattern: /即梦/i, message: '模型维护中' },
    { pattern: /all models unavailable/i, message: '模型维护中' },
    { pattern: /所有型号均不可用/i, message: '模型维护中' },
    { pattern: /所有模型均不可用/i, message: '模型维护中' },
    { pattern: /model.*not available/i, message: '模型维护中' },
    { pattern: /视频生成有失败项/i, message: '模型维护中' },
    { pattern: /没有视频生成成功/i, message: '模型维护中' },

    // 真人照片相关
    { pattern: /violation.*photorealistic people/i, message: '不支持真人照片' },
    { pattern: /photorealistic.*not supported/i, message: '不支持真人照片' },
    { pattern: /contains.*real.*person/i, message: '不支持真人照片' },
    
    // 资源配额相关
    { pattern: /RESOURCE_EXHAUSTED/i, message: '资源配额已用尽' },
    { pattern: /quota.*exceeded/i, message: '配额已超限' },
    { pattern: /rate limit/i, message: '请求频率过高' },
    
    // 上传失败
    { pattern: /upload.*failed/i, message: '上传失败' },
    { pattern: /上传图片失败/i, message: '上传图片失败' },
    
    // 生成失败
    { pattern: /generation.*failed/i, message: '生成失败' },
    { pattern: /Failed to generate/i, message: '生成失败' },
    
    // 超时
    { pattern: /timeout/i, message: '请求超时' },
    { pattern: /timed out/i, message: '请求超时' },
    
    // 网络错误
    { pattern: /network error/i, message: '网络错误' },
    { pattern: /connection.*failed/i, message: '连接失败' },
    // TLS/SSL：按你的要求统一归类为维护中（避免暴露技术细节）
    { pattern: /tls\/ssl/i, message: '模型维护中' },
    { pattern: /_ssl\.c/i, message: '模型维护中' },
    { pattern: /connection has been closed/i, message: '模型维护中' },
    { pattern: /eof/i, message: '模型维护中' }
  ]
  
  // 检查是否匹配任何错误模式
  for (const { pattern, message } of errorMappings) {
    if (pattern.test(result)) {
      result = message
      return result
    }
  }
  
  // 2. 如果没有匹配到特定模式，尝试提取中文部分
  const patterns = [
    /上传图片失败[,，]?\s*重试.*$/i,  // 匹配"上传图片失败, 重试: xxx"后面的内容
    /上传图片失败[,，]?\s*veo.*$/i,   // 匹配"上传图片失败, veo xxx"后面的内容
    /视频生成失败[（(]所有型号均不可用[,，].*$/i,  // 匹配"视频生成失败（所有型号均不可用，xxx"后面的内容
    /Failed to generate:.*$/i,        // 匹配"Failed to generate: xxx"后面的内容
  ]
  
  for (const pattern of patterns) {
    if (pattern.test(result)) {
      // 提取中文关键词
      if (result.includes('上传图片失败')) {
        result = '上传图片失败'
      } else if (result.includes('视频生成失败')) {
        result = '视频生成失败'
      } else if (result.includes('所有型号均不可用')) {
        result = '模型维护中'
      } else {
        result = result.replace(pattern, '生成失败')
  }
      break
    }
  }
  
  // 3. 移除技术细节
  // 如果包含"重试:"，只保留到"重试:"之前的内容
  const retryIndex = result.indexOf('重试:')
  if (retryIndex > 0) {
    result = result.substring(0, retryIndex).trim()
    result = result.replace(/[,，。]+$/, '')
  }
  
  // 如果包含"violation"等技术信息，只保留到这之前的内容
  const techPatterns = [
    'violation:',
    'veo upload',
    'unexpected error',
    'RESOURCE_EXHAUSTED',
    'error code',
    'stack trace'
  ]
  
  for (const tech of techPatterns) {
    const techIndex = result.toLowerCase().indexOf(tech.toLowerCase())
    if (techIndex > 0) {
      result = result.substring(0, techIndex).trim()
      result = result.replace(/[,，。、]+$/, '')
      break
    }
  }
  
  // 4. 移除括号内的英文内容
  result = result.replace(/[（(][^）)]*[a-zA-Z]+[^）)]*[）)]/g, '')
  
  // 5. 最终清理
  result = result.trim().replace(/[,，。、]+$/, '')
  
  return result || '生成失败'
}


const is_maintenance_message = (message: string | undefined): boolean => {
  return formatErrorMessage(message) === '模型维护中'
}

const is_cancelled_message = (message: string | undefined): boolean => {
  return formatErrorMessage(message) === '已取消'
}

const cancelled_by_user = ref(false)

// 终止生成
const handleCancelGeneration = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要终止当前的生成任务吗？已生成的内容将保留，未完成的任务将被取消。',
      '确认终止',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    cancelLoading.value = true
    cancelled_by_user.value = true
    
    const scriptId = projectStore.currentScript?.id
    if (!scriptId) {
      ElMessage.error('脚本ID不存在')
      return
    }
    
    // 停止轮询（在调用 API 之前）
    isComponentMounted.value = false
    if (pollingTimer.value) {
      clearTimeout(pollingTimer.value)
      pollingTimer.value = null
    }
    
    // 调用取消API
    await scriptApi.cancelGeneration(scriptId)
    
    // 等待一下让后端完成更新
    await new Promise(resolve => setTimeout(resolve, 500))
    
    // 强制刷新关键帧和视频状态
    try {
      const kfResponse = await keyframeApi.getKeyframesByScript(scriptId)
      const kfs = kfResponse.keyframes || []
      keyframes.value = [...kfs] // 使用新数组触发响应式更新
      projectStore.updateKeyframes(kfs)
      
      const vidResponse = await videoApi.getVideoSegmentsByScript(scriptId)
      const vids = vidResponse.videoSegments || []
      videos.value = [...vids] // 使用新数组触发响应式更新
      projectStore.updateVideoSegments(vids)
    } catch (error) {
      console.error('刷新状态失败:', error)
    }
    
    // 重新检查进度
    await checkExistingProgress()
    
    // 重置重试状态，确保重试按钮可用
    isRetrying.value = false
    
    // 注意：导出/FFmpeg 等耗时任务可能仍在后台停止中，这里不再误报“已终止”
    ElMessage.success('终止请求已提交')
    
    // 重新启用组件挂载标志
    isComponentMounted.value = true
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('终止生成失败:', error)
      ElMessage.error(error?.message || '终止生成失败')
    }
  } finally {
    cancelLoading.value = false
  }
}

const handleBack = () => {
    router.push({ name: 'InspirationInput' })
}

const goToOneStep = () => {
  router.push({ name: 'OneStepGenerate' })
}

const handleDownload = async () => {
  if (!exportUrl.value) {
    ElMessage.warning('视频地址不存在')
    return
  }
  
  const loadingMsg = ElMessage.info({
    message: '正在下载视频...',
    duration: 0
  })
  
  try {
    // 使用后端代理API下载，避免页面抖动
    const proxyUrl = `/api/files/proxy?url=${encodeURIComponent(exportUrl.value)}`
    const response = await fetch(proxyUrl)
    
    if (!response.ok) {
      throw new Error('下载失败')
    }
    
    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${projectName.value || 'video'}_final.mp4`
    link.style.display = 'none'
    document.body.appendChild(link)
    link.click()
    
    // 清理
    setTimeout(() => {
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
    }, 100)
    
    loadingMsg.close()
    ElMessage.success('视频下载成功')
  } catch (error) {
    loadingMsg.close()
    console.error('下载视频失败:', error)
    ElMessage.error('下载视频失败，请重试')
  }
}

// 加载模型配置
const loadModels = async () => {
  try {
    const imageModels = await modelApi.getImageModels()
    const models = Array.isArray(imageModels) ? imageModels : (imageModels?.data || [])
    
    // 一键生成图片模型默认策略：
    // - custom_style_1767597711851：优先 Seedream（失败由后端按链路降级到即梦）
    // - 其他：默认 nano-banana-pro（否则回退到第一个可用模型）
    const current_style =
      (projectStore.currentProject as any)?.script?.style ||
      (projectStore as any)?.currentScript?.style ||
      (route.query.style as string) ||
      ''
    const defaultModel =
      (current_style === 'custom_style_1767597711851'
        ? models.find((m: any) => m?.id === 'doubao-seedream-4-5-251128') ||
          models.find((m: any) => m?.id === 'jimeng_t2i_v40') ||
          null
        : null) ||
      models.find((m: any) => m?.id === 'nano-banana-pro') ||
      (models.length > 0 ? models[0] : null)
    
    if (defaultModel) {
      imageModel.value = defaultModel.id
      // 一键生成：优先使用创意页传入的比例（9:16 / 16:9），否则回退到模型可用比例
      const desired = requested_aspect_ratio.value
      const allow = new Set<string>(ALLOWED_ASPECT_RATIOS as unknown as string[])
      const modelSupports = Array.isArray(defaultModel.aspect_ratios)
        ? defaultModel.aspect_ratios.some((r: string) => allow.has(String(r)))
        : true
      aspectRatio.value = modelSupports
        ? desired
        : pick_default_aspect_ratio(defaultModel.aspect_ratios)
      if (defaultModel.qualities?.length > 0) {
        quality.value = defaultModel.qualities[0]
      }
    }

    // 加载视频模型
    const videoModelsRes = await videoApi.getVideoModels()
    const videoModels = Array.isArray(videoModelsRes)
      ? videoModelsRes
      : (videoModelsRes as any)?.data || (videoModelsRes as any)?.models || []

    // 一键生成默认优先：veo3.1-fast-ref -> sora-2 -> 豆包 -> 即梦（首帧 1080P）
    const preferredVideoModelIds = [
      'veo3.1-fast-ref',
      'sora-2',
      'doubao-seedance-1-5-pro-251215',
      'jimeng_i2v_first_v30_1080',
    ]
    const defaultVideoModel =
      videoModels.find((m: any) => preferredVideoModelIds.includes(m?.id)) ||
      (videoModels.length > 0 ? videoModels[0] : null)

    if (defaultVideoModel) {
      videoModel.value = defaultVideoModel.id
    }
  } catch (error) {
    console.error('加载模型配置失败:', error)
  }
}

// 第一步：生成脚本
const generateScript = async () => {
  if (!inspiration.value) {
    ElMessage.error('缺少创意描述')
    return false
  }

  // 自动切到脚本预览
  auto_set_active_step('script')

  steps.value.script.status = 'processing'
  steps.value.script.message = '正在生成脚本...'
  steps.value.script.progress = 30

  try {
    // 使用现有脚本或生成新脚本
    if (projectStore.currentScript?.content) {
      scriptContent.value = projectStore.currentScript.content
      steps.value.script.progress = 100
      steps.value.script.status = 'completed'
      steps.value.script.message = '脚本已就绪'
      return true
    }

    // 调用优化API生成脚本
    const scriptId = projectStore.currentScript?.id
    if (scriptId) {
      steps.value.script.progress = 50
      const enableSearch = route.query.enableSearch === 'true'
      const model = (route.query.model as string) || ''
      const response = await scriptApi.optimizeScript(scriptId, inspiration.value, model, enableSearch)
      scriptContent.value = response?.content || ''
      
      if (scriptContent.value) {
        steps.value.script.progress = 100
        steps.value.script.status = 'completed'
        steps.value.script.message = '脚本生成完成'
        return true
      }
    }

    throw new Error('脚本生成失败')
  } catch (error: any) {
    steps.value.script.status = 'failed'
    steps.value.script.message = error?.message || '脚本生成失败'
    return false
  }
}

// 第二步：生成关键帧
const generateKeyframes = async () => {
  const scriptId = projectStore.currentScript?.id
  if (!scriptId) {
    steps.value.keyframes.status = 'failed'
    steps.value.keyframes.message = '脚本ID不存在'
    return false
  }

  // 自动切到关键帧预览
  auto_set_active_step('keyframes')

  steps.value.keyframes.status = 'processing'
  steps.value.keyframes.message = '正在生成关键帧...'
  steps.value.keyframes.progress = 0

  try {
    // 调用生成关键帧API（生成所有帧）
    const request: any = {
      script_id: scriptId,
      model: imageModel.value,
      aspect_ratio: normalize_aspect_ratio(aspectRatio.value),
      only_first_frame: false
    }
    if (quality.value) request.quality = quality.value
    
    // 添加参考图URLs（如果有）
    if (projectStore.referenceImageUrls.length > 0) {
      console.log('Using reference images:', projectStore.referenceImageUrls)
      request.reference_image_urls = projectStore.referenceImageUrls
    } else {
      console.log('No reference images found in store')
    }

    await keyframeApi.generateKeyframes(request)
    
    // 开始轮询关键帧状态
    await pollKeyframesStatus(scriptId)
    return true
  } catch (error: any) {
    steps.value.keyframes.status = 'failed'
    steps.value.keyframes.message = formatErrorMessage(error?.message) || '关键帧生成失败'
    return false
  }
}

// 轮询关键帧状态
const pollKeyframesStatus = async (scriptId: number): Promise<void> => {
  return new Promise((resolve, reject) => {
    const poll = async () => {
      // 检查组件是否已卸载
      if (!isComponentMounted.value) {
        console.log('[OneClickGenerate.pollKeyframes] 组件已卸载，停止轮询')
        return
      }
      
      // 检查是否还在当前项目页面
      const currentScript = projectStore.currentScript
      if (!currentScript || currentScript.id !== scriptId) {
        console.log('[OneClickGenerate.pollKeyframes] 已切换到其他项目，停止轮询', {
          currentScriptId: currentScript?.id,
          pollingScriptId: scriptId
        })
        return
      }

      try {
        const response = await keyframeApi.getKeyframesByScript(scriptId)
        const kfs = response.keyframes || []
        keyframes.value = kfs
        projectStore.updateKeyframes(kfs)

        const total = kfs.length
        const completed = kfs.filter((k: any) => k.status?.toLowerCase() === 'completed').length
        const failed = kfs.filter((k: any) => k.status?.toLowerCase() === 'failed').length
        const generating = kfs.filter((k: any) => k.status?.toLowerCase() === 'generating').length
        const pending = kfs.filter((k: any) => k.status?.toLowerCase() === 'pending').length

        steps.value.keyframes.current = completed
        steps.value.keyframes.total = total
        steps.value.keyframes.progress = total > 0 ? Math.round((completed / total) * 100) : 0
        steps.value.keyframes.message = `已完成 ${completed}/${total} 个关键帧`

        // 只有当 generating 和 pending 都为 0 时，才算结束
        if (completed + failed === total && generating === 0 && pending === 0) {
          // 全部完成
          if (failed > 0) {
            // 有失败项，停止后续流程
            steps.value.keyframes.status = 'failed'
            const failed_messages = kfs
              .filter((k: any) => k.status?.toLowerCase() === 'failed')
              .map((k: any) => String(k.errorMessage || k.error_message || ''))
              .filter(Boolean)
            const maintenance_hit = failed_messages.some(
              (m: string) => formatErrorMessage(m) === '模型维护中'
            )
            if (maintenance_hit) {
              steps.value.keyframes.message = '模型维护中，请稍后重试'
              reject(new Error('模型维护中'))
            } else {
            steps.value.keyframes.message = `${completed} 个完成，${failed} 个失败，请重试失败项`
            reject(new Error('关键帧生成有失败项'))
            }
          } else {
            // 全部成功
            steps.value.keyframes.status = 'completed'
            steps.value.keyframes.message = '全部关键帧生成完成'
            resolve()
          }
        } else {
          // 继续轮询（再次检查是否还在当前项目）
          if (isComponentMounted.value && currentScript?.id === scriptId) {
            pollingTimer.value = setTimeout(poll, 2000)
          }
        }
      } catch (error) {
        console.error('轮询关键帧状态失败:', error)
        // 出错时也要检查是否还在当前项目
        if (isComponentMounted.value && projectStore.currentScript?.id === scriptId) {
          pollingTimer.value = setTimeout(poll, 3000)
        }
      }
    }

    poll()
  })
}

// 第三步：生成视频
const generateVideos = async () => {
  const scriptId = projectStore.currentScript?.id
  if (!scriptId) {
    steps.value.videos.status = 'failed'
    steps.value.videos.message = '脚本ID不存在'
    return false
  }

  // 检查是否有完成的关键帧
  const completedKeyframes = keyframes.value.filter(k => k.status?.toLowerCase() === 'completed')
  if (completedKeyframes.length === 0) {
    steps.value.videos.status = 'failed'
    steps.value.videos.message = '没有可用的关键帧'
    return false
  }

  // 自动切到视频预览
  auto_set_active_step('videos')

  steps.value.videos.status = 'processing'
  steps.value.videos.message = '正在生成视频...'
  steps.value.videos.progress = 0

  try {
    // 调用生成视频API
    await videoApi.generateVideos({
      scriptId,
      model: videoModel.value,
      aspectRatio: normalize_aspect_ratio(aspectRatio.value),
      duration: 4.0
    })

    // 开始轮询视频状态
    await pollVideosStatus(scriptId)
    return true
  } catch (error: any) {
    steps.value.videos.status = 'failed'
    steps.value.videos.message = formatErrorMessage(error?.message) || '视频生成失败'
    return false
  }
}

// 轮询视频状态
const pollVideosStatus = async (scriptId: number): Promise<void> => {
  return new Promise((resolve, reject) => {
    const poll = async () => {
      // 检查组件是否已卸载
      if (!isComponentMounted.value) {
        console.log('[OneClickGenerate.pollVideos] 组件已卸载，停止轮询')
        return
      }
      
      // 检查是否还在当前项目页面
      const currentScript = projectStore.currentScript
      if (!currentScript || currentScript.id !== scriptId) {
        console.log('[OneClickGenerate.pollVideos] 已切换到其他项目，停止轮询', {
          currentScriptId: currentScript?.id,
          pollingScriptId: scriptId
        })
        return
      }

      try {
        const response = await videoApi.getVideoSegmentsByScript(scriptId)
        const vids = response.videoSegments || []
        videos.value = vids
        projectStore.updateVideoSegments(vids)

        const total = vids.length
        const completed = vids.filter((v: any) => v.status?.toLowerCase() === 'completed').length
        const failed = vids.filter((v: any) => v.status?.toLowerCase() === 'failed').length
        const generating = vids.filter((v: any) => v.status?.toLowerCase() === 'generating').length

        steps.value.videos.current = completed
        steps.value.videos.total = total
        steps.value.videos.progress = total > 0 ? Math.round((completed / total) * 100) : 0
        steps.value.videos.message = `已完成 ${completed}/${total} 个视频`

        if (completed + failed === total && generating === 0) {
          if (failed > 0) {
            // 有失败项，停止后续流程
            steps.value.videos.status = 'failed'
            const failed_messages = vids
              .filter((v: any) => v.status?.toLowerCase() === 'failed')
              .map((v: any) => String(v.errorMessage || v.error_message || ''))
              .filter(Boolean)
            const maintenance_hit = failed_messages.some(
              (m: string) => formatErrorMessage(m) === '模型维护中'
            )
            if (maintenance_hit) {
              steps.value.videos.message = '模型维护中，请稍后重试'
              reject(new Error('模型维护中'))
            } else {
            steps.value.videos.message = `${completed} 个完成，${failed} 个失败，请重试失败项`
            reject(new Error('视频生成有失败项'))
            }
          } else if (completed > 0) {
            // 全部成功
            steps.value.videos.status = 'completed'
              steps.value.videos.message = '全部视频生成完成'
            resolve()
            // 视频生成完成后，自动执行导出（再次检查是否还在当前项目）
            if (isComponentMounted.value && currentScript?.id === scriptId && steps.value.export.status !== 'completed') {
              await exportVideo()
            }
          } else {
            // completed === 0，说明没有任何视频完成，可能都是pending或其他异常状态
            steps.value.videos.status = 'failed'
            steps.value.videos.message = '模型维护中，请稍后重试'
            reject(new Error('没有视频生成成功'))
          }
        } else {
          // 继续轮询（再次检查是否还在当前项目）
          if (isComponentMounted.value && currentScript?.id === scriptId) {
            pollingTimer.value = setTimeout(poll, 3000)
          }
        }
      } catch (error) {
        console.error('轮询视频状态失败:', error)
        // 出错时也要检查是否还在当前项目
        if (isComponentMounted.value && projectStore.currentScript?.id === scriptId) {
          pollingTimer.value = setTimeout(poll, 5000)
        }
      }
    }

    poll()
  })
}

// 第四步：导出合成视频
const exportVideo = async () => {
  const scriptId = projectStore.currentScript?.id
  if (!scriptId) {
    steps.value.export.status = 'failed'
    steps.value.export.message = '脚本ID不存在'
    return false
  }

  // 如果视频存在失败项（含“模型维护中”），不允许继续进入音频/导出，避免“部分失败仍继续”的误导
  const has_failed_videos = videos.value.some(
    (v: any) => v.status?.toLowerCase?.() === 'failed'
  )
  if (steps.value.videos.status !== 'completed' || has_failed_videos) {
    steps.value.audio.status = 'pending'
    steps.value.audio.message = '等待视频全部完成'
    steps.value.export.status = 'failed'
    steps.value.export.message = '视频生成存在失败项，请先重试失败项后再导出'
    return false
  }

  // 第四步前置：音频合成（未完成前不允许进入导出）
  steps.value.audio.status = 'processing'
  steps.value.audio.message = '正在合成配音...'
  steps.value.audio.progress = 0

  try {
    // 先触发/等待后端准备音频（后端会重试一次，失败返回“模型维护中”）
    await videoApi.prepareAudioForExport(scriptId)
    // 准备期间刷新音频进度（简单轮询一次即可更新 UI）
    const response = await videoApi.getVideoSegmentsByScript(scriptId)
    const vids = response.videoSegments || []
    videos.value = vids
    projectStore.updateVideoSegments(vids)
    const total = vids.length
    const completed = vids.filter((v: any) => (v.audioStatus || v.audio_status)?.toLowerCase?.() === 'completed').length
    steps.value.audio.current = completed
    steps.value.audio.total = total
    steps.value.audio.progress = total > 0 ? Math.round((completed / total) * 100) : 0
    steps.value.audio.status = 'completed'
    steps.value.audio.message = '配音已完成'
  } catch (error: any) {
    steps.value.audio.status = 'failed'
    steps.value.audio.message = formatErrorMessage(error?.message) || '模型维护中'
    return false
  }

  // 重新获取最新的视频状态，确保数据是最新的
  try {
    const response = await videoApi.getVideoSegmentsByScript(scriptId)
    const vids = response.videoSegments || []
    videos.value = vids
    projectStore.updateVideoSegments(vids)
  } catch (error) {
    console.error('获取视频状态失败:', error)
  }

  // 检查是否有完成的视频
  const completedVideos = videos.value.filter(v => v.status?.toLowerCase() === 'completed')
  if (completedVideos.length === 0) {
    steps.value.export.status = 'failed'
    steps.value.export.message = '没有可用的视频'
    return false
  }

  steps.value.export.status = 'processing'
  steps.value.export.message = '正在合成视频...'
  steps.value.export.progress = 50

  try {
    const response = await videoApi.exportVideos(scriptId, 'concatenated')
    exportUrl.value = response.downloadUrl

    steps.value.export.progress = 100
    steps.value.export.status = 'completed'
    steps.value.export.message = '视频合成完成'
    
    ElMessage.success('一键生成完成！')
    return true
  } catch (error: any) {
    steps.value.export.status = 'failed'
    steps.value.export.message = error?.message || '视频合成失败'
    return false
  }
}

const handleReExport = async () => {
  // 清空旧地址，避免用户误以为还是旧成片
  exportUrl.value = ''
  steps.value.export.status = 'pending'
  steps.value.export.message = '准备重新导出...'
  steps.value.export.progress = 0
  await exportVideo()
}

// 重试失败项
const handleRetry = async () => {
  if (isRetrying.value) return // 防止重复点击
  
  isRetrying.value = true
  
  // 确保组件挂载标志为 true，允许轮询
  isComponentMounted.value = true

  try {
    const scriptId = projectStore.currentScript?.id
    if (!scriptId) {
      throw new Error('脚本ID不存在')
    }

    const sleep = (ms: number) =>
      new Promise<void>((resolve) => setTimeout(resolve, ms))

    const sortKeyframesForRetry = (items: any[]) => {
      const getOrder = (segmentId: string): number => {
        if (String(segmentId).includes('_first_frame')) return -1
        const match = String(segmentId).match(/segment_(\d+)/)
        if (match) return Number(match[1])
        return 9999
      }
      return [...items].sort((a, b) => getOrder(a.segmentId) - getOrder(b.segmentId))
    }

    const waitForKeyframeDone = async (keyframeId: number): Promise<void> => {
      const timeoutMs = 15 * 60 * 1000
      const start = Date.now()
      while (isComponentMounted.value) {
        if (Date.now() - start > timeoutMs) {
          throw new Error(`等待关键帧完成超时: ${keyframeId}`)
        }
        const response = await keyframeApi.getKeyframesByScript(scriptId)
        const kfs = response.keyframes || []
        keyframes.value = kfs
        const target = kfs.find((k: any) => k.id === keyframeId)
        const status = target?.status?.toLowerCase?.()
        if (status === 'completed' || status === 'failed') {
          return
        }
        await sleep(2000)
      }
    }

    // 重试失败的关键帧
    const failedKeyframes = sortKeyframesForRetry(
      keyframes.value.filter(k => k.status?.toLowerCase() === 'failed')
    )

    // 立刻把“关键帧生成”步骤从 failed 拉回 processing，避免用户误以为没触发
    if (failedKeyframes.length > 0) {
      steps.value.keyframes.status = 'processing'
      steps.value.keyframes.message = '正在重试失败关键帧...'
    }

    // 立刻做一次“乐观 UI 更新”：把所有待重试的关键帧先置为 generating 并清空错误
    // 这样用户不会在接口返回前看到“用户取消生成”的红框状态，避免卡顿观感。
    if (failedKeyframes.length > 0) {
      const retryIds = new Set(failedKeyframes.map((k: any) => k.id))
      keyframes.value = keyframes.value.map((k: any) => {
        if (!retryIds.has(k.id)) return k
        return {
          ...k,
          status: 'generating',
          errorMessage: null,
          error_message: null,
        }
      })
        projectStore.updateKeyframes(keyframes.value)
      }

    for (const kf of failedKeyframes) {
      // 串行：发起重试 -> 等待该帧完成/失败 -> 再重试下一帧
      await keyframeApi.regenerateKeyframe(kf.id, imageModel.value, aspectRatio.value, quality.value)
      await waitForKeyframeDone(kf.id)
    }

    // 重试失败的视频
    const failedVideos = videos.value.filter(v => v.status?.toLowerCase() === 'failed')
    for (const vid of failedVideos) {
      try {
        await videoApi.regenerateVideoSegment(vid.id, videoModel.value)
      } catch (e) {
        console.error('重试视频失败:', e)
      }
    }

    // 重试失败的音频合成（会触发/等待后端 prepare-audio）
    if (steps.value.audio.status === 'failed' && isComponentMounted.value) {
      steps.value.audio.status = 'processing'
      steps.value.audio.message = '正在重试配音合成...'
      steps.value.audio.progress = 0
      await videoApi.prepareAudioForExport(scriptId)
      const response = await videoApi.getVideoSegmentsByScript(scriptId)
      const vids = response.videoSegments || []
      videos.value = vids
      projectStore.updateVideoSegments(vids)
      const total = vids.length
      const completed = vids.filter((v: any) => (v.audioStatus || v.audio_status)?.toLowerCase?.() === 'completed').length
      steps.value.audio.current = completed
      steps.value.audio.total = total
      steps.value.audio.progress = total > 0 ? Math.round((completed / total) * 100) : 0
      steps.value.audio.status = 'completed'
      steps.value.audio.message = '配音已完成'
    }

    // 若仅导出失败（没有关键帧/视频失败项），允许直接重试导出
    if (
      failedKeyframes.length === 0 &&
      failedVideos.length === 0 &&
      steps.value.export.status === 'failed' &&
      isComponentMounted.value
    ) {
      steps.value.export.status = 'processing'
      steps.value.export.message = '正在重新导出...'
      steps.value.export.progress = 50
      await exportVideo()
    }

    // 重新开始轮询
    if (failedKeyframes.length > 0) {
      steps.value.keyframes.status = 'processing'
      steps.value.keyframes.message = '正在重试关键帧...'
      if (scriptId && isComponentMounted.value) {
        await pollKeyframesStatus(scriptId)
        // 继续生成视频
        if (steps.value.videos.status !== 'completed' && isComponentMounted.value) {
          await generateVideos()
        }
        // 导出
        if (steps.value.export.status !== 'completed' && isComponentMounted.value) {
          await exportVideo()
        }
      }
    } else if (failedVideos.length > 0) {
      steps.value.videos.status = 'processing'
      steps.value.videos.message = '正在重试视频...'
      if (scriptId && isComponentMounted.value) {
        await pollVideosStatus(scriptId)
        // 导出
        if (steps.value.export.status !== 'completed' && isComponentMounted.value) {
          await exportVideo()
        }
      }
    }

    if (isComponentMounted.value) {
      ElMessage.success('重试完成')
    }
  } catch (error: any) {
    if (isComponentMounted.value) {
      ElMessage.error(error?.message || '重试失败')
    }
  } finally {
    isRetrying.value = false
  }
}

// 检查当前项目状态，恢复已完成的步骤
const checkExistingProgress = async () => {
  const scriptId = projectStore.currentScript?.id
  if (!scriptId) {
    return {
      scriptDone: false,
      keyframesDone: false,
      videosDone: false,
      audioDone: false,
      exportDone: false
    }
  }

  let scriptDone = false
  let keyframesDone = false
  let videosDone = false
  let audioDone = false
  
  // 获取脚本片段数量，用于校验
  const scriptSegmentsCount = projectStore.currentScript?.segments?.length || 0

  // 检查脚本
  if (projectStore.currentScript?.content) {
    scriptContent.value = projectStore.currentScript.content
    steps.value.script.status = 'completed'
    steps.value.script.message = '脚本已完成'
    steps.value.script.progress = 100
    scriptDone = true
  }

  // 检查关键帧
  try {
    const kfResponse = await keyframeApi.getKeyframesByScript(scriptId)
    const kfs = kfResponse.keyframes || []
    keyframes.value = kfs
    projectStore.updateKeyframes(kfs)

    if (kfs.length > 0) {
      const completed = kfs.filter((k: any) => k.status?.toLowerCase() === 'completed').length
      const failed = kfs.filter((k: any) => k.status?.toLowerCase() === 'failed').length
      const generating = kfs.filter((k: any) => k.status?.toLowerCase() === 'generating').length
      const pending = kfs.filter((k: any) => k.status?.toLowerCase() === 'pending').length

      // 只有当关键帧数量足够，且所有都完成时，才算完成
      // 注意：如果 scriptSegmentsCount 为 0（可能是旧数据没有segments），降级为只检查 kfs.length
      const isCountMatch = scriptSegmentsCount > 0 ? kfs.length >= scriptSegmentsCount : true
      
      if (completed === kfs.length && isCountMatch) {
        // 全部完成
        steps.value.keyframes.status = 'completed'
        steps.value.keyframes.message = '关键帧已完成'
        steps.value.keyframes.progress = 100
        steps.value.keyframes.current = completed
        steps.value.keyframes.total = kfs.length
        keyframesDone = true
      } else if (generating > 0 || pending > 0) {
        // 正在生成中（包括 pending），继续轮询
        steps.value.keyframes.status = 'processing'
        steps.value.keyframes.message = `正在生成关键帧 ${completed}/${kfs.length}`
        steps.value.keyframes.progress = Math.round((completed / kfs.length) * 100)
        steps.value.keyframes.current = completed
        steps.value.keyframes.total = kfs.length
      } else if (failed > 0 && completed + failed === kfs.length) {
        // 有失败项，标记为失败状态
          steps.value.keyframes.status = 'failed'
        steps.value.keyframes.message = `${completed} 个完成，${failed} 个失败，请重试失败项`
        steps.value.keyframes.current = completed
        steps.value.keyframes.total = kfs.length
      } else if (!isCountMatch) {
         // 数量不对，可能是部分生成，视为 processing 或 failed？
         // 如果没有任何 generating/pending，那可能是出错了，或者还在创建中
         // 这里保守起见，如果数量不够，不标记为 completed
         steps.value.keyframes.message = `关键帧数量不足 (${kfs.length}/${scriptSegmentsCount})`
         // 如果不是 processing，可能是 failed 或异常
         // 但为了能触发重新生成或轮询，这里不设为 completed
      }
    }
  } catch (error) {
    console.error('检查关键帧状态失败:', error)
  }

  // 检查视频
  try {
    const vidResponse = await videoApi.getVideoSegmentsByScript(scriptId)
    const vids = vidResponse.videoSegments || []
    videos.value = vids
    projectStore.updateVideoSegments(vids)

    if (vids.length > 0) {
      const completed = vids.filter((v: any) => v.status?.toLowerCase() === 'completed').length
      const failed = vids.filter((v: any) => v.status?.toLowerCase() === 'failed').length
      const generating = vids.filter((v: any) => v.status?.toLowerCase() === 'generating').length
      const pending = vids.filter((v: any) => v.status?.toLowerCase() === 'pending').length
      
      const isCountMatch = scriptSegmentsCount > 0 ? vids.length >= scriptSegmentsCount : true

      if (completed === vids.length && isCountMatch) {
        // 全部完成
        steps.value.videos.status = 'completed'
        steps.value.videos.message = '视频已完成'
        steps.value.videos.progress = 100
        steps.value.videos.current = completed
        steps.value.videos.total = vids.length
        videosDone = true
      } else if (generating > 0 || pending > 0) {
        // 正在生成中，继续轮询
        steps.value.videos.status = 'processing'
        steps.value.videos.message = `正在生成视频 ${completed}/${vids.length}`
        steps.value.videos.progress = Math.round((completed / vids.length) * 100)
        steps.value.videos.current = completed
        steps.value.videos.total = vids.length
      } else if (failed > 0 && completed + failed === vids.length) {
        // 有失败项，标记为失败状态
           steps.value.videos.status = 'failed'
        steps.value.videos.message = `${completed} 个完成，${failed} 个失败，请重试失败项`
         steps.value.videos.current = completed
         steps.value.videos.total = vids.length
      }

      // 恢复音频合成步骤（刷新后需要从 videoSegments.audioStatus 重新计算）
      // 只有在“视频生成完成”后，音频步骤才有意义；否则保持 pending（等待视频完成）
      if (!videosDone) {
        steps.value.audio.status = 'pending'
        steps.value.audio.message = '等待视频完成'
        steps.value.audio.progress = 0
        steps.value.audio.current = 0
        steps.value.audio.total = vids.length
      } else {
        const a_completed = vids.filter(
          (v: any) => (v.audioStatus || v.audio_status)?.toLowerCase?.() === 'completed'
        ).length
        const a_failed = vids.filter(
          (v: any) => (v.audioStatus || v.audio_status)?.toLowerCase?.() === 'failed'
        ).length
        const a_generating = vids.filter((v: any) => {
          const s = (v.audioStatus || v.audio_status)?.toLowerCase?.()
          return s === 'generating' || s === 'pending'
        }).length

        steps.value.audio.current = a_completed
        steps.value.audio.total = vids.length
        steps.value.audio.progress = vids.length > 0 ? Math.round((a_completed / vids.length) * 100) : 0

        if (a_completed === vids.length && vids.length > 0) {
          steps.value.audio.status = 'completed'
          steps.value.audio.message = '配音已完成'
          audioDone = true
        } else if (a_generating > 0) {
          steps.value.audio.status = 'processing'
          steps.value.audio.message = `正在合成配音 ${a_completed}/${vids.length}`
        } else if (a_failed > 0) {
          steps.value.audio.status = 'failed'
          steps.value.audio.message = '模型维护中'
        } else {
          // 没有明确状态（例如空数据），保守处理
          steps.value.audio.status = 'processing'
          steps.value.audio.message = `正在合成配音 ${a_completed}/${vids.length}`
        }
      }
    }
  } catch (error) {
    console.error('检查视频状态失败:', error)
  }

  // 检查导出状态
  let exportDone = false
  if (videosDone && scriptId) {
    // 如果视频全部完成，从 API 获取最新的脚本信息，检查是否已有导出记录
    try {
      const scriptResponse = await scriptApi.getScript(scriptId)
      const script = scriptResponse as any
      
      if (script.exportedVideoUrl) {
        steps.value.export.status = 'completed'
        steps.value.export.message = '视频已导出'
        steps.value.export.progress = 100
        exportUrl.value = script.exportedVideoUrl
        exportDone = true

        // 兜底：后端已强制“导出前音频就绪”，所以导出成功即视为音频完成
        steps.value.audio.status = 'completed'
        steps.value.audio.message = '配音已完成'
        steps.value.audio.progress = 100
        audioDone = true
      }
    } catch (error) {
      console.error('检查导出状态失败:', error)
      // 如果 API 调用失败，回退到检查本地 exportUrl
      if (exportUrl.value) {
        steps.value.export.status = 'completed'
        steps.value.export.message = '视频已导出'
        steps.value.export.progress = 100
        exportDone = true

        // 同上兜底
        steps.value.audio.status = 'completed'
        steps.value.audio.message = '配音已完成'
        steps.value.audio.progress = 100
        audioDone = true
      }
    }
  }

  return { scriptDone, keyframesDone, videosDone, audioDone, exportDone }
}

// 主流程
const startGeneration = async () => {
  // 加载模型配置
  await loadModels()

  // 设置项目名称
  projectName.value = projectStore.currentProject?.name || inspiration.value?.slice(0, 20) || '一键生成项目'

  // 检查已有进度
  const { scriptDone, keyframesDone, videosDone, exportDone } = await checkExistingProgress()

  // 步骤1: 生成脚本（如果未完成）
  if (!scriptDone) {
    const scriptOk = await generateScript()
    if (!scriptOk) return
  }

  // 步骤2: 生成关键帧（如果未完成）
  if (!keyframesDone) {
    // 如果正在生成中，继续轮询
    if (steps.value.keyframes.status === 'processing') {
      const scriptId = projectStore.currentScript?.id
      if (scriptId) {
        auto_set_active_step('keyframes')
        await pollKeyframesStatus(scriptId)
      }
    } else if (steps.value.keyframes.status === 'failed') {
      // 失败状态，不自动重新生成，需要用户点击重试
      auto_set_active_step('keyframes')
      return
    } else if (keyframes.value.length > 0) {
      // 已经有关键帧记录但未完成
      // 检查是否有正在生成或 pending 的关键帧
      const generating = keyframes.value.filter(k => 
        k.status?.toLowerCase() === 'generating' || 
        k.status?.toLowerCase() === 'pending'
      ).length
      
      if (generating > 0) {
        // 有正在生成的，继续轮询等待完成
        const scriptId = projectStore.currentScript?.id
        if (scriptId) {
          auto_set_active_step('keyframes')
          steps.value.keyframes.status = 'processing'
          await pollKeyframesStatus(scriptId)
        }
      } else {
        // 没有正在生成的，可能都是 failed 状态，或者数量不足
        // 检查数量是否足够，如果不足也视为异常
        const scriptSegmentsCount = projectStore.currentScript?.segments?.length || 0
        const isCountMatch = scriptSegmentsCount > 0 ? keyframes.value.length >= scriptSegmentsCount : true
        
        if (!isCountMatch) {
             // 数量不足，且没有 generating/pending，视为异常，不自动开始下一步
             console.warn('关键帧数量不足且没有正在生成的任务', { current: keyframes.value.length, expected: scriptSegmentsCount })
             auto_set_active_step('keyframes')
             return
        }

        // 如果全部是 failed，或者其他非 processing 状态
        auto_set_active_step('keyframes')
        return
      }
    } else {
      // 没有关键帧记录，开始生成
      console.log('开始生成关键帧', { referenceImages: projectStore.referenceImageUrls })
      // 立即设置状态为 processing，确保终止按钮显示
      steps.value.keyframes.status = 'processing'
      steps.value.keyframes.message = '正在生成关键帧...'
      
      // 等待 Vue 更新 DOM，确保终止按钮显示
      await nextTick()
      
      const keyframesOk = await generateKeyframes()
      if (!keyframesOk) return
    }
  } else {
    // 关键帧已完成，切换到关键帧预览
    auto_set_active_step('keyframes')
  }

  // 安全检查：进入视频生成前，再次确认关键帧状态
  // 必须全部完成才能继续
  const scriptSegmentsCount = projectStore.currentScript?.segments?.length || 0
  const currentKeyframes = keyframes.value
  const completedKfCount = currentKeyframes.filter(k => k.status?.toLowerCase() === 'completed').length
  const isKfCountMatch = scriptSegmentsCount > 0 ? currentKeyframes.length >= scriptSegmentsCount : currentKeyframes.length > 0
  
  // 如果关键帧没有全部完成，停止流转
  if (completedKfCount < currentKeyframes.length || !isKfCountMatch || completedKfCount === 0) {
    if (!videosDone) {
      console.log('关键帧未全部完成，停止自动流转到视频生成', { 
        completed: completedKfCount, 
        total: currentKeyframes.length,
        expected: scriptSegmentsCount
      })
      // 如果状态不是 processing，且未完成，确保页面停留在关键帧 tab
      if (steps.value.keyframes.status !== 'processing' && steps.value.keyframes.status !== 'completed') {
         auto_set_active_step('keyframes')
      }
      return
    }
  }

  // 步骤3: 生成视频（如果未完成）
  if (!videosDone) {
    // 如果正在生成中，继续轮询
    if (steps.value.videos.status === 'processing') {
      const scriptId = projectStore.currentScript?.id
      if (scriptId) {
        auto_set_active_step('videos')
        await pollVideosStatus(scriptId)
      }
    } else if (steps.value.videos.status === 'failed') {
      // 失败状态，不自动重新生成，需要用户点击重试
      auto_set_active_step('videos')
      return
    } else if (videos.value.length > 0) {
      // 已经有视频记录但未完成
      // 检查是否有正在生成的视频
      const generating = videos.value.filter(v => v.status?.toLowerCase() === 'generating').length
      if (generating > 0) {
        // 有正在生成的，继续轮询等待完成
        const scriptId = projectStore.currentScript?.id
        if (scriptId) {
          auto_set_active_step('videos')
          steps.value.videos.status = 'processing'
          await pollVideosStatus(scriptId)
        }
      } else {
        // 没有正在生成的，可能都是pending或failed状态，不自动重新生成
        auto_set_active_step('videos')
        return
      }
    } else {
      // 没有视频记录，开始生成
      const videosOk = await generateVideos()
      if (!videosOk) return
    }
  } else {
    // 视频已完成，切换到视频预览
    auto_set_active_step('videos')
  }

  // 步骤4: 导出视频（仅在视频全部完成且未导出时执行）
  if (videosDone && !exportDone) {
    await exportVideo()
  }
  // 如果已导出，保持在视频预览页面
}

// 初始化项目数据的函数
const initializeProject = async () => {
  console.log('[OneClickGenerate.initializeProject] 开始初始化项目', {
    projectId: projectId.value,
    autoStart: route.query.autoStart
  })
  
  // 检查是否是从首页一键生成跳转过来的（带有 autoStart 参数）
  const autoStart = route.query.autoStart === 'true'
  // 仅在明确携带 autoContinue 时，才允许“自动继续生成流程”
  // 这样打开老项目只会加载/展示，不会重新触发生成。
  const autoContinue = route.query.autoContinue === 'true'
  
  if (autoStart) {
    // 从首页跳转过来，需要先创建项目和脚本
    try {
      const requestData: any = {
        inspiration: route.query.inspiration as string,
        style: route.query.style as string,
        totalDuration: parseInt(route.query.totalDuration as string) || 20,
        segmentDuration: parseInt(route.query.segmentDuration as string) || 4,
        generationMode: 'one_click',
        enableSearch: route.query.enableSearch === 'true'
      }

      // 不再将 custom_style_1767597711851 与即梦强绑定；
      // 图片模型选择由 loadModels() 根据风格策略决定（该风格优先 Seedream，后端按链路降级到即梦）。
      
      // 添加参考图URLs（如果有）
      if (projectStore.referenceImageUrls.length > 0) {
        requestData.referenceImageUrls = projectStore.referenceImageUrls
        console.log('一键生成：使用参考图', projectStore.referenceImageUrls)
      } else {
        console.log('一键生成：没有参考图')
      }
      // inspiration 为 computed（来自 route.query），无需在此手动赋值
      
      // 显示脚本生成进度
      steps.value.script.status = 'processing'
      steps.value.script.message = '正在生成脚本...'
      steps.value.script.progress = 50
      
      // 生成脚本
      const script = await scriptApi.generateScript(requestData, route.query.model as string)
      
      if (script?.projectId) {
        // 获取完整项目信息
        const project = await projectApi.getProject(script.projectId)
        const projectWithScript = project as any
        if (projectWithScript.scripts && Array.isArray(projectWithScript.scripts) && projectWithScript.scripts.length > 0) {
          projectWithScript.script = projectWithScript.scripts[0]
        } else if (!projectWithScript.script && script) {
          projectWithScript.script = script
        }
        
        projectStore.setCurrentProject(projectWithScript)
        projectStore.addProject(projectWithScript)

        // 同步创意页选择的比例到项目（用于后续关键帧/视频生成与预览）
        try {
          const desired_ratio =
            query_aspect_ratio.value ||
            normalize_aspect_ratio(String((projectWithScript as any)?.aspectRatio || ''))
          projectStore.updateCurrentProject({
            aspectRatio: desired_ratio,
          } as any)
          aspectRatio.value = desired_ratio
          await persist_project_aspect_ratio_if_needed(projectWithScript, desired_ratio)
        } catch (e) {
          console.warn('同步项目比例失败:', e)
        }
        
        // 更新路由，移除 query 参数，添加 projectId
        await router.replace({
          name: 'OneClickGenerate',
          params: { projectId: script.projectId.toString() },
          // 保留比例选择，避免后续重新加载项目把比例回退为默认 16:9
          // 同时带上 autoContinue：让后续的 initializeProject 能自动进入 startGeneration 流程
          query: {
            aspectRatio: query_aspect_ratio.value || requested_aspect_ratio.value,
            autoContinue: 'true',
          }
        })
        
        // 路由变化会触发 watch，watch 会重新初始化项目
        // 所以这里直接返回，停止当前流程，避免竞态条件
        return
        
        /* 
        // 以下代码已由 watch 触发的重新初始化接管，无需执行
        // 脚本生成完成
        steps.value.script.status = 'completed'
        steps.value.script.message = '脚本生成完成'
        steps.value.script.progress = 100
        
        // 等待 Vue 更新 DOM
        await nextTick()
        
        // 继续生成流程（使用 await 确保状态更新）
        await startGeneration()
        */
      }
    } catch (error: any) {
      console.error('创建项目失败:', error)
      steps.value.script.status = 'failed'
      steps.value.script.message = error?.message || '脚本生成失败'
      ElMessage.error('创建项目失败，请返回重试')
    }
  } else if (projectId.value) {
    // 正常打开已有项目
    console.log('[OneClickGenerate.initializeProject] 加载项目', {
      currentProjectId: projectStore.currentProject?.id,
      targetProjectId: projectId.value
    })
    
    // 总是重新加载项目数据，确保数据是最新的
    try {
      const project = await projectApi.getProject(projectId.value)
      // 兼容后端返回 scripts[] 而非 script 的情况，避免 currentScript 为空导致误触发“重新生成脚本/视频”
      const projectWithScript = project as any
      if (
        projectWithScript.scripts &&
        Array.isArray(projectWithScript.scripts) &&
        projectWithScript.scripts.length > 0
      ) {
        projectWithScript.script = projectWithScript.scripts[0]
      }
      projectStore.setCurrentProject(projectWithScript)
      // 优先使用项目持久化的比例；如果项目没存比例，不要立刻回退 16:9 覆盖掉用户原选择
      if (has_persisted_project_aspect_ratio(project)) {
        aspectRatio.value = normalize_aspect_ratio(String((project as any)?.aspectRatio || ''))
      }

      // 仅当 URL 明确带了 aspectRatio 时，才允许覆盖项目比例（避免无 query 时误写回 16:9）
      if (query_aspect_ratio.value) {
        try {
          projectStore.updateCurrentProject({
            aspectRatio: query_aspect_ratio.value,
          } as any)
          aspectRatio.value = query_aspect_ratio.value
          await persist_project_aspect_ratio_if_needed(project, query_aspect_ratio.value)
        } catch (e) {
          console.warn('同步项目比例失败:', e)
        }
      } else if (!has_persisted_project_aspect_ratio(project)) {
        // 兜底：项目没存比例时，尝试用已生成的关键帧图片尺寸推断（修复切换项目后变 16:9）
        try {
          const sid = Number((project as any)?.script?.id || 0)
          if (sid) {
            const resp: any = await keyframeApi.getKeyframesByScript(sid)
            const completed = (resp?.keyframes || []).filter((k: any) => {
              const s = String(k?.status || '').toLowerCase()
              return s === 'completed' && (k.imageUrl || k.image_url)
            })
            const first_img = completed?.[0]?.imageUrl || completed?.[0]?.image_url
            if (first_img) {
              const inferred = await infer_aspect_ratio_from_image_url(first_img)
              if (inferred) {
                aspectRatio.value = inferred
                projectStore.updateCurrentProject({ aspectRatio: inferred } as any)
                await persist_project_aspect_ratio_if_needed(project, inferred)
              }
            }
          }
        } catch (e) {
          console.warn('推断并持久化项目比例失败:', e)
        }
      }
      console.log('[OneClickGenerate.initializeProject] 项目加载成功', {
        projectId: project.id,
        projectName: project.name
      })
    } catch (e) {
      console.error('加载项目失败:', e)
      ElMessage.error('加载项目失败')
      return
    }

    // 先加载/展示已有进度
    const progress = await checkExistingProgress()

    // 若仅剩“导出合成”未完成：自动继续到导出（不会重新生成关键帧/视频）
    if (progress.videosDone && !progress.exportDone) {
      if (!auto_export_triggered.value) {
        auto_export_triggered.value = true
        await exportVideo()
      }
      return
    }

    // 默认不自动继续生成，避免打开老项目时误触发重新生成；
    // 只有在 URL 明确携带 autoContinue=true 时，才自动继续生成/轮询流程。
    if (autoContinue) {
    await startGeneration()
    }
  }
}

// 监听路由参数变化
watch(() => route.params.projectId, (newProjectId, oldProjectId) => {
  console.log('[OneClickGenerate.watch] 路由参数变化', {
    from: oldProjectId,
    to: newProjectId
  })
  
  if (newProjectId && newProjectId !== oldProjectId) {
    console.log('[OneClickGenerate.watch] 清理旧项目的轮询定时器')
    
    // 清理之前的轮询定时器
    if (pollingTimer.value) {
      clearTimeout(pollingTimer.value)
      pollingTimer.value = null
    }
    
    // 重置生成状态，避免显示旧项目的进度
    steps.value.script.status = 'pending'
    steps.value.keyframes.status = 'pending'
    steps.value.videos.status = 'pending'
    steps.value.export.status = 'pending'
    auto_export_triggered.value = false
    
    // 重新初始化项目
    initializeProject()
  }
})

// 生命周期
onMounted(async () => {
  await initializeProject()
})

onUnmounted(() => {
  isComponentMounted.value = false // 标记组件已卸载，停止后续轮询
  if (pollingTimer.value) {
    clearTimeout(pollingTimer.value)
    pollingTimer.value = null
  }
})
</script>

<style scoped>
.one-click-generate {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f3f4f6;
  color: #333;
  overflow: hidden;
}

/* 二级头（Figma 20:4976） */
.oc-topbar {
  height: 69px;
  flex: 0 0 69px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: #ffffff;
  border-bottom: 1px solid #e5e7eb;
  box-sizing: border-box;
}

.oc-topbar-left {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.oc-back-btn {
  color: #6a7282;
}

.oc-topbar-divider {
  width: 1px;
  height: 20px;
  background: #d1d5dc;
}

.oc-title {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  line-height: 28px;
  color: #1e2939;
}

.oc-topbar-right {
  display: inline-flex;
  align-items: center;
  gap: 12px;
}

.oc-btn {
  height: 36px;
  border-radius: 8px;
}

.oc-btn-ghost {
  border: 1px solid #d1d5dc;
  background: #ffffff;
  color: #0a0a0a;
}

.oc-btn-primary {
  border: none;
  background: linear-gradient(180deg, #2b7fff 0%, #00b8db 100%);
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1),
    0 2px 4px -2px rgba(0, 0, 0, 0.1);
}

.oc-btn-danger {
  border: none;
}

.clickable-media {
  cursor: zoom-in;
}

.video-header-actions {
  display: flex;
  gap: 8px;
}

.final-video-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.preview-video-frame {
  width: 100%;
  display: flex;
  justify-content: center;
}

.preview-video-player {
  width: 100%;
  max-height: 70vh;
  background: #000;
  border-radius: 12px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.back-btn {
  color: #606266;
  font-size: 14px;
}

.title {
  font-size: 20px;
  font-weight: 600;
  margin: 0;
  color: #00aaaa;
}

.header-right {
  display: flex;
  align-items: center;
}

.project-name {
  font-size: 14px;
  color: #909399;
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: row;
  gap: 0;
  padding: 0;
  overflow: hidden;
  min-height: 0;
}

.main-content.oc-layout {
  background: #f3f4f6;
}

/* 进度面板 */
.progress-panel {
  width: 320px;
  flex-shrink: 0;
  background: #fff;
  border-radius: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  box-shadow: none;
  border: none;
  border-right: 1px solid #e5e7eb;
  height: 100%;
  overflow: auto;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0;
  padding: 24px 24px 12px;
}

.progress-title {
  display: flex;
  align-items: center;
  gap: 16px;
}

.progress-header h2 {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
  color: #303133;
}

.progress-header h2 {
  font-size: 14px;
  font-weight: 700;
  color: #1e2939;
  line-height: 20px;
}

.total-progress {
  font-size: 24px;
  font-weight: 800;
  color: #2b7fff;
  line-height: 32px;
}

.progress-panel :deep(.el-progress-bar__outer) {
  height: 8px !important;
  background: rgba(3, 2, 19, 0.2);
}

.progress-panel :deep(.el-progress-bar__inner) {
  background: #030213;
}

.oc-overall-progress {
  margin: 0 24px 24px;
  height: 8px;
  border-radius: 999px;
  background: rgba(3, 2, 19, 0.2);
  overflow: hidden;
}

.oc-overall-progress-inner {
  height: 100%;
  background: #030213;
}

.total-progress {
  font-size: 24px;
  font-weight: 700;
  color: #2b7fff;
}

.progress-steps {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 12px 24px 24px;
  box-sizing: border-box;
}

.step {
  display: flex;
  gap: 16px;
  padding: 18px;
  background: #ffffff;
  border-radius: 10px;
  border: 2px solid #e5e7eb;
  transition: all 0.3s ease;
  min-height: 76px;
  box-sizing: border-box;
  cursor: pointer;
  user-select: none;
}

.step:focus-visible {
  outline: 3px solid rgba(43, 127, 255, 0.25);
  outline-offset: 2px;
}

.step.active {
  border-color: rgba(43, 127, 255, 0.65);
  box-shadow: 0 0 0 3px rgba(43, 127, 255, 0.12);
}

.step:hover {
  border-color: rgba(43, 127, 255, 0.35);
}

.step.processing {
  background: #eff6ff;
  border-color: #2b7fff;
}

.step.completed {
  background: #f0fdf4;
  border-color: #b9f8cf;
}

.step.failed {
  background: #fff2f0;
  border-color: #ffccc7;
}

.step-icon {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  flex-shrink: 0;
  border: 2px solid #d1d5dc;
  box-sizing: border-box;
}

.step-icon .success {
  color: #16a34a;
  font-size: 14px;
}

.step-icon .error {
  color: #ff4d4f;
  font-size: 14px;
}

.step-icon .maintenance {
  color: #e6a23c;
  font-size: 14px;
}

.step-icon .cancelled {
  color: #6a7282;
  font-size: 14px;
}

.step-icon .processing {
  color: #2b7fff;
  font-size: 14px;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.step-number {
  font-size: 12px;
  font-weight: 500;
  color: #6a7282;
}

.step-content {
  flex: 1;
  min-width: 0;
}

.step-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 4px;
  color: #1e2939;
}

.step-desc {
  font-size: 12px;
  color: #6a7282;
  margin-bottom: 8px;
}

.step-detail {
  font-size: 12px;
  color: #2b7fff;
  margin-bottom: 8px;
  font-weight: 500;
}

.step :deep(.el-progress__bar) {
  background: #e4e7ed;
}

.step :deep(.el-progress-bar__inner) {
  background: linear-gradient(90deg, #00aaaa, #52c41a);
}

.action-buttons {
  margin-top: 24px;
  display: flex;
  gap: 12px;
}

.action-buttons .el-button {
  flex: 1;
}

/* 预览面板 */
.preview-panel {
  flex: 1;
  min-width: 0;
  background: #f3f4f6;
  border-radius: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: none;
  border: none;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0;
  flex-shrink: 0;
  height: 53px;
  padding: 0 24px;
  background: #ffffff;
  border-bottom: 1px solid #e5e7eb;
}

.preview-header h2 {
  font-size: 14px;
  font-weight: 700;
  margin: 0;
  color: #1e2939;
}

.preview-content {
  flex: 1;
  overflow: auto;
  min-height: 0;
  padding: 24px;
}

/* 脚本预览 */
.script-preview {
  height: 100%;
}

.script-text {
  white-space: pre-wrap;
  font-size: 14px;
  line-height: 1.8;
  color: #333;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
  max-height: 100%;
  overflow: auto;
  border: 1px solid #e4e7ed;
}

/* 关键帧预览 */
.preview-actions {
  margin-bottom: 16px;
  display: flex;
  justify-content: flex-end;
}

.keyframes-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 20px;
  padding-bottom: 16px;
}

.keyframe-item {
  position: relative;
  aspect-ratio: auto;
  border-radius: 10px;
  overflow: hidden;
  background: #f3f4f6;
  border: 1px solid #e5e7eb;
}

.keyframe-item.generating {
  border-color: #2b7fff;
}

.keyframe-item.failed {
  border-color: #ef4444;
}

.keyframe-index {
  position: absolute;
  left: 8px;
  bottom: 8px;
  background: linear-gradient(180deg, #2b7fff 0%, #00b8db 100%);
  color: #ffffff;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
  z-index: 1;
  white-space: nowrap;
}

.keyframe-image-container {
  position: relative;
  width: 100%;
  height: 100%;
}

.keyframe-image-container img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.keyframe-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.3s;
}

.keyframe-image-container:hover .keyframe-overlay {
  opacity: 1;
}

.keyframe-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.keyframe-loading,
.keyframe-failed,
.keyframe-pending {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 6px;
  font-size: 12px;
  color: #6a7282;
}

.keyframe-loading .el-icon {
  font-size: 24px;
  color: #2b7fff;
}

.keyframe-failed .failed-icon,
.video-failed .failed-icon {
  font-size: 18px;
  line-height: 20px;
}

.keyframe-failed .failed-text,
.video-failed .failed-text {
  font-size: 12px;
  font-weight: 700;
  color: #ef4444;
  line-height: 16px;
}

.keyframe-failed .failed-sub,
.video-failed .failed-sub {
  font-size: 11px;
  color: #9ca3af;
  line-height: 16px;
}

.keyframe-failed .cancel-icon,
.video-failed .cancel-icon {
  font-size: 22px;
  line-height: 22px;
  color: rgba(43, 127, 255, 0.65);
}

.keyframe-failed .cancel-text,
.video-failed .cancel-text {
  font-size: 12px;
  font-weight: 700;
  color: #6a7282;
  line-height: 16px;
}

.keyframe-failed .cancel-sub,
.video-failed .cancel-sub {
  font-size: 11px;
  color: #9ca3af;
  line-height: 16px;
}

/* 音频预览（主题一致 + 精致） */
.audio-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.audio-card {
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  overflow: hidden;
}

.audio-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 12px 10px;
  border-bottom: 1px solid #f3f4f6;
}

.audio-tag {
  height: 23px;
  padding: 4px 10px;
  border-radius: 999px;
  background: linear-gradient(180deg, #2b7fff 0%, #00b8db 100%);
  color: #ffffff;
  font-size: 12px;
  font-weight: 500;
  line-height: 16px;
}

.audio-status {
  font-size: 12px;
  color: #6a7282;
}

.audio-card-body {
  padding: 12px;
}

.audio-player audio {
  width: 100%;
}

.audio-empty {
  font-size: 12px;
  color: #6a7282;
  padding: 10px 0;
}

.audio-error {
  margin-top: 8px;
  font-size: 11px;
  color: #ef4444;
  line-height: 16px;
}

@media (max-width: 900px) {
  .audio-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 1200px) {
  .keyframes-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .keyframes-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

/* 视频预览 */
.videos-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 20px;
  padding-bottom: 16px;
}

.video-item {
  position: relative;
  aspect-ratio: auto;
  border-radius: 10px;
  overflow: hidden;
  background: #f3f4f6;
  border: 1px solid #e5e7eb;
}

.video-item.generating {
  border-color: #2b7fff;
}

.video-item.failed {
  border-color: #ef4444;
}

.video-header {
  position: absolute;
  top: 8px;
  left: 8px;
  right: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  z-index: 1;
}

.video-index {
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.download-btn {
  background: rgba(0, 0, 0, 0.6);
  border: none;
  color: #fff;
}

.download-btn:hover {
  background: rgba(0, 0, 0, 0.8);
}

.video-item video {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.video-loading,
.video-failed,
.video-pending {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 6px;
  font-size: 12px;
  color: #6a7282;
}

.video-loading .el-icon {
  font-size: 32px;
  color: #2b7fff;
}

@media (max-width: 1200px) {
  .videos-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .videos-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

.retry-hint {
  font-size: 11px;
  color: #faad14;
  margin-top: 4px;
}

/* 空状态 */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 300px;
  color: #909399;
  gap: 16px;
}

.empty-state p {
  margin: 0;
  font-size: 14px;
}

/* 最终视频 */
.final-video {
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid #e4e7ed;
  flex-shrink: 0;
}

.final-video h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 16px 0;
  color: #52c41a;
}

.final-video-player {
  width: 100%;
  max-height: 400px;
  border-radius: 8px;
  background: #000;
}
</style>

