<template>
  <div class="studio-container">
    <!-- 顶部导航栏 -->
    <header class="studio-header">
      <div class="header-left">
        <el-button text @click="goBack" class="back-btn">
          <el-icon><ArrowLeft /></el-icon>
        </el-button>
        <h1 class="project-title">{{ projectTitle }}</h1>
        <el-tag type="info" size="small" v-if="projectStatus">{{ projectStatus }}</el-tag>
      </div>
      <div class="header-center">
        <el-button-group>
          <el-button :type="viewMode === 'timeline' ? 'primary' : 'default'" @click="viewMode = 'timeline'">
            <el-icon><VideoCamera /></el-icon>
            时间线
          </el-button>
          <el-button :type="viewMode === 'script' ? 'primary' : 'default'" @click="viewMode = 'script'">
            <el-icon><Document /></el-icon>
            脚本
          </el-button>
        </el-button-group>
      </div>
      <div class="header-right">
        <el-button type="success" @click="handleExport" :loading="exporting">
          <el-icon><Download /></el-icon>
          导出视频
        </el-button>
      </div>
    </header>

    <!-- 主工作区 -->
    <main class="studio-main">
      <!-- 左侧：AI Agent 面板 -->
      <aside class="agent-panel" :class="{ collapsed: agentCollapsed }">
        <div class="panel-header">
          <span class="panel-title">
            <el-icon><ChatDotRound /></el-icon>
            AI 助手
          </span>
          <el-button text @click="agentCollapsed = !agentCollapsed">
            <el-icon><component :is="agentCollapsed ? 'Expand' : 'Fold'" /></el-icon>
          </el-button>
        </div>
        <div class="panel-content" v-show="!agentCollapsed">
          <!-- Agent 对话 -->
          <div class="chat-messages" ref="chatMessagesRef">
            <div 
              v-for="(msg, idx) in agentMessages" 
              :key="idx" 
              class="chat-message"
              :class="msg.role"
            >
              <div class="message-avatar">
                <el-icon v-if="msg.role === 'assistant'"><Robot /></el-icon>
                <el-icon v-else><User /></el-icon>
              </div>
              <div class="message-content">
                <div class="message-text">{{ msg.content }}</div>
                <div class="message-actions" v-if="msg.actions">
                  <div 
                    v-for="(action, aidx) in msg.actions" 
                    :key="aidx" 
                    class="action-capsule"
                    :class="action.status"
                  >
                    <el-icon><component :is="getActionIcon(action.type)" /></el-icon>
                    <span>{{ action.label }}</span>
                    <span class="action-status">
                      <el-icon v-if="action.status === 'running'" class="is-loading"><Loading /></el-icon>
                      <el-icon v-else-if="action.status === 'done'"><CircleCheck /></el-icon>
                      <el-icon v-else-if="action.status === 'error'"><CircleClose /></el-icon>
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <!-- Agent 输入 -->
          <div class="chat-input">
            <el-input
              v-model="agentInput"
              type="textarea"
              :rows="2"
              placeholder="描述你想要创建的视频..."
              @keydown.enter.ctrl="sendAgentMessage"
            />
            <el-button type="primary" @click="sendAgentMessage" :loading="agentThinking">
              <el-icon><Promotion /></el-icon>
            </el-button>
          </div>
        </div>
      </aside>

      <!-- 中间：预览 + 时间线 -->
      <section class="editor-area">
        <!-- 预览播放器 -->
        <div class="preview-container">
          <div class="preview-player" ref="previewPlayerRef">
            <div class="player-placeholder" v-if="!currentPreviewUrl">
              <el-icon :size="64"><VideoPlay /></el-icon>
              <p>预览区域</p>
            </div>
            <video 
              v-else 
              ref="videoRef"
              :src="currentPreviewUrl" 
              @timeupdate="onTimeUpdate"
              @loadedmetadata="onVideoLoaded"
            />
          </div>
          <div class="player-controls">
            <el-button-group>
              <el-button text @click="skipBackward">
                <el-icon><DArrowLeft /></el-icon>
              </el-button>
              <el-button text @click="togglePlay">
                <el-icon><component :is="isPlaying ? 'VideoPause' : 'VideoPlay'" /></el-icon>
              </el-button>
              <el-button text @click="skipForward">
                <el-icon><DArrowRight /></el-icon>
              </el-button>
            </el-button-group>
            <span class="time-display">{{ formatTime(currentTime) }} / {{ formatTime(duration) }}</span>
            <el-slider 
              v-model="volume" 
              :min="0" 
              :max="100" 
              :show-tooltip="false"
              class="volume-slider"
            />
          </div>
        </div>

        <!-- 时间线编辑器 -->
        <div class="timeline-container">
          <div class="timeline-toolbar">
            <el-button-group>
              <el-button text @click="zoomOut" :disabled="zoomLevel <= 0.25">
                <el-icon><ZoomOut /></el-icon>
              </el-button>
              <span class="zoom-level">{{ Math.round(zoomLevel * 100) }}%</span>
              <el-button text @click="zoomIn" :disabled="zoomLevel >= 4">
                <el-icon><ZoomIn /></el-icon>
              </el-button>
            </el-button-group>
            <el-button-group>
              <el-button text @click="undo" :disabled="!canUndo">
                <el-icon><RefreshLeft /></el-icon>
              </el-button>
              <el-button text @click="redo" :disabled="!canRedo">
                <el-icon><RefreshRight /></el-icon>
              </el-button>
            </el-button-group>
          </div>
          <div class="timeline-tracks" ref="timelineRef">
            <!-- 时间刻度 -->
            <div class="timeline-ruler">
              <div 
                v-for="tick in timelineTicks" 
                :key="tick.time"
                class="ruler-tick"
                :style="{ left: `${tick.position}px` }"
              >
                <span class="tick-label">{{ tick.label }}</span>
              </div>
              <!-- 播放头 -->
              <div 
                class="playhead"
                :style="{ left: `${playheadPosition}px` }"
              />
            </div>
            <!-- 视频轨道 -->
            <div class="track video-track">
              <div class="track-label">
                <el-icon><VideoCamera /></el-icon>
                视频
              </div>
              <div class="track-clips">
                <div 
                  v-for="clip in videoClips" 
                  :key="clip.id"
                  class="clip video-clip"
                  :style="getClipStyle(clip)"
                  @click="selectClip(clip)"
                  :class="{ selected: selectedClip?.id === clip.id }"
                >
                  <img :src="clip.thumbnail" v-if="clip.thumbnail" />
                  <span class="clip-label">{{ clip.label }}</span>
                </div>
              </div>
            </div>
            <!-- 配音轨道 -->
            <div class="track speech-track">
              <div class="track-label">
                <el-icon><Microphone /></el-icon>
                配音
              </div>
              <div class="track-clips">
                <div 
                  v-for="clip in speechClips" 
                  :key="clip.id"
                  class="clip speech-clip"
                  :style="getClipStyle(clip)"
                  @click="selectClip(clip)"
                  :class="{ selected: selectedClip?.id === clip.id }"
                >
                  <div class="waveform-placeholder"></div>
                  <span class="clip-label">{{ clip.label }}</span>
                </div>
              </div>
            </div>
            <!-- BGM 轨道 -->
            <div class="track bgm-track">
              <div class="track-label">
                <el-icon><Headset /></el-icon>
                BGM
              </div>
              <div class="track-clips">
                <div 
                  v-for="clip in bgmClips" 
                  :key="clip.id"
                  class="clip bgm-clip"
                  :style="getClipStyle(clip)"
                  @click="selectClip(clip)"
                  :class="{ selected: selectedClip?.id === clip.id }"
                >
                  <span class="clip-label">{{ clip.label }}</span>
                </div>
              </div>
            </div>
            <!-- 字幕轨道 -->
            <div class="track caption-track">
              <div class="track-label">
                <el-icon><ChatLineSquare /></el-icon>
                字幕
              </div>
              <div class="track-clips">
                <div 
                  v-for="clip in captionClips" 
                  :key="clip.id"
                  class="clip caption-clip"
                  :style="getClipStyle(clip)"
                  @click="selectClip(clip)"
                  :class="{ selected: selectedClip?.id === clip.id }"
                >
                  <span class="clip-label">{{ clip.text }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 右侧：资产面板 -->
      <aside class="assets-panel" :class="{ collapsed: assetsCollapsed }">
        <div class="panel-header">
          <span class="panel-title">
            <el-icon><FolderOpened /></el-icon>
            资产库
          </span>
          <el-button text @click="assetsCollapsed = !assetsCollapsed">
            <el-icon><component :is="assetsCollapsed ? 'Expand' : 'Fold'" /></el-icon>
          </el-button>
        </div>
        <div class="panel-content" v-show="!assetsCollapsed">
          <el-tabs v-model="assetsTab">
            <el-tab-pane label="图片" name="images">
              <div class="assets-grid">
                <div 
                  v-for="asset in imageAssets" 
                  :key="asset.id"
                  class="asset-item"
                  draggable="true"
                  @dragstart="onDragStart($event, asset)"
                >
                  <img :src="asset.thumbnail || asset.url" />
                </div>
              </div>
            </el-tab-pane>
            <el-tab-pane label="视频" name="videos">
              <div class="assets-grid">
                <div 
                  v-for="asset in videoAssets" 
                  :key="asset.id"
                  class="asset-item"
                  draggable="true"
                  @dragstart="onDragStart($event, asset)"
                >
                  <video :src="asset.url" muted />
                  <el-icon class="play-icon"><VideoPlay /></el-icon>
                </div>
              </div>
            </el-tab-pane>
            <el-tab-pane label="音频" name="audio">
              <div class="assets-list">
                <div 
                  v-for="asset in audioAssets" 
                  :key="asset.id"
                  class="asset-audio-item"
                  draggable="true"
                  @dragstart="onDragStart($event, asset)"
                >
                  <el-icon><Headset /></el-icon>
                  <span>{{ asset.name }}</span>
                  <span class="duration">{{ formatTime(asset.duration / 1000) }}</span>
                </div>
              </div>
            </el-tab-pane>
          </el-tabs>
        </div>
      </aside>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  ArrowLeft,
  VideoCamera,
  Document,
  Download,
  ChatDotRound,
  Expand,
  Fold,
  User,
  Promotion,
  VideoPlay,
  VideoPause,
  DArrowLeft,
  DArrowRight,
  ZoomIn,
  ZoomOut,
  RefreshLeft,
  RefreshRight,
  Microphone,
  Headset,
  ChatLineSquare,
  FolderOpened,
  CircleCheck,
  CircleClose,
  Loading,
} from '@element-plus/icons-vue'

