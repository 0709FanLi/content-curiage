<template>
  <div class="video-list-container">
    <!-- 合成中（Figma 19:3710） -->
    <template v-if="compose_state === 'composing'">
      <div class="compose-header">
        <div class="compose-title">视频合成中...</div>
      </div>
      <div class="compose-body">
        <div class="compose-card">
          <div class="compose-card-inner">
            <div class="compose-hero">
              <div class="compose-icon" />
              <div class="compose-hero-title">
                正在合成您的视频
              </div>
              <div class="compose-hero-sub">
                请稍候，我们正在将所有片段合成为完整视频...
              </div>
            </div>

            <div class="compose-progress">
              <div class="compose-progress-track">
                <div
                  class="compose-progress-fill"
                  :style="{ width: `${Math.min(100, Math.max(0, Math.round(concatenatingProgress)))}%` }"
                 
                />
              </div>
              <div class="compose-progress-meta">
                <div class="compose-progress-label">
                  合成进度
                </div>
                <div class="compose-progress-value">
                  {{ Math.min(100, Math.max(0, Math.round(concatenatingProgress))) }}%
                </div>
              </div>
            </div>

            <div class="compose-stats">
              <div class="compose-stat">
                <div class="compose-stat-label">
                  视频片段
                </div>
                <div class="compose-stat-value">
                  {{ videoSegments.length }} 个
                </div>
              </div>
              <div class="compose-stat">
                <div class="compose-stat-label">
                  输出格式
                </div>
                <div class="compose-stat-value">MP4</div>
              </div>
              <div class="compose-stat">
                <div class="compose-stat-label">
                  预计时间
                </div>
                <div class="compose-stat-value">
                  1-5 分钟
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- 合成完成：预览 + 下载 + 返回片段页 -->
    <template v-else-if="compose_state === 'done'">
      <!-- 二级头（右侧内容区顶部栏），按 Figma 19:3982 -->
      <div class="vf-done-header">
        <div class="vf-done-title">
          <span class="vf-done-title-text">视频合成完成</span>
          <img src="@/assets/icons/check.png" class="vf-done-title-dot" />
        </div>
        <div class="vf-done-actions">
        <el-button
          type="default"
            class="vf-done-back"
            @click="back_to_segments"
          >
            <el-icon><Back /></el-icon>
            返回视频片段
          </el-button>
          <el-button
            type="primary"
            class="vf-done-download"
            :disabled="!composed_download_url"
            @click="download_composed_video"
          >
            <el-icon><Download /></el-icon>
            下载视频
          </el-button>
        </div>
      </div>

      <div class="vf-done-content">
        <div class="vf-preview-card">
          <div class="vf-preview-head">
            <div class="vf-preview-title">合成视频预览</div>
            <div class="vf-preview-sub">视频已成功合成，您可以下载此视频</div>
          </div>

          <div class="vf-preview-player">
            <video
              v-if="composed_download_url"
              :src="composed_download_url"
              class="vf-preview-video"
              controls
              preload="metadata"
              playsinline
            />
          </div>

          <div class="vf-preview-meta">
            <div class="vf-meta-item">
              <div class="vf-meta-label">总片段数</div>
              <div class="vf-meta-value">{{ videoSegments.length }} 个</div>
            </div>
            <div class="vf-meta-item">
              <div class="vf-meta-label">视频格式</div>
              <div class="vf-meta-value">MP4 (H.264)</div>
            </div>
            <div class="vf-meta-item">
              <div class="vf-meta-label">分辨率</div>
              <div class="vf-meta-value">{{ project_resolution_hint }}</div>
            </div>
            <div class="vf-meta-item">
              <div class="vf-meta-label">文件大小</div>
              <div class="vf-meta-value">约 — MB</div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- 视频片段页（Figma 19:3270） -->
    <template v-else>
      <div class="vf-page-header">
        <div class="vf-page-title">视频生成结果</div>
        <div class="vf-page-actions">
          <el-button
            type="default"
            class="vf-btn vf-btn-ghost"
            @click="go_to_keyframes"
           
          >
            <el-icon><Back /></el-icon>
          返回关键帧
        </el-button>
          <el-button
            type="default"
            class="vf-btn vf-btn-ghost"
            :disabled="!allVideosCompleted"
            :loading="exporting"
            @click="handleExportVideos('separate')"
           
          >
                <el-icon><FolderOpened /></el-icon>
            确认片段，单独导出（*ZIP）
          </el-button>
          <el-button
            type="primary"
            class="vf-btn vf-btn-primary"
            :disabled="has_existing_composed_video ? !existing_composed_url : !allVideosCompleted"
            :loading="exporting"
            @click="has_existing_composed_video ? view_composed_video() : start_compose()"
           
          >
                <el-icon><VideoPlay /></el-icon>
            {{ has_existing_composed_video ? '查看视频' : '确认片段，合成视频' }}
          </el-button>
      </div>
    </div>

    <div class="videos-content">
      <div class="video-grid">
        <div
          v-for="video in sortedVideos"
          :key="video.id"
          class="video-card"
           
        >
            <div class="card-video-area">
              <div
                v-if="video.videoUrl && video.status === 'completed'"
                class="video-player-container"
               
              >
                <video
                  :src="video.videoUrl"
                  class="video-player"
                  preload="metadata"
                  muted
                  playsinline
                />

                <!-- 播放按钮：点击打开预览并播放 -->
                <div class="vid-play-overlay">
                  <el-button
                    class="vid-play-btn"
                    circle
                    size="small"
                    title="播放"
                    @click.stop="open_video_preview(video)"
                  >
                    <el-icon><VideoPlay /></el-icon>
                  </el-button>
                </div>

                <div class="vid-actions">
                  <el-button
                    class="vid-action-btn"
                    size="small"
                    circle
                @click="open_video_preview(video)"
                    title="预览"
              >
                    <el-icon><ZoomIn /></el-icon>
                  </el-button>
                  <el-button
                    class="vid-action-btn"
                    size="small"
                    circle
                @click="handleDownloadVideo(video)"
                    title="下载"
              >
                    <el-icon><Download /></el-icon>
                  </el-button>
                  <el-button
                    class="vid-action-btn"
                    size="small"
                    circle
                    @click="handleEditVideoUrl(video)"
                    title="上传视频链接"
                  >
                    <el-icon><Link /></el-icon>
                  </el-button>
                  <el-button
                    class="vid-action-btn"
                    size="small"
                    circle
                @click="handleEditVideoDescription(video)"
                    title="编辑并重新生成"
              >
                    <el-icon><Edit /></el-icon>
                  </el-button>
                  <el-button
                    class="vid-action-btn"
                    size="small"
                    circle
                @click="handleRefreshVideo(video.id)"
                title="重新生成"
              >
                    <el-icon><Refresh /></el-icon>
                  </el-button>
          </div>

                <div class="vid-tag">
                  {{ getVideoSegmentTitle(video) }}
                </div>
            </div>
            
            <div v-else-if="video.status === 'generating'" class="video-placeholder generating">
              <div class="loading-animation">
                <div class="loading-bar"></div>
              </div>
              <div class="loading-text">
                <span class="loading-icon">🎬</span>
                <span>视频生成中...</span>
              </div>
              <!-- 不再显示重试状态和中断按钮 -->
              <div class="loading-tip">预计 1-5 分钟</div>
            </div>
            
            <div v-else-if="video.status === 'pending'" class="video-placeholder pending">
              <div class="pending-animation">
                <div class="pulse-circle"></div>
              </div>
              <div class="pending-text">
                <span class="pending-icon">⏱️</span>
                <span>等待生成...</span>
              </div>
            </div>

            <div v-else-if="video.status === 'failed'" class="video-placeholder failed">
              <div class="failed-icon">🔧</div>
              <div class="failed-text">模型维护中</div>
              <div class="error-detail">请稍后重试</div>
              <el-button class="retry-btn" size="small" type="primary" @click="handleRefreshVideo(video.id)">
                重新生成
              </el-button>
            </div>

            <div v-else class="video-placeholder">
              <div class="placeholder-icon">🎬</div>
              <div class="placeholder-text">视频未生成</div>
            </div>
          </div>

          <div class="card-description">
            <p :title="video.prompt">{{ video.prompt }}</p>
          </div>
        </div>
      </div>
    </div>
    </template>

    <!-- 编辑视频描述弹窗 -->
    <el-dialog
      v-model="editVideoDescriptionDialogVisible"
      title="编辑视频描述"
      width="600px"
      :before-close="handleCancelEditVideoDescription"
    >
      <div class="edit-description-content">
        <el-input
          v-model="editingVideoDescription"
          type="textarea"
          :rows="8"
          placeholder="请输入视频描述..."
          maxlength="1000"
          show-word-limit
        />
      </div>
      <template #footer>
        <div class="dialog-footer">
          <el-select
            v-model="editingVideoModel"
            placeholder="选择生成模型"
            class="model-select"
            style="width: 200px; margin-right: auto;"
          >
            <el-option
              v-for="model in videoModels"
              :key="model.id"
              :label="model.name"
              :value="model.id"
            />
          </el-select>
          <el-button @click="handleCancelEditVideoDescription">取消</el-button>
          <el-button 
            type="primary" 
            @click="handleConfirmEditVideoDescription"
            :disabled="!editingVideoDescription.trim() || !editingVideoModel"
            :loading="regeneratingVideoFromEdit"
          >
            确定并重新生成视频
          </el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 修改视频链接弹窗 -->
    <el-dialog
      v-model="editVideoUrlDialogVisible"
      title="上传视频链接"
      width="600px"
      :before-close="handleCancelEditVideoUrl"
    >
      <div class="edit-description-content">
        <el-input
          v-model="editingVideoUrl"
          placeholder="请输入可访问的 MP4 链接（http/https），将替换当前视频链接"
          maxlength="500"
          show-word-limit
        />
        <div class="edit-url-tip">
          修改后将立即用于预览与下载，不会触发重新生成。
        </div>
        </div>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="handleCancelEditVideoUrl">取消</el-button>
          <el-button type="primary" :loading="savingVideoUrl" @click="handleConfirmEditVideoUrl">
            保存
          </el-button>
      </div>
      </template>
    </el-dialog>

    <!-- 视频放大预览 -->
    <el-dialog
      v-model="previewVisible"
      :show-close="true"
      class="video-preview-dialog"
      width="980px"
      align-center
      :append-to-body="true"
      :close-on-click-modal="true"
      :close-on-press-escape="true"
    >
      <div v-if="previewSrc" class="preview-video-body">
        <video
          :src="previewSrc"
          controls
          autoplay
          class="preview-video-player"
          preload="metadata"
        />
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { ElMessage, ElIcon } from 'element-plus'
import { useRouter } from 'vue-router'
import { Back, Download, Edit, FolderOpened, Link, Refresh, VideoPlay, ZoomIn } from '@element-plus/icons-vue'
import { videoApi, projectApi, scriptApi } from '@/api'
import { useProjectStore } from '@/stores'
import type { VideoSegment } from '@/types'

