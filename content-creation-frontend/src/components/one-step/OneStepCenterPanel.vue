<template>
  <div class="os-center">
    <div class="os-preview">
      <div class="os-preview-stage">
        <div class="os-preview-inner" :class="{ portrait: aspectRatio === '9:16' }">
          <div v-if="!videoUrl" class="os-preview-empty">
            <div class="os-preview-icon">▶</div>
            <div class="os-preview-text">预览区域</div>
          </div>
          <video
            v-else
            ref="videoRef"
            class="os-video"
            :src="videoUrl"
            controls
            preload="metadata"
            playsinline
          />
        </div>
      </div>

      <div class="os-preview-meta">
        <div class="os-pill">{{ aspectRatio }}</div>
        <div class="os-muted">{{ videoUrl ? '可播放预览' : '等待视频生成…' }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

defineEmits<{
  (e: 'selectSegment', segmentId: string): void
}>()

const props = defineProps<{
  videoUrl: string
  aspectRatio: '16:9' | '9:16'
  activeSegmentId: string
}>()

const videoRef = ref<HTMLVideoElement | null>(null)
</script>

<style scoped>
.os-center {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 560px;
  height: 100%;
  min-height: 0;
}
.os-preview {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}
.os-preview-stage {
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.os-preview-inner {
  /* 关键：不滚动情况下，预览区要“自适应缩放”到可视高度
     这里用 height:100% 约束高度，再由 aspect-ratio 推导宽度（width:auto）。 */
  height: 100%;
  width: auto;
  max-width: 100%;
  aspect-ratio: 16 / 9;
  background: #0b0f1a;
  border-radius: 16px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}
.os-preview-inner.portrait {
  aspect-ratio: 9 / 16;
}
.os-video {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: #0b0f1a;
}
.os-preview-empty {
  color: #9ca3af;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}
.os-preview-icon {
  width: 44px;
  height: 44px;
  border-radius: 999px;
  border: 1px solid #374151;
  display: flex;
  align-items: center;
  justify-content: center;
}
.os-preview-meta {
  margin-top: 10px;
  display: flex;
  align-items: center;
  gap: 10px;
}
.os-pill {
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid #e5e7eb;
  background: #f9fafb;
  font-size: 12px;
  color: #111827;
}
.os-muted {
  color: #6b7280;
  font-size: 12px;
}
</style>