// 路由
const route = useRoute()
const router = useRouter()

// 项目信息
const projectTitle = ref('新项目')
const projectStatus = ref('')
const projectId = computed(() => route.params.projectId as string)

// 视图模式
const viewMode = ref<'timeline' | 'script'>('timeline')

// 面板折叠状态
const agentCollapsed = ref(false)
const assetsCollapsed = ref(false)

// AI Agent
const agentInput = ref('')
const agentThinking = ref(false)
const agentMessages = ref<Array<{
  role: 'user' | 'assistant'
  content: string
  actions?: Array<{
    type: string
    label: string
    status: 'pending' | 'running' | 'done' | 'error'
  }>
}>>([
  {
    role: 'assistant',
    content: '你好！我是你的 AI 创作助手。告诉我你想创建什么样的视频，我会帮你完成脚本、图片、视频和配音的生成。',
  }
])

// 预览播放器
const currentPreviewUrl = ref('')
const videoRef = ref<HTMLVideoElement>()
const isPlaying = ref(false)
const currentTime = ref(0)
const duration = ref(0)
const volume = ref(80)

// 时间线
const zoomLevel = ref(1)
const playheadPosition = ref(0)
const selectedClip = ref<any>(null)

// 撤销/重做
const canUndo = ref(false)
const canRedo = ref(false)