const props = defineProps<{
  projectId: number | null
}>()

const projectStore = useProjectStore()
const router = useRouter()

// 状态
const videoSegments = ref<VideoSegment[]>([])
const generatingVideos = ref(false)
const exporting = ref(false)
const concatenatingProgress = ref(0)
const concatenatingMessage = ref('准备拼接...')
const videoModels = ref<any[]>([])
// 默认不写死模型：等加载到可用模型列表后，自动选择列表第一个
const selectedVideoModel = ref<string>('')

type ComposeState = 'idle' | 'composing' | 'done'
const compose_state = ref<ComposeState>('idle')
const composed_download_url = ref<string>('')
const exported_url_from_server = ref<string>('')
const exported_url_loaded = ref(false)

const existing_composed_url = computed(() => {
  const script: any = projectStore.currentScript as any
  return (
    String(exported_url_from_server.value || '').trim() ||
    String(script?.exportedVideoUrl || script?.exported_video_url || '').trim() ||
    String(composed_download_url.value || '').trim()
  )
})

const has_existing_composed_video = computed(() => {
  return Boolean(existing_composed_url.value)
})

const project_resolution_hint = computed(() => {
  const ratio = String((projectStore.currentProject as any)?.aspectRatio || '')
  return ratio === '9:16' ? '1080x1920' : '1920x1080'
})

