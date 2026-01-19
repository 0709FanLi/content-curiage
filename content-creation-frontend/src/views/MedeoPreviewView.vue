<template>
  <div class="medeo-preview">
    <header class="top">
      <div class="title">Medeo 预览</div>
      <div class="sub">无需操作：自动生成 → 自动渲染 → 自动展示成片</div>
    </header>

    <main class="main">
      <section class="player">
        <div class="stage">
          <div v-if="!videoUrl" class="empty">
            <div class="spin" />
            <div class="empty-title">{{ phaseTitle }}</div>
            <div class="empty-sub">{{ phaseDesc }}</div>
          </div>
          <video v-else class="video" :src="videoUrl" controls playsinline preload="metadata" />
        </div>
      </section>

      <aside class="side">
        <div class="card">
          <div class="card-title">状态</div>
          <div class="kv">
            <div class="k">Project</div>
            <div class="v">{{ projectId }}</div>
            <div class="k">chat_session_id</div>
            <div class="v mono">{{ chatSessionId || '—' }}</div>
            <div class="k">op_record_id</div>
            <div class="v mono">{{ opRecordId || '—' }}</div>
            <div class="k">last_task_status</div>
            <div class="v">{{ lastTaskStatus || '—' }}</div>
            <div class="k">render_status</div>
            <div class="v">{{ renderStatus || '—' }}</div>
          </div>
        </div>

        <div v-if="errorMessage" class="card danger">
          <div class="card-title">错误</div>
          <div class="err">{{ errorMessage }}</div>
          <div class="actions">
            <el-button size="small" @click="restart">重试</el-button>
          </div>
        </div>
      </aside>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { medeoApi } from '@/api'

const route = useRoute()
const projectId = Number((route.params as any)?.projectId || 0)

const chatSessionId = ref<string>('')
const opRecordId = ref<string>('')
const lastTaskStatus = ref<string>('')
const renderStatus = ref<string>('')
const videoUrl = ref<string>('')
const errorMessage = ref<string>('')

const phase = ref<'loading' | 'generating' | 'ready' | 'rendering' | 'done' | 'error'>('loading')

const phaseTitle = computed(() => {
  if (phase.value === 'loading') return '加载中…'
  if (phase.value === 'generating') return '正在生成内容…'
  if (phase.value === 'ready') return '生成完成（阶段摘要）'
  if (phase.value === 'rendering') return '正在渲染成片…'
  if (phase.value === 'error') return '生成失败'
  return '已完成'
})

const phaseDesc = computed(() => {
  if (phase.value === 'generating') return '你无需操作，页面会自动等待并进入渲染。'
  if (phase.value === 'ready') return '已拿到渲染任务ID，稍后将自动开始渲染…'
  if (phase.value === 'rendering') return '渲染完成后会自动展示视频。'
  if (phase.value === 'error') return '你可以点击右侧“重试”。'
  return ''
})

let stopped = false

function sleep(ms: number) {
  return new Promise(resolve => window.setTimeout(resolve, ms))
}

async function patch(data: any) {
  if (!projectId) return
  try {
    await medeoApi.patchProject(projectId, data)
  } catch {
    // ignore
  }
}

async function loadSnapshot() {
  const snap = await medeoApi.getProject(projectId)
  chatSessionId.value = String(snap?.chat_session_id || '')
  opRecordId.value = String(snap?.video_draft_op_record_id || '')
  lastTaskStatus.value = String(snap?.last_task_status || '')
  renderStatus.value = String(snap?.render_status || '')
  const full = String(snap?.render_full_url || '')
  if (full) {
    videoUrl.value = full
    phase.value = 'done'
  }
}

async function pollGenerateUntilOpRecord() {
  if (!chatSessionId.value) throw new Error('chat_session_id 缺失，无法轮询')
  phase.value = 'generating'
  while (!stopped) {
    const st = await medeoApi.getLastTaskStatus(chatSessionId.value)
    lastTaskStatus.value = String(st?.status || '')
    await patch({ last_task_status: lastTaskStatus.value })
    const op = String(st?.video_draft_op_record_id || '')
    if (op) {
      opRecordId.value = op
      await patch({ video_draft_op_record_id: op })
      return
    }
    await sleep(2000)
  }
}