// 资产
const assetsTab = ref('images')
const imageAssets = ref<any[]>([])
const videoAssets = ref<any[]>([])
const audioAssets = ref<any[]>([])

// 轨道 Clips（示例数据）
const videoClips = ref<any[]>([])
const speechClips = ref<any[]>([])
const bgmClips = ref<any[]>([])
const captionClips = ref<any[]>([])

// 导出
const exporting = ref(false)

// 时间线刻度
const timelineTicks = computed(() => {
  const ticks = []
  const totalSeconds = duration.value || 60
  const pixelsPerSecond = 50 * zoomLevel.value
  
  for (let i = 0; i <= totalSeconds; i += 5) {
    ticks.push({
      time: i,
      position: i * pixelsPerSecond,
      label: formatTime(i),
    })
  }
  return ticks
})

// 方法
function goBack() {
  router.push('/inspiration')
}

function handleExport() {
  exporting.value = true
  ElMessage.info('导出功能开发中...')
  setTimeout(() => {
    exporting.value = false
  }, 1000)
}

function sendAgentMessage() {
  if (!agentInput.value.trim()) return
  
  const userMessage = agentInput.value.trim()
  agentMessages.value.push({
    role: 'user',
    content: userMessage,
  })
  agentInput.value = ''
  agentThinking.value = true
  
  // 模拟 AI 响应
  setTimeout(() => {
    agentMessages.value.push({
      role: 'assistant',
      content: '好的，我来帮你创建视频。让我开始准备...',
      actions: [
        { type: 'script', label: '生成脚本', status: 'running' },
        { type: 'image', label: '生成关键帧', status: 'pending' },
        { type: 'video', label: '生成视频', status: 'pending' },
        { type: 'tts', label: '生成配音', status: 'pending' },
      ]
    })
    agentThinking.value = false
  }, 1500)
}