const previewVisible = ref(false)
const previewSrc = ref('')

const open_video_preview = (video: VideoSegment) => {
  if (!video?.videoUrl || video.status !== 'completed') return
  previewSrc.value = String(video.videoUrl)
  previewVisible.value = true
}

// 编辑相关
const editVideoDescriptionDialogVisible = ref(false)
const editingVideoDescription = ref('')
const editingVideo = ref<VideoSegment | null>(null)
const editingVideoModel = ref('')
const regeneratingVideoFromEdit = ref(false)
const editVideoUrlDialogVisible = ref(false)
const editingVideoUrl = ref('')
const savingVideoUrl = ref(false)

let pollingTimer: ReturnType<typeof setInterval> | null = null

// 计算属性
const sortedVideos = computed(() => {
  return [...videoSegments.value].sort((a, b) => a.segmentIndex - b.segmentIndex)
})

const allVideosCompleted = computed(() => {
  return videoSegments.value.length > 0 && videoSegments.value.every(v => v.status === 'completed')
})

// 方法
const getVideoSegmentTitle = (video: VideoSegment) => `第${video.segmentIndex + 1}段`

const go_to_keyframes = () => {
  if (props.projectId) {
    router.push(`/project/${props.projectId}/keyframes`)
    return
  }
  router.back()
}