async function ensureRenderJob() {
  if (!opRecordId.value) throw new Error('op_record_id 缺失，无法渲染')
  phase.value = 'rendering'
  const resp = await medeoApi.createRenderJob(opRecordId.value)
  renderStatus.value = String(resp?.status || 'started')
  await patch({ render_status: renderStatus.value })
}

async function pollRenderUntilDone() {
  if (!opRecordId.value) throw new Error('op_record_id 缺失，无法轮询渲染')
  phase.value = 'rendering'
  while (!stopped) {
    const resp = await medeoApi.queryRenderJob(opRecordId.value)
    renderStatus.value = String(resp?.status || '')
    const result = resp?.result || {}
    if (renderStatus.value === 'completed') {
      const full = String(result?.full_url || '')
      const url = String(result?.url || '')
      if (full) {
        videoUrl.value = full
        await patch({ render_status: 'completed', render_url: url, render_metadata: result?.metadata || null })
        phase.value = 'done'
        return
      }
    }
    if (renderStatus.value === 'failed') {
      const msg = String(result?.error?.message || 'render failed')
      throw new Error(msg)
    }
    await patch({ render_status: renderStatus.value })
    await sleep(2000)
  }
}

async function run() {
  errorMessage.value = ''
  try {
    if (!projectId) throw new Error('projectId 不合法')
    await loadSnapshot()
    if (videoUrl.value) return
    if (!opRecordId.value) {
      await pollGenerateUntilOpRecord()
    }
    // 生成阶段已完成：先展示一段“阶段摘要”，再自动开始渲染（用户无需操作）
    phase.value = 'ready'
    await sleep(3000)
    await ensureRenderJob()
    await pollRenderUntilDone()
  } catch (e: any) {
    const msg = String(e?.message || e || 'unknown error')
    errorMessage.value = msg
    phase.value = 'error'
    await patch({ last_error: msg })
    ElMessage.error(msg)
  }
}

function restart() {
  stopped = false
  run()
}

onMounted(() => run())
onBeforeUnmount(() => {
  stopped = true
})
</script>

<style scoped>
.medeo-preview {
  height: 100%;
  min-height: 0;
  padding: 16px;
  background: #f3f4f6;
  display: grid;
  grid-template-rows: auto 1fr;
  gap: 14px;
}
.top {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}
.title {
  font-size: 18px;
  font-weight: 800;
  color: #111827;
}
.sub {
  color: #6b7280;
  font-size: 12px;
}
.main {
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(560px, 1fr) 380px;
  gap: 14px;
}
.player {
  min-height: 0;
}
.stage {
  height: 100%;
  border-radius: 18px;
  border: 1px solid #e5e7eb;
  background: #0b0f1a;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}
.video {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: #0b0f1a;
}
.empty {
  color: #e5e7eb;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}
.spin {
  width: 26px;
  height: 26px;
  border-radius: 999px;
  border: 3px solid rgba(255, 255, 255, 0.25);
  border-top-color: rgba(255, 255, 255, 0.9);
  animation: spin 1s linear infinite;
}
.empty-title {
  font-weight: 700;
}
.empty-sub {
  color: rgba(229, 231, 235, 0.8);
  font-size: 12px;
}
.side {
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  padding: 12px;
}
.card.danger {
  border-color: rgba(239, 68, 68, 0.35);
  background: rgba(254, 242, 242, 0.7);
}
.card-title {
  font-weight: 700;
  color: #111827;
  margin-bottom: 10px;
}
.kv {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 10px;
  font-size: 12px;
}
.k {
  color: #6b7280;
}
.v {
  color: #111827;
}
.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  font-size: 11px;
}
.err {
  color: #991b1b;
  font-size: 12px;
  white-space: pre-wrap;
}
.actions {
  margin-top: 10px;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
@media (max-width: 1200px) {
  .main {
    grid-template-columns: 1fr;
  }
}
</style>