function getActionIcon(type: string) {
  const icons: Record<string, any> = {
    script: Document,
    image: VideoCamera,
    video: VideoPlay,
    tts: Microphone,
  }
  return icons[type] || Document
}

function togglePlay() {
  if (!videoRef.value) return
  if (isPlaying.value) {
    videoRef.value.pause()
  } else {
    videoRef.value.play()
  }
  isPlaying.value = !isPlaying.value
}

function skipBackward() {
  if (!videoRef.value) return
  videoRef.value.currentTime = Math.max(0, videoRef.value.currentTime - 5)
}

function skipForward() {
  if (!videoRef.value) return
  videoRef.value.currentTime = Math.min(duration.value, videoRef.value.currentTime + 5)
}

function onTimeUpdate() {
  if (!videoRef.value) return
  currentTime.value = videoRef.value.currentTime
  updatePlayhead()
}

function onVideoLoaded() {
  if (!videoRef.value) return
  duration.value = videoRef.value.duration
}

function updatePlayhead() {
  const pixelsPerSecond = 50 * zoomLevel.value
  playheadPosition.value = currentTime.value * pixelsPerSecond
}

function zoomIn() {
  zoomLevel.value = Math.min(4, zoomLevel.value * 1.5)
}

function zoomOut() {
  zoomLevel.value = Math.max(0.25, zoomLevel.value / 1.5)
}

function undo() {
  ElMessage.info('撤销功能开发中...')
}

function redo() {
  ElMessage.info('重做功能开发中...')
}