const view_composed_video = () => {
  const url = existing_composed_url.value
  if (!url) return
  composed_download_url.value = url
  compose_state.value = 'done'
}

const back_to_segments = () => {
  compose_state.value = 'idle'
}

const loadVideoSegments = async () => {
  let scriptId = projectStore.currentScript?.id
  
  // 如果store中没有scriptId，尝试重新加载项目信息
  if (!scriptId && props.projectId) {
    try {
      const project = await projectApi.getProject(props.projectId)
      projectStore.setCurrentProject(project as any)
      scriptId = (project as any)?.script?.id
    } catch (e) {
      console.error('重新加载项目失败:', e)
    }
  }
  
  if (!scriptId) {
    console.warn('无法获取scriptId，跳过加载视频')
    return
  }

  try {
    const response = await videoApi.getVideoSegmentsByScript(scriptId)
    videoSegments.value = response.videoSegments || []
    
    const hasGenerating = videoSegments.value.some(v =>
      ['generating', 'pending'].includes(v.status)
    )
    
    if (hasGenerating) {
      generatingVideos.value = true
      startPolling()
    } else {
      generatingVideos.value = false
      stopPolling()
    }
    // 更新store
    projectStore.updateVideoSegments(videoSegments.value)

    // 补充拉取脚本详情（project 接口不返回 exportedVideoUrl），用于判断“已合成则查看视频”
    if (!exported_url_loaded.value) {
      try {
        const script: any = await scriptApi.getScript(scriptId)
        exported_url_from_server.value = String(script?.exportedVideoUrl || '').trim()
        exported_url_loaded.value = true
      } catch (e) {
        // 不阻塞主流程：拿不到就保持原逻辑
        console.warn('加载脚本导出链接失败，跳过:', e)
      }
    }
  } catch (error) {
    console.error('加载视频片段失败:', error)
    stopPolling()
  }
}

const startPolling = () => {
  if (pollingTimer) return
  pollingTimer = setInterval(async () => {
    await loadVideoSegments()
    const allFinished = videoSegments.value.every(v =>
      ['completed', 'failed'].includes(v.status)
    )
    if (allFinished) {
      stopPolling()
      generatingVideos.value = false
    }
  }, 3000)
}

