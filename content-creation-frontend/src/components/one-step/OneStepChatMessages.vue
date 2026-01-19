<template>
  <div class="os-msgs">
    <div class="os-bubble user">
      <div class="os-bubble-text">{{ inspiration }}</div>
      <div class="os-bubble-meta">
        <span class="os-chip">{{ totalDurationSec }}s</span>
        <span class="os-chip">{{ aspectRatio }}</span>
      </div>
    </div>

    <div class="os-bubble assistant">
      <div class="os-bubble-text">
        <div class="os-agent-title">Agent 状态</div>
        <div class="os-agent-line">{{ assistantSummary }}</div>
        <div class="os-agent-adv">
          <div class="os-agent-adv-title">Agent 优势（自动化）</div>
          <ul class="os-agent-adv-list">
            <li>按段智能判定 I2V/T2V；缺图自动降级为 T2V</li>
            <li>全链路打点（脚本/分镜/视频/导出），可回溯</li>
            <li>失败后可补救：导出成片、重试、按时间点重生成</li>
          </ul>
        </div>
      </div>
    </div>

    <div v-if="todos.length" class="os-card">
      <div class="os-card-title">进度</div>
      <div class="os-todos">
        <div v-for="t in todos" :key="t.key" class="os-todo">
          <span class="os-todo-dot" :class="t.status" />
          <span class="os-todo-text">{{ t.label }}</span>
        </div>
      </div>
    </div>

    <div v-for="m in timelineMessages" :key="m.key" class="os-bubble" :class="m.role">
      <div class="os-bubble-text">
        <div class="os-meta-line">
          <span class="os-meta-pill" :class="m.level">{{ m.level }}</span>
          <span class="os-meta-type">{{ m.eventType }}</span>
        </div>
        <div class="os-msg-line">{{ m.text }}</div>

        <div v-if="m.attachments?.length" class="os-attach">
          <div class="os-attach-grid">
            <button
              v-for="a in m.attachments"
              :key="a.key"
              type="button"
              class="os-attach-item"
              @click="openUrl(a.openUrl)"
            >
              <img v-if="a.thumbUrl" class="os-attach-img" :src="a.thumbUrl" alt="" />
              <div v-else class="os-attach-skel" />
              <div class="os-attach-badge" v-if="a.badge">{{ a.badge }}</div>
            </button>
          </div>
        </div>

        <div v-if="m.agentDecision" class="os-decision">
          <div class="os-decision-title">决策</div>
          <div class="os-decision-row">I2V：{{ m.agentDecision.i2vCount }} 段；T2V：{{ m.agentDecision.t2vCount }} 段</div>
          <div v-if="m.agentDecision.missing?.length" class="os-decision-row os-muted">
            缺图降级 T2V：{{ m.agentDecision.missing.join('、') }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Keyframe, VideoSegment } from '@/types'
import type { StepRunEvent } from '@/composables/useStepRunSse'

type TodoItem = { key: string; label: string; status: 'running' | 'done' | 'todo' | 'error' }
type Attachment = { key: string; thumbUrl?: string; openUrl?: string; badge?: string }
type TimelineMessage = {
  key: string
  role: 'assistant' | 'user'
  level: 'info' | 'warning' | 'error'
  eventType: string
  text: string
  attachments?: Attachment[]
  agentDecision?: { i2vCount: number; t2vCount: number; missing?: string[] }
}

const props = defineProps<{
  inspiration: string
  totalDurationSec: number
  aspectRatio: '16:9' | '9:16'
  runStatus: string
  events: StepRunEvent[]
  keyframes: Keyframe[]
  videos: VideoSegment[]
  finalVideoUrl?: string
}>()

const assistantSummary = computed(() => {
  const st = (props.runStatus || '').toLowerCase()
  if (!st) return '已创建任务。'
  if (st === 'running') return '我正在执行分镜/配音/视频生成与拼接，请稍候。'
  if (st === 'completed') return '已完成！你可以对话式提出修改指令。'
  if (st === 'failed') return '任务失败了（可补救导出/重试/按时间点重生成）。'
  return `当前状态：${props.runStatus}`
})

