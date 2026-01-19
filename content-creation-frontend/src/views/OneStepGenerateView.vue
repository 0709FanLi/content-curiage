<template>
  <div class="osg-page">
    <header class="osg-header">
      <div class="osg-header-left">
        <div class="osg-title">一步生成</div>
        <div class="osg-subtitle">对话式长视频生成（按设计复刻：三栏 + 底部横滑时间轴）</div>
      </div>
      <div class="osg-header-right">
        <el-button type="default" @click="goToInspiration">返回首页</el-button>
        <el-button v-if="projectId" type="primary" plain @click="openProject">打开项目</el-button>
        <el-button v-if="finalVideoUrl" type="success" plain @click="openFinal">成片</el-button>
      </div>
    </header>

    <main class="osg-main">
      <aside class="osg-left">
        <OneStepAssetsPanel :script="script" :keyframes="keyframes" :videos="sortedVideos" />
      </aside>

      <section class="osg-center">
        <OneStepCenterPanel
          :video-url="activeVideoUrl"
          :aspect-ratio="aspectRatio"
          :active-segment-id="activeSegmentId"
          @select-segment="selectSegmentById"
        />
      </section>

      <aside class="osg-right">
        <OneStepChatPanel
          :run-id="runId"
          :inspiration="inspiration"
          :total-duration-sec="totalDurationSec"
          :segment-duration-sec="segmentDurationSec"
          :aspect-ratio="aspectRatio"
          :enable-storyboard="enableStoryboard"
          :creating="creating"
          :run-status="runStatus"
          :events="events"
          :keyframes="keyframes"
          :videos="sortedVideos"
          :final-video-url="finalVideoUrl"
          @create="handleCreateRun"
          @command="sendCommand"
        />
      </aside>
    </main>

    <footer class="osg-footer">
      <OneStepTimeline
        :videos="sortedVideos"
        :keyframes="keyframes"
        :active-video-id="activeVideoId"
        :missing-storyboard-segments="missingStoryboardSegments"
        @select-video="selectVideo"
      />
    </footer>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { stepGenerateApi } from '@/api'
import type { VideoSegment } from '@/types'
import OneStepAssetsPanel from '@/components/one-step/OneStepAssetsPanel.vue'
import OneStepCenterPanel from '@/components/one-step/OneStepCenterPanel.vue'
import OneStepChatPanel from '@/components/one-step/OneStepChatPanel.vue'
import OneStepTimeline from '@/components/one-step/OneStepTimeline.vue'
import { useStepRunSse } from '@/composables/useStepRunSse'
import { useStepRunSnapshot } from '@/composables/useStepRunSnapshot'

const router = useRouter()
const route = useRoute()

// create/run state
const inspiration = ref('')
const totalDurationSec = ref(20)
const segmentDurationSec = ref(4)
const aspectRatio = ref<'16:9' | '9:16'>('16:9')
const enableStoryboard = ref(true)

const creating = ref(false)
const runId = ref<number | null>(null)
const projectId = ref<number | null>(null)
const scriptId = ref<number | null>(null)

const runStatus = ref<string>('') // 来自 snapshot.run
const currentStep = ref<number>(0) // 来自 snapshot.run
const finalVideoUrl = ref<string>('') // 来自 snapshot.run

// SSE events
const { events, start: startSse, stop: stopSse } = useStepRunSse({ runId: () => runId.value })

// snapshot resources：逐步生成的产物由后端聚合返回，前端只轮询一个接口
const pollingEnabled = computed(() => (runStatus.value || '').toLowerCase() === 'running')
const { run: snapshotRun, script, keyframes, sortedVideos, refresh: refreshSnapshot } = useStepRunSnapshot({
  runId: () => runId.value,
  pollingEnabled: () => pollingEnabled.value
})

// selection
const activeVideoId = ref<number | null>(null)
const activeSegmentId = ref<string>('')

const activeVideo = computed<VideoSegment | null>(() => {
  if (!activeVideoId.value) return null
  return sortedVideos.value.find(v => v.id === activeVideoId.value) || null
})