const stopPolling = () => {
  if (pollingTimer) {
    clearInterval(pollingTimer)
    pollingTimer = null
  }
}

const handleRefreshVideo = async (videoId: number) => {
  try {
    // 默认使用当前选中的模型；若当前值无效，则使用可用列表第一个
    const model = selectedVideoModel.value || videoModels.value[0]?.id
    if (!model) {
      ElMessage.error('未获取到可用的视频模型，请稍后重试')
      return
    }
    await videoApi.regenerateVideoSegment(videoId, model)
    ElMessage.success('已开始重新生成')
    await loadVideoSegments()
    startPolling()
  } catch (error: any) {
    ElMessage.error(error?.message || '重新生成失败')
  }
}

const handleCancelVideo = async (video: VideoSegment) => {
  try {
    await videoApi.updateVideoSegment(video.id, { status: 'failed', errorMessage: '用户中断重试' })
    ElMessage.info('已请求中断')
    await loadVideoSegments()
  } catch (error: any) {
    ElMessage.error(error?.message || '中断失败')
  }
}

const handleExportVideos = async (exportType: 'separate' | 'concatenated') => {
  const scriptId = projectStore.currentScript?.id
  if (!scriptId) return
  
  exporting.value = true
  if (exportType === 'concatenated') {
    // 兼容旧调用：转到新的“合成中 -> 合成完成(仅下载)”流程
    await start_compose()
    return
  }

  {
    try {
      ElMessage.info('正在打包...')
      const response = await videoApi.exportVideos(scriptId, exportType)
      const link = document.createElement('a')
      link.href = response.downloadUrl
      link.download = `videos_${Date.now()}.zip`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      ElMessage.success('导出成功')
    } catch (error: any) {
      ElMessage.error(error?.message || '导出失败')
    } finally {
      exporting.value = false
    }
  }
}

const start_compose = async () => {
  const scriptId = projectStore.currentScript?.id
  if (!scriptId) return
  if (!allVideosCompleted.value) return

  exporting.value = true
  compose_state.value = 'composing'
  composed_download_url.value = ''
  concatenatingProgress.value = 0
  concatenatingMessage.value = '正在合成视频...'

  const interval = setInterval(() => {
    if (concatenatingProgress.value < 90) {
      const increment = 4 + Math.random() * 8
      concatenatingProgress.value = Math.min(90, concatenatingProgress.value + increment)
    }
  }, 700)

  try {
    const response = await videoApi.exportVideos(scriptId, 'concatenated')
    composed_download_url.value = response.downloadUrl
    concatenatingProgress.value = 100
    concatenatingMessage.value = '合成完成'
    await new Promise(r => setTimeout(r, 400))
    compose_state.value = 'done'
    } catch (error: any) {
    ElMessage.error(error?.message || '合成失败')
    compose_state.value = 'idle'
    } finally {
      exporting.value = false
    clearInterval(interval)
    }
  }