const todos = computed<TodoItem[]>(() => {
  const types = new Set(props.events.map(e => e.event_type))
  return [
    { key: 'script', label: '生成脚本与分段', status: types.has('step_done') ? 'done' : types.has('step_start') ? 'running' : 'todo' },
    { key: 'storyboard', label: '生成智能分镜首帧', status: types.has('storyboard_done') ? 'done' : types.has('storyboard_failed') ? 'error' : types.has('storyboard_start') ? 'running' : 'todo' },
    { key: 'video', label: '生成视频片段', status: types.has('videos_done') ? 'done' : types.has('videos_started') ? 'running' : 'todo' },
    { key: 'export', label: '导出拼接成片', status: types.has('run_completed') || types.has('export_done') ? 'done' : types.has('wait_videos') || types.has('export_start') ? 'running' : types.has('export_failed') ? 'error' : 'todo' }
  ]
})

function segIdFromIndex(idx: number) {
  return `segment_${idx}`
}

function keyframeThumbForSegmentId(segmentId: string) {
  const kf = props.keyframes?.find(k => k.segmentId === segmentId)
  return kf?.imageUrl
}

function videoThumbForIndex(idx: number) {
  const v = props.videos?.find(x => (x.segmentIndex ?? -1) === idx)
  return v?.firstFrameUrl || keyframeThumbForSegmentId(segIdFromIndex(idx))
}

function openUrl(url?: string) {
  if (!url) return
  window.open(url, '_blank', 'noreferrer')
}

const timelineMessages = computed<TimelineMessage[]>(() => {
  const out: TimelineMessage[] = []
  for (const e of props.events || []) {
    const level = ((e.level || 'info') as any) as 'info' | 'warning' | 'error'
    const t = String(e.event_type || '')
    const text = String(e.message || '')

    const msg: TimelineMessage = {
      key: String(e.id ?? `${t}-${text}`),
      role: 'assistant',
      level: level === 'error' ? 'error' : level === 'warning' ? 'warning' : 'info',
      eventType: t,
      text
    }

    // 关键节点展示缩略图：分镜/视频/成片
    if (t === 'storyboard_done') {
      const count = props.keyframes?.length || 0
      msg.attachments = Array.from({ length: count }).map((_, idx) => ({
        key: `kf-${idx}`,
        thumbUrl: keyframeThumbForSegmentId(segIdFromIndex(idx)),
        openUrl: keyframeThumbForSegmentId(segIdFromIndex(idx)),
        badge: '分镜'
      }))
    }

    if (t === 'videos_done' || t === 'videos_started' || t === 'video_mode') {
      const count = props.videos?.length || 0
      if (count) {
        msg.attachments = Array.from({ length: count }).map((_, idx) => {
          const v = props.videos?.find(x => (x.segmentIndex ?? -1) === idx)
          return {
            key: `v-${idx}`,
            thumbUrl: videoThumbForIndex(idx),
            openUrl: v?.videoUrl,
            badge: v?.videoUrl ? '视频' : '生成中'
          }
        })
      }
    }

    if (t === 'run_completed' || t === 'export_done') {
      const url = props.finalVideoUrl
      if (url) {
        msg.attachments = [{ key: 'final', thumbUrl: videoThumbForIndex(0), openUrl: url, badge: '成片' }]
      }
    }

    // Agent 决策：从 video_mode 的 data 里读出 i2v/t2v
    if (t === 'video_mode') {
      const i2v = Array.isArray((e as any)?.data?.i2v_segments) ? (e as any).data.i2v_segments : []
      const missing = Array.isArray((e as any)?.data?.missing_storyboard_segments)
        ? (e as any).data.missing_storyboard_segments
        : []
      const total = props.videos?.length || 0
      msg.agentDecision = { i2vCount: i2v.length, t2vCount: Math.max(0, total - i2v.length), missing }
    }

    out.push(msg)
  }
  return out
})
</script>

