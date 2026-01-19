<template>
  <div class="os-panel">
    <div class="os-panel-head">
      <div class="os-panel-title">Assets</div>
      <div class="os-panel-actions">
        <el-button text class="os-icon-btn" :icon="Filter" />
      </div>
    </div>

    <el-tabs v-model="activeTab" class="os-tabs">
      <el-tab-pane label="Media" name="media" />
      <el-tab-pane label="口播文案" name="audio" />
      <el-tab-pane label="Doc" name="doc" />
    </el-tabs>

    <div v-if="activeTab === 'media'" class="os-grid">
      <div v-for="item in mediaItems" :key="item.key" class="os-asset-card">
        <img v-if="item.thumbnail" class="os-asset-thumb" :src="item.thumbnail" alt="" />
        <div v-else class="os-asset-skeleton" />
        <div v-if="item.durationLabel" class="os-asset-duration">{{ item.durationLabel }}</div>
      </div>
      <div class="os-asset-add">
        <el-button circle :icon="Plus" />
      </div>
    </div>

    <div v-else-if="activeTab === 'audio'" class="os-audio">
      <div v-if="audioSegments.length" class="os-audio-list">
        <div v-for="seg in audioSegments" :key="seg.key" class="os-audio-row">
          <div class="os-audio-time">{{ fmt(seg.timeStart) }}</div>
          <div class="os-audio-text">{{ seg.text }}</div>
        </div>
      </div>
      <div v-else class="os-doc-placeholder">
        <div class="os-muted">口播文案生成中…</div>
      </div>
    </div>

    <div v-else class="os-doc-placeholder">
      <div class="os-muted">Doc 面板预留</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Filter, Plus } from '@element-plus/icons-vue'
import type { Keyframe, Script, VideoSegment } from '@/types'

const props = defineProps<{
  script: Script | null
  keyframes: Keyframe[]
  videos: VideoSegment[]
}>()

const activeTab = ref<'media' | 'audio' | 'doc'>('media')

const mediaItems = computed(() => {
  // 先展示：视频首帧（优先）+ keyframe fallback
  const items: Array<{ key: string; thumbnail?: string; durationLabel?: string }> = []
  for (const v of props.videos || []) {
    items.push({
      key: `v-${v.id}`,
      thumbnail: v.firstFrameUrl,
      durationLabel: v.duration ? `${Math.round(v.duration)}s` : undefined
    })
  }
  for (const k of props.keyframes || []) {
    items.push({
      key: `kf-${k.id}`,
      thumbnail: k.imageUrl
    })
  }
  return items.slice(0, 30)
})

const audioSegments = computed(() => {
  const s = props.script
  const arr = (s?.segments || []) as any[]
  const fallbackStep = Number((s as any)?.segmentDuration ?? (s as any)?.segment_duration ?? 4) || 4
  return arr.map((seg, idx) => {
    const timeStart = seg?.timeStart ?? seg?.time_start ?? idx * fallbackStep
    return {
      key: String(seg?.id ?? `seg-${idx}`),
      timeStart: Number(timeStart || 0),
      text: String(seg?.narration ?? seg?.content ?? '').trim()
    }
  }).filter(x => x.text)
})

function fmt(sec: number) {
  const s = Math.max(0, Math.floor(Number(sec || 0)))
  const mm = String(Math.floor(s / 60)).padStart(2, '0')
  const ss = String(s % 60).padStart(2, '0')
  return `${mm}:${ss}`
}
</script>

<style scoped>
.os-panel {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  overflow: hidden;
  height: 100%;
  display: flex;
  flex-direction: column;
}
.os-panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 12px 0 12px;
}
.os-panel-title {
  font-weight: 600;
  color: #111827;
}
.os-icon-btn {
  padding: 6px;
}
.os-tabs {
  padding: 0 12px;
}
.os-grid {
  padding: 12px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  overflow: auto;
}
.os-audio {
  padding: 12px;
  overflow: auto;
}
.os-audio-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.os-audio-row {
  display: grid;
  grid-template-columns: 56px 1fr;
  gap: 10px;
  padding: 10px;
  border-radius: 12px;
  border: 1px solid #eef2f7;
  background: #fff;
}
.os-audio-time {
  font-size: 12px;
  color: #6b7280;
  padding-top: 2px;
}
.os-audio-text {
  font-size: 13px;
  color: #111827;
  line-height: 1.5;
  white-space: pre-wrap;
}
.os-asset-card {
  position: relative;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid #eef2f7;
  background: #f3f4f6;
  height: 94px;
}
.os-asset-thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.os-asset-skeleton {
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, #eee, #f8f8f8, #eee);
  background-size: 200% 100%;
  animation: shimmer 1.2s infinite;
}
.os-asset-duration {
  position: absolute;
  right: 8px;
  bottom: 8px;
  padding: 2px 6px;
  font-size: 12px;
  color: #111827;
  background: rgba(255, 255, 255, 0.85);
  border-radius: 999px;
}
.os-asset-add {
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px dashed #d1d5db;
  border-radius: 12px;
  background: #fff;
  height: 94px;
}
.os-doc-placeholder {
  padding: 12px;
}
.os-muted {
  color: #6b7280;
  font-size: 12px;
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