const download_composed_video = () => {
  if (!composed_download_url.value) return
  const link = document.createElement('a')
  link.href = composed_download_url.value
  link.download = `video_${Date.now()}.mp4`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

// 编辑相关
const handleEditVideoDescription = (video: VideoSegment) => {
  editingVideo.value = video
  editingVideoDescription.value = video.prompt || ''
  editingVideoModel.value = selectedVideoModel.value || videoModels.value[0]?.id
  editVideoDescriptionDialogVisible.value = true
}

const handleEditVideoUrl = (video: VideoSegment) => {
  editingVideo.value = video
  editingVideoUrl.value = String(video.videoUrl || '').trim()
  editVideoUrlDialogVisible.value = true
}

const handleConfirmEditVideoUrl = async () => {
  if (!editingVideo.value) return
  const url = String(editingVideoUrl.value || '').trim()
  if (!url || (!url.startsWith('http://') && !url.startsWith('https://'))) {
    ElMessage.error('请输入有效的 http/https 视频链接')
    return
  }

  savingVideoUrl.value = true
  try {
    await videoApi.updateVideoSegment(editingVideo.value.id, { videoUrl: url })
    ElMessage.success('已更新视频链接')
    editVideoUrlDialogVisible.value = false
    await loadVideoSegments()
  } catch (error: any) {
    ElMessage.error(error?.message || '更新视频链接失败')
  } finally {
    savingVideoUrl.value = false
  }
}

const handleCancelEditVideoUrl = () => {
  editVideoUrlDialogVisible.value = false
}

const handleConfirmEditVideoDescription = async () => {
  if (!editingVideo.value) return
  regeneratingVideoFromEdit.value = true
  try {
    await videoApi.updateVideoSegment(editingVideo.value.id, { prompt: editingVideoDescription.value.trim() })
    await videoApi.regenerateVideoSegment(editingVideo.value.id, editingVideoModel.value)
    ElMessage.success('已开始重新生成视频')
    editVideoDescriptionDialogVisible.value = false
    await loadVideoSegments()
    startPolling()
  } catch (error: any) {
    ElMessage.error(error?.message || '编辑并重新生成失败')
  } finally {
    regeneratingVideoFromEdit.value = false
  }
}

const handleCancelEditVideoDescription = () => {
    editVideoDescriptionDialogVisible.value = false
}

const loadVideoModels = async () => {
  try {
    const res = await videoApi.getVideoModels()
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

// 下载单个视频
const handleDownloadVideo = async (video: VideoSegment) => {
  if (!video.videoUrl) {
    ElMessage.warning('视频地址不存在')
    return
  }
  
  const loadingMsg = ElMessage.info({
    message: '正在下载视频...',
    duration: 0
  })
  
  try {
    // 使用后端代理API下载，设置正确的响应头强制下载
    const proxyUrl = `/api/files/proxy?url=${encodeURIComponent(video.videoUrl)}`
    const response = await fetch(proxyUrl)
    
    if (!response.ok) {
      throw new Error('下载失败')
    }
    
    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `video_segment_${video.segmentIndex + 1}.mp4`
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

onMounted(async () => {
  await loadVideoModels()
  await loadVideoSegments()
})

onUnmounted(() => {
  stopPolling()
})

watch(() => props.projectId, async (newVal) => {
  if (newVal) {
    stopPolling()
    videoSegments.value = []
    await loadVideoSegments()
  }
})
</script>

<style scoped>
.video-list-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f3f4f6;
  overflow: hidden;
}

.videos-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  box-sizing: border-box;
}

.video-grid {
  display: grid;
  /* 一行最多 4 个，超过 4 个自动换行；用弹性列避免右侧大片空白 */
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 20px;
  align-items: start;
  justify-content: start;
}

.video-card {
  background: #fff;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid #e5e7eb;
  height: 258px;
}

.card-video-area {
  position: relative;
  width: 100%;
  height: 166px;
  background: #000;
}

.video-player-container, .video-placeholder {
  position: absolute; top: 0; left: 0; width: 100%; height: 100%;
}

.video-player-container {
  cursor: default;
}

.video-player { width: 100%; height: 100%; object-fit: contain; }

.vid-play-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}

.vid-play-btn {
  pointer-events: auto;
  width: 44px;
  height: 44px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(229, 231, 235, 0.7);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.22);
}

.video-player-container:hover .vid-play-btn {
  transform: scale(1.04);
}

.preview-video-body {
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

.video-placeholder {
  display: flex; flex-direction: column; justify-content: center; align-items: center;
  color: #fff; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}
.video-placeholder.generating { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
.video-placeholder.failed { background: linear-gradient(135deg, #ff6b6b 0%, #ee5a6f 100%); }

.loading-animation { width: 60%; height: 6px; background: rgba(255,255,255,0.2); border-radius: 3px; margin-bottom: 15px; overflow: hidden; }
.loading-bar { width: 30%; height: 100%; background: #fff; animation: loading-slide 1.8s infinite; }

@keyframes loading-slide {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(400%); }
}

.loading-text {
  font-size: 16px;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
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

.loading-icon {
  font-size: 24px;
  animation: bounce 1s infinite;
}

@keyframes bounce {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-10px); }
}

.loading-tip { font-size: 13px; color: rgba(255, 255, 255, 0.8); }

.pending-animation {
  margin-bottom: 15px;
}

.pulse-circle {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.3);
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.2); opacity: 0.6; }
}

.pending-text {
  font-size: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.pending-icon {
  font-size: 24px;
}

.failed-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.failed-text {
  font-size: 16px;
  margin-bottom: 8px;
}

.error-detail {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.9);
  margin-bottom: 16px;
  padding: 0 24px;
  line-height: 1.5;
}

.retry-btn {
  margin-top: 8px;
}

.placeholder-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.placeholder-text {
  font-size: 16px;
  color: rgba(255, 255, 255, 0.9);
}

.card-description {
  padding: 16px;
  font-size: 12px;
  color: #6a7282;
  height: 92px;
  overflow: hidden;
  line-height: 19.5px;
  box-sizing: border-box;
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

.edit-description-content { padding: 10px 0; }
.dialog-footer { display: flex; align-items: center; gap: 12px; }

/* 顶部页头（Figma 19:3504） */
.vf-page-header {
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

.vf-page-title {
  font-size: 18px;
  font-weight: 600;
  color: #1e2939;
  line-height: 28px;
}

.vf-page-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.vf-btn {
  height: 36px;
  border-radius: 8px;
}

.vf-btn.vf-btn-ghost {
  background: #ffffff;
  border: 1px solid #d1d5dc;
  color: #0a0a0a;
}

.vf-btn.vf-btn-primary {
  background: linear-gradient(180deg, #2b7fff 0%, #00b8db 100%);
  border: none;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1),
    0 2px 4px -2px rgba(0, 0, 0, 0.1);
}

/* hover 操作按钮（与关键帧页一致风格） */
.vid-actions {
  position: absolute;
  top: 12px;
  right: 12px;
  display: flex;
  gap: 8px;
  opacity: 0;
  transition: opacity 0.15s ease;
}

.video-player-container:hover .vid-actions {
  opacity: 1;
}

.vid-action-btn {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(229, 231, 235, 0.6);
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1),
    0 2px 4px -2px rgba(0, 0, 0, 0.1);
}

.vid-tag {
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
}

/* 合成中 / 合成完成 */
.compose-header {
  height: 61px;
  flex: 0 0 61px;
  background: #ffffff;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  padding: 0 24px;
  box-sizing: border-box;
}

.compose-title {
  font-size: 18px;
  font-weight: 600;
  color: #1e2939;
}

.compose-body {
  flex: 1;
  overflow: auto;
  padding: 24px 136px 0;
  box-sizing: border-box;
}

/* 合成完成（Figma 19:3982，保留下载按钮） */
.vf-done-header {
  height: 69px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: #ffffff;
  border-bottom: 1px solid #e5e7eb;
}

.vf-done-title {
  display: inline-flex;
  align-items: center;
  gap: 12px;
}

.vf-done-title-text {
  font-size: 18px;
  font-weight: 700;
  color: #1e2939;
  line-height: 28px;
}

.vf-done-title-dot {
  width: 20px;
  height: 20px;
  position: relative;
}

.vf-done-title-dot::after {
  content: '';
  position: absolute;
  inset: 4px;
  border-radius: 50%;
  background: linear-gradient(180deg, #2b7fff 0%, #00b8db 100%);
}

.vf-done-download {
  height: 36px;
  border-radius: 8px;
  border: none;
  background: linear-gradient(180deg, #2b7fff 0%, #00b8db 100%);
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1),
    0 2px 4px -2px rgba(0, 0, 0, 0.1);
}

.vf-done-content {
  padding: 24px 24px 0 24px;
}

.vf-preview-card {
  max-width: 1022px;
  margin: 0 auto;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  overflow: hidden;
}

.vf-preview-head {
  padding: 24px;
  border-bottom: 1px solid #e5e7eb;
}

.vf-preview-title {
  font-size: 18px;
  font-weight: 700;
  color: #1e2939;
  line-height: 28px;
}

.vf-preview-sub {
  margin-top: 4px;
  font-size: 14px;
  color: #6a7282;
  line-height: 20px;
}

.vf-preview-player {
  background: #000;
  height: 575px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.vf-preview-video {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: #000;
}

.vf-preview-meta {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  padding: 12px 24px;
  background: #f9fafb;
}

.vf-meta-label {
  font-size: 12px;
  color: #6a7282;
  line-height: 16px;
}

.vf-meta-value {
  margin-top: 4px;
  font-size: 14px;
  font-weight: 700;
  color: #1e2939;
  line-height: 20px;
}

@media (max-width: 1200px) {
  .vf-preview-player {
    height: 420px;
  }
  .vf-preview-meta {
    grid-template-columns: repeat(2, 1fr);
  }
}

.compose-card {
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 33px 176px;
  box-sizing: border-box;
  height: 354px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.compose-card-inner {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.compose-hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.compose-icon {
  width: 64px;
  height: 64px;
  border-radius: 999px;
  background: linear-gradient(180deg, #2b7fff 0%, #00b8db 100%);
  position: relative;
}

.compose-icon::after {
  content: '';
  position: absolute;
  inset: 12px;
  border-radius: 999px;
  border: 4px solid #ffffff;
  border-left-color: transparent;
  border-bottom-color: transparent;
  animation: spin 1.2s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.compose-hero-title {
  font-size: 20px;
  font-weight: 600;
  color: #1e2939;
  line-height: 28px;
}

.compose-hero-sub {
  font-size: 14px;
  color: #6a7282;
  line-height: 20px;
}

.compose-progress {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.compose-progress-track {
  height: 8px;
  background: rgba(3, 2, 19, 0.2);
  border-radius: 999px;
  overflow: hidden;
}

.compose-progress-fill {
  height: 8px;
  background: #030213;
  border-radius: 999px;
}

.compose-progress-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.compose-progress-label {
  font-size: 14px;
  color: #6a7282;
}

.compose-progress-value {
  font-size: 14px;
  font-weight: 500;
  color: #2b7fff;
}

.compose-stats {
  display: flex;
  gap: 16px;
}

.compose-stat {
  flex: 1;
  background: #f9fafb;
  border-radius: 10px;
  padding: 12px;
  box-sizing: border-box;
  height: 64px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: center;
  justify-content: center;
}

.compose-stat-label {
  font-size: 12px;
  color: #6a7282;
  line-height: 16px;
}

.compose-stat-value {
  font-size: 14px;
  font-weight: 600;
  color: #1e2939;
  line-height: 20px;
}

.compose-done-card {
  align-items: center;
  gap: 16px;
}

.compose-done-title {
  font-size: 18px;
  font-weight: 600;
  color: #1e2939;
}

.compose-download-btn {
  height: 36px;
  border-radius: 10px;
  padding: 0 24px;
  background: linear-gradient(166deg, #2b7fff 0%, #00b8db 100%);
  border: none;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1),
    0 2px 4px -2px rgba(0, 0, 0, 0.1);
}

@media (max-width: 1400px) {
  .video-grid {
    grid-template-columns: repeat(3, minmax(260px, 1fr));
  }
}

@media (max-width: 1100px) {
  .video-grid {
    grid-template-columns: repeat(2, minmax(260px, 1fr));
  }
  .compose-body {
    padding: 24px 24px 0;
  }
  .compose-card {
    padding: 28px 24px;
  }
}

@media (max-width: 700px) {
  .video-grid {
    grid-template-columns: 1fr;
  }
  .vf-page-header {
    flex-wrap: wrap;
    height: auto;
    gap: 12px;
    padding: 12px 16px;
  }
  .videos-content {
    padding: 16px;
  }
}
</style>