<style scoped>
.os-msgs {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding-right: 2px;
}
.os-bubble {
  border-radius: 16px;
  padding: 12px;
  margin-bottom: 10px;
  border: 1px solid #e5e7eb;
  background: #fff;
}
.os-bubble.user {
  background: #ede9fe;
  border-color: #e9d5ff;
}
.os-bubble.assistant {
  background: #f9fafb;
}
.os-bubble-text {
  font-size: 13px;
  color: #111827;
  line-height: 1.5;
  white-space: pre-wrap;
}
.os-bubble-meta {
  margin-top: 8px;
  display: flex;
  gap: 8px;
}
.os-chip {
  font-size: 12px;
  color: #6b7280;
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid rgba(229, 231, 235, 0.9);
  border-radius: 999px;
  padding: 2px 8px;
}
.os-agent-title {
  font-weight: 700;
  margin-bottom: 6px;
}
.os-agent-line {
  margin-bottom: 10px;
}
.os-agent-adv {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 10px;
}
.os-agent-adv-title {
  font-weight: 600;
  margin-bottom: 6px;
}
.os-agent-adv-list {
  margin: 0;
  padding-left: 16px;
  color: #111827;
}
.os-card {
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  padding: 12px;
  margin: 12px 0;
  background: #fff;
}
.os-card-title {
  font-weight: 600;
  margin-bottom: 8px;
  color: #111827;
}
.os-todos {
  display: flex;
  flex-direction: column;
}
.os-todo {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 6px 0;
}
.os-todo-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: #d1d5db;
}
.os-todo-dot.running {
  background: #60a5fa;
}
.os-todo-dot.done {
  background: #22c55e;
}
.os-todo-dot.error {
  background: #ef4444;
}
.os-todo-text {
  font-size: 12px;
  color: #111827;
}
.os-meta-line {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.os-meta-pill {
  font-size: 12px;
  padding: 1px 6px;
  border-radius: 999px;
  border: 1px solid rgba(229, 231, 235, 0.9);
  background: rgba(255, 255, 255, 0.6);
  color: #111827;
}
.os-meta-pill.info {
  background: rgba(34, 197, 94, 0.12);
  border-color: rgba(34, 197, 94, 0.25);
}
.os-meta-pill.warning {
  background: rgba(245, 158, 11, 0.12);
  border-color: rgba(245, 158, 11, 0.25);
}
.os-meta-pill.error {
  background: rgba(239, 68, 68, 0.12);
  border-color: rgba(239, 68, 68, 0.25);
}
.os-meta-type {
  font-size: 12px;
  color: #6b7280;
}
.os-msg-line {
  font-size: 13px;
  color: #111827;
}
.os-attach {
  margin-top: 10px;
}
.os-attach-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}
.os-attach-item {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  overflow: hidden;
  background: #f3f4f6;
  height: 76px;
  position: relative;
  padding: 0;
  cursor: pointer;
}
.os-attach-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.os-attach-skel {
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, #eee, #f8f8f8, #eee);
  background-size: 200% 100%;
  animation: shimmer 1.2s infinite;
}
.os-attach-badge {
  position: absolute;
  left: 8px;
  top: 8px;
  font-size: 12px;
  padding: 2px 6px;
  border-radius: 999px;
  background: rgba(17, 24, 39, 0.75);
  color: #fff;
}
.os-decision {
  margin-top: 10px;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 10px;
  background: #fff;
}
.os-decision-title {
  font-weight: 600;
  margin-bottom: 6px;
}
.os-decision-row {
  font-size: 12px;
  color: #111827;
  line-height: 1.5;
}
.os-muted {
  color: #6b7280;
}
@keyframes shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}
</style>

