<template>
  <div class="os-timeline">
    <div class="os-ruler">
      <div class="os-ruler-title">Timeline</div>
    </div>

    <div
      ref="railRef"
      class="os-rail"
      @mousedown="onMouseDown"
      @mouseleave="onMouseLeave"
      @mouseup="onMouseUp"
      @mousemove="onMouseMove"
    >
      <div class="os-rail-inner">
        <div
          v-for="v in videos"
          :key="v.id"
          class="os-card"
          :class="{ active: v.id === activeVideoId }"
          @click.stop="$emit('selectVideo', v.id)"
        >
          <img v-if="thumb(v)" class="os-card-img" :src="thumb(v)" alt="" />
          <div v-else class="os-card-skeleton" />

          <div class="os-card-meta">
            <div class="os-card-title">#{{ v.segmentIndex + 1 }}</div>
            <div class="os-card-sub">{{ Math.round(v.duration || 0) }}s</div>
          </div>

          <div v-if="missingSet.has(segId(v))" class="os-badge">T2V</div>
          <div v-else-if="v.status !== 'completed'" class="os-badge ghost">{{ v.status }}</div>
        </div>

        <div v-if="videos.length === 0" class="os-empty">
          暂无视频段（生成中…）
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Keyframe, VideoSegment } from '@/types'

defineEmits<{
  (e: 'selectVideo', videoId: number): void
}>()

const props = defineProps<{
  videos: VideoSegment[]
  keyframes: Keyframe[]
  activeVideoId: number | null
  missingStoryboardSegments: string[]
}>()

const missingSet = computed(() => new Set(props.missingStoryboardSegments || []))

function segId(v: VideoSegment) {
  return `segment_${v.segmentIndex ?? 0}`
}

function thumb(v: VideoSegment) {
  if (v.firstFrameUrl) return v.firstFrameUrl
  const kf = props.keyframes?.find(k => k.segmentId === segId(v))
  return kf?.imageUrl
}

// drag-to-scroll
const railRef = ref<HTMLDivElement | null>(null)
const isDown = ref(false)
const startX = ref(0)
const scrollLeft = ref(0)

function onMouseDown(e: MouseEvent) {
  if (!railRef.value) return
  isDown.value = true
  railRef.value.classList.add('dragging')
  startX.value = e.pageX - railRef.value.offsetLeft
  scrollLeft.value = railRef.value.scrollLeft
}
function onMouseLeave() {
  if (!railRef.value) return
  isDown.value = false
  railRef.value.classList.remove('dragging')
}
function onMouseUp() {
  if (!railRef.value) return
  isDown.value = false
  railRef.value.classList.remove('dragging')
}
function onMouseMove(e: MouseEvent) {
  if (!isDown.value || !railRef.value) return
  e.preventDefault()
  const x = e.pageX - railRef.value.offsetLeft
  const walk = (x - startX.value) * 1.2
  railRef.value.scrollLeft = scrollLeft.value - walk
}
</script>

<style scoped>
.os-timeline {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  overflow: hidden;
}
.os-ruler {
  padding: 10px 14px;
  border-bottom: 1px solid #f1f5f9;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.os-ruler-title {
  font-weight: 600;
  color: #111827;
}
.os-rail {
  overflow-x: auto;
  overflow-y: hidden;
  cursor: grab;
  padding: 12px 14px 14px 14px;
}
.os-rail.dragging {
  cursor: grabbing;
}
.os-rail-inner {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}
.os-card {
  width: 112px;
  height: 78px;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  background: #f3f4f6;
  overflow: hidden;
  position: relative;
  flex: 0 0 auto;
  cursor: pointer;
  transition: transform 0.12s ease, box-shadow 0.12s ease, border-color 0.12s ease;
}
.os-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.08);
}
.os-card.active {
  border-color: #7c3aed;
  box-shadow: 0 0 0 2px rgba(124, 58, 237, 0.18);
}
.os-card-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.os-card-skeleton {
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, #eee, #f8f8f8, #eee);
  background-size: 200% 100%;
  animation: shimmer 1.2s infinite;
}
.os-card-meta {
  position: absolute;
  left: 8px;
  bottom: 8px;
  right: 8px;
  display: flex;
  justify-content: space-between;
  gap: 8px;
  color: #111827;
  background: rgba(255, 255, 255, 0.85);
  border: 1px solid rgba(229, 231, 235, 0.9);
  border-radius: 10px;
  padding: 3px 6px;
  font-size: 12px;
}
.os-badge {
  position: absolute;
  top: 8px;
  left: 8px;
  padding: 2px 6px;
  border-radius: 999px;
  font-size: 12px;
  background: rgba(17, 24, 39, 0.85);
  color: #fff;
}
.os-badge.ghost {
  background: rgba(255, 255, 255, 0.85);
  color: #111827;
  border: 1px solid rgba(229, 231, 235, 0.9);
}
.os-empty {
  padding: 10px 0;
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