function getClipStyle(clip: any) {
  const pixelsPerSecond = 50 * zoomLevel.value
  return {
    left: `${clip.startMs / 1000 * pixelsPerSecond}px`,
    width: `${(clip.endMs - clip.startMs) / 1000 * pixelsPerSecond}px`,
  }
}

function selectClip(clip: any) {
  selectedClip.value = clip
}

function onDragStart(event: DragEvent, asset: any) {
  event.dataTransfer?.setData('application/json', JSON.stringify(asset))
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

// 加载项目数据
onMounted(async () => {
  if (projectId.value) {
    // TODO: 加载项目数据
    projectTitle.value = `项目 ${projectId.value}`
    projectStatus.value = '编辑中'
  }
  
  // 添加示例数据
  videoClips.value = [
    { id: 'v1', startMs: 0, endMs: 5000, label: '片段 1', thumbnail: '' },
    { id: 'v2', startMs: 5000, endMs: 12000, label: '片段 2', thumbnail: '' },
    { id: 'v3', startMs: 12000, endMs: 20000, label: '片段 3', thumbnail: '' },
  ]
  speechClips.value = [
    { id: 's1', startMs: 500, endMs: 4500, label: '配音 1' },
    { id: 's2', startMs: 5500, endMs: 11000, label: '配音 2' },
    { id: 's3', startMs: 12500, endMs: 19000, label: '配音 3' },
  ]
  captionClips.value = [
    { id: 'c1', startMs: 500, endMs: 4500, text: '欢迎来到...' },
    { id: 'c2', startMs: 5500, endMs: 11000, text: '这是第二段...' },
  ]
  
  duration.value = 20
})

// 监听音量变化
watch(volume, (val) => {
  if (videoRef.value) {
    videoRef.value.volume = val / 100
  }
})
</script>

<style scoped>
.studio-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #0a0a0f;
  color: #e0e0e0;
  font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* 顶部导航 */
.studio-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  background: linear-gradient(180deg, #15151d 0%, #0f0f15 100%);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.back-btn {
  color: #888;
}

.project-title {
  font-size: 16px;
  font-weight: 500;
  margin: 0;
}

.header-center {
  display: flex;
  gap: 8px;
}

.header-right {
  display: flex;
  gap: 12px;
}

/* 主工作区 */
.studio-main {
  display: flex;
  flex: 1;
  overflow: hidden;
}

/* 左侧 Agent 面板 */
.agent-panel {
  width: 320px;
  background: #12121a;
  border-right: 1px solid rgba(255, 255, 255, 0.06);
  display: flex;
  flex-direction: column;
  transition: width 0.3s ease;
}

.agent-panel.collapsed {
  width: 48px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
  color: #a0a0a0;
}

.panel-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Agent 对话 */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.chat-message {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.chat-message.user {
  flex-direction: row-reverse;
}

.message-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.chat-message.user .message-avatar {
  background: linear-gradient(135deg, #3b82f6 0%, #06b6d4 100%);
}

.message-content {
  max-width: 80%;
}

.message-text {
  background: #1e1e28;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.5;
}

.chat-message.user .message-text {
  background: #2563eb;
  color: white;
}

.message-actions {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.action-capsule {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  background: #1a1a24;
  border-radius: 16px;
  font-size: 12px;
  color: #888;
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.action-capsule.running {
  border-color: #f59e0b;
  color: #f59e0b;
}

.action-capsule.done {
  border-color: #10b981;
  color: #10b981;
}

.action-capsule.error {
  border-color: #ef4444;
  color: #ef4444;
}

.action-status .is-loading {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* Agent 输入 */
.chat-input {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  background: #0f0f15;
}

.chat-input :deep(.el-textarea__inner) {
  background: #1a1a24;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  color: #e0e0e0;
  resize: none;
}

/* 中间编辑区 */
.editor-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 预览容器 */
.preview-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #000;
  min-height: 300px;
}

.preview-player {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.player-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  color: #444;
}

.preview-player video {
  max-width: 100%;
  max-height: 100%;
}

.player-controls {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px 16px;
  background: #15151d;
}

.time-display {
  font-size: 12px;
  color: #888;
  font-variant-numeric: tabular-nums;
}

.volume-slider {
  width: 100px;
}

/* 时间线容器 */
.timeline-container {
  height: 240px;
  background: #12121a;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  display: flex;
  flex-direction: column;
}

.timeline-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.zoom-level {
  font-size: 12px;
  color: #888;
  margin: 0 8px;
}

.timeline-tracks {
  flex: 1;
  overflow-x: auto;
  overflow-y: auto;
  position: relative;
}

.timeline-ruler {
  height: 24px;
  background: #0f0f15;
  position: relative;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.ruler-tick {
  position: absolute;
  top: 0;
  height: 100%;
  border-left: 1px solid rgba(255, 255, 255, 0.1);
}

.tick-label {
  font-size: 10px;
  color: #666;
  margin-left: 4px;
}

.playhead {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 2px;
  background: #ef4444;
  z-index: 10;
}

.playhead::before {
  content: '';
  position: absolute;
  top: 0;
  left: -5px;
  width: 12px;
  height: 12px;
  background: #ef4444;
  border-radius: 2px;
  clip-path: polygon(50% 100%, 0 0, 100% 0);
}

/* 轨道 */
.track {
  display: flex;
  height: 48px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.track-label {
  width: 80px;
  padding: 8px 12px;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #888;
  background: #0f0f15;
  flex-shrink: 0;
}

.track-clips {
  flex: 1;
  position: relative;
}

/* Clip */
.clip {
  position: absolute;
  top: 4px;
  height: 40px;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  overflow: hidden;
  transition: box-shadow 0.2s;
}

.clip:hover {
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.5);
}

.clip.selected {
  box-shadow: 0 0 0 2px #6366f1;
}

.video-clip {
  background: linear-gradient(135deg, #1e3a5f 0%, #1a2744 100%);
}

.speech-clip {
  background: linear-gradient(135deg, #3d1f4a 0%, #2d1438 100%);
}

.bgm-clip {
  background: linear-gradient(135deg, #1f4a3d 0%, #143828 100%);
}

.caption-clip {
  background: linear-gradient(135deg, #4a3d1f 0%, #382814 100%);
}

.clip img {
  height: 100%;
  object-fit: cover;
}

.clip-label {
  padding: 0 8px;
  font-size: 11px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.waveform-placeholder {
  flex: 1;
  height: 60%;
  background: repeating-linear-gradient(
    90deg,
    rgba(139, 92, 246, 0.3) 0px,
    rgba(139, 92, 246, 0.5) 2px,
    rgba(139, 92, 246, 0.3) 4px
  );
  margin: 0 8px;
}

/* 右侧资产面板 */
.assets-panel {
  width: 280px;
  background: #12121a;
  border-left: 1px solid rgba(255, 255, 255, 0.06);
  display: flex;
  flex-direction: column;
  transition: width 0.3s ease;
}

.assets-panel.collapsed {
  width: 48px;
}

.assets-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  padding: 12px;
}

.asset-item {
  aspect-ratio: 16 / 9;
  border-radius: 6px;
  overflow: hidden;
  cursor: grab;
  position: relative;
}

.asset-item img,
.asset-item video {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.asset-item .play-icon {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 24px;
  color: white;
  opacity: 0.8;
}

.assets-list {
  padding: 12px;
}

.asset-audio-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #1a1a24;
  border-radius: 6px;
  margin-bottom: 8px;
  cursor: grab;
  font-size: 13px;
}

.asset-audio-item .duration {
  margin-left: auto;
  color: #666;
  font-size: 12px;
}

/* Element Plus 覆盖 */
:deep(.el-tabs__item) {
  color: #888;
}

:deep(.el-tabs__item.is-active) {
  color: #6366f1;
}

:deep(.el-tabs__active-bar) {
  background-color: #6366f1;
}
</style>