const activeVideoUrl = computed(() => {
  const v = activeVideo.value
  return v?.status === 'completed' ? (v.videoUrl || '') : ''
})

const missingStoryboardSegments = computed(() => {
  const s = new Set<string>()
  for (const e of events.value) {
    const arr = e?.data?.missing_storyboard_segments
    if (Array.isArray(arr)) for (const x of arr) s.add(String(x))
  }
  return Array.from(s)
})

function goToInspiration() {
  router.push({ name: 'InspirationInput' })
}
function openProject() {
  if (!projectId.value) return
  router.push({ path: `/project/${projectId.value}/script` })
}
function openFinal() {
  if (!finalVideoUrl.value) return
  window.open(finalVideoUrl.value, '_blank', 'noreferrer')
}

function selectVideo(id: number) {
  activeVideoId.value = id
  const v = sortedVideos.value.find(x => x.id === id)
  if (v) activeSegmentId.value = `segment_${v.segmentIndex ?? 0}`
}
function selectSegmentById(segmentId: string) {
  activeSegmentId.value = segmentId
  const idx = Number(String(segmentId).replace('segment_', ''))
  const v = sortedVideos.value.find(x => x.segmentIndex === idx)
  if (v) activeVideoId.value = v.id
}

function applySnapshotRun() {
  const r: any = snapshotRun.value
  if (!r) return
  runStatus.value = r.status || ''
  currentStep.value = Number(r.current_step || r.currentStep || 0)
  finalVideoUrl.value = r.final_video_url || r.finalVideoUrl || ''

  // 刷新恢复：把最初创意/配置也从 snapshot.run 回填，避免右侧对话气泡为空
  if (typeof r.inspiration === 'string') inspiration.value = r.inspiration
  if (typeof r.total_duration_sec === 'number') totalDurationSec.value = r.total_duration_sec
  if (typeof r.segment_duration_sec === 'number') segmentDurationSec.value = r.segment_duration_sec
  if (r.aspect_ratio === '9:16' || r.aspect_ratio === '16:9') aspectRatio.value = r.aspect_ratio
  if (typeof r.enable_storyboard === 'boolean') enableStoryboard.value = r.enable_storyboard
}

async function handleCreateRun(payload: {
  inspiration: string
  total: number
  seg: number
  ratio: '16:9' | '9:16'
  storyboard: boolean
}) {
  creating.value = true
  try {
    inspiration.value = payload.inspiration
    totalDurationSec.value = payload.total
    segmentDurationSec.value = payload.seg
    aspectRatio.value = payload.ratio
    enableStoryboard.value = payload.storyboard

    const resp = await stepGenerateApi.createRun({
      inspiration: payload.inspiration,
      total_duration_sec: payload.total,
      segment_duration_sec: payload.seg,
      aspect_ratio: payload.ratio,
      decision_model_primary: 'deepseek-chat',
      decision_model_fallback: 'gemini-3-pro',
      decision_thinking_level: 'low',
      style: '默认',
      enable_storyboard: payload.storyboard,
      enable_seedream_group: true,
      video_mode: 'auto'
    })

    runId.value = resp.run_id
    projectId.value = resp.project_id
    scriptId.value = resp.script_id
    ElMessage.success('任务已创建，开始执行')

    startSse()
    await refreshSnapshot()
    applySnapshotRun()
  } catch (e: any) {
    ElMessage.error(e?.message || '创建失败')
  } finally {
    creating.value = false
  }
}

async function sendCommand(message: string) {
  if (!runId.value) return
  try {
    await stepGenerateApi.command(runId.value, message)
    ElMessage.success('已发送')
  } catch (e: any) {
    ElMessage.error(e?.message || '发送失败')
  }
}

// default selection when videos arrive
watch(
  () => sortedVideos.value.map(v => v.id).join(','),
  () => {
    if (!activeVideoId.value && sortedVideos.value.length) {
      selectVideo(sortedVideos.value[0].id)
    }
  }
)

onMounted(() => {
  try {
    const q = router.currentRoute.value.query as any
    if (typeof q?.inspiration === 'string' && q.inspiration.trim()) inspiration.value = q.inspiration.trim()
    if (typeof q?.totalDuration === 'string') totalDurationSec.value = Number(q.totalDuration) || totalDurationSec.value
    if (typeof q?.segmentDuration === 'string') segmentDurationSec.value = Number(q.segmentDuration) || segmentDurationSec.value
    if (q?.aspectRatio === '9:16' || q?.aspectRatio === '16:9') aspectRatio.value = q.aspectRatio
  } catch {
    // ignore
  }

  // snapshot 自带 runStatus/currentStep/finalVideoUrl，因此不再单独轮询 /runs/{id}
})

async function restoreLatestRunFromProject() {
  const pidRaw = (route.params as any)?.projectId
  const pid = pidRaw ? Number(pidRaw) : NaN
  if (!Number.isFinite(pid) || pid <= 0) return

  // 若 URL 已携带 runId，则优先使用
  const q = route.query as any
  const qRunId = q?.runId ? Number(q.runId) : NaN
  if (Number.isFinite(qRunId) && qRunId > 0) {
    runId.value = qRunId
    projectId.value = pid
    startSse()
    await refreshSnapshot()
    applySnapshotRun()
    return
  }

  // 否则按 project_id 找到最新 run
  try {
    const resp = await stepGenerateApi.getLatestRunByProject(pid)
    const latestRunId = Number((resp as any)?.run_id || (resp as any)?.runId || 0)
    if (!latestRunId) return
    runId.value = latestRunId
    projectId.value = pid
    startSse()
    await refreshSnapshot()
    applySnapshotRun()
  } catch (e) {
    // 不阻断页面，仅无法恢复
    console.warn('Failed to restore latest run:', e)
  }
}

watch(
  () => (route.params as any)?.projectId,
  () => {
    // 仅在“项目入口”路由使用恢复逻辑；/one-step 作为创建入口不自动恢复
    if (route.name === 'OneStepGenerateProject') {
      restoreLatestRunFromProject()
    }
  },
  { immediate: true }
)

onBeforeUnmount(() => {
  stopSse()
})

watch(
  () => snapshotRun.value,
  () => applySnapshotRun()
)
</script>

<style scoped>
.osg-page {
  /* 注意：外层 MainContent.content-area 是 fixed height + overflow:hidden
     所以这里必须用 100% 吃满容器高度，而不是 100vh（否则 footer 会被裁切）。 */
  height: 100%;
  min-height: 0;
  padding: 16px;
  background: #f5f6f8;
  display: grid;
  grid-template-rows: auto 1fr auto;
  gap: 16px;
  overflow: hidden;
}
.osg-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
}
.osg-title {
  font-size: 20px;
  font-weight: 700;
  color: #111827;
}
.osg-subtitle {
  margin-top: 6px;
  font-size: 12px;
  color: #6b7280;
}
.osg-main {
  display: grid;
  grid-template-columns: 320px minmax(560px, 1fr) 420px;
  gap: 16px;
  align-items: stretch;
  min-height: 0; /* allow children to scroll within the 1fr row */
}
.osg-left,
.osg-right {
  height: 100%;
  min-height: 0;
}
.osg-center {
  min-height: 0;
  /* 中间预览区不做内部滚动，避免鼠标滚轮触发“预览区上下滚动”的观感 */
  overflow: hidden;
}
.osg-footer {
  height: 220px;
}
@media (max-width: 1280px) {
  .osg-main {
    grid-template-columns: 1fr;
    grid-template-areas:
      'center'
      'left'
      'right';
  }
  .osg-left {
    grid-area: left;
  }
  .osg-center {
    grid-area: center;
  }
  .osg-right {
    grid-area: right;
  }
  .osg-footer {
    height: auto;
  }
}
</style>

