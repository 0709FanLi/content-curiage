<template>
  <button
    type="button"
    class="rcp-card"
    :class="{ active: selected }"
    @click="$emit('open')"
    @mouseenter="hovered = true"
    @mouseleave="hovered = false"
  >
    <div class="rcp-media">
      <video
        v-if="recipe.highlightVideoUrl"
        ref="videoRef"
        class="rcp-video"
        :src="recipe.highlightVideoUrl"
        autoplay
        muted
        loop
        playsinline
        preload="auto"
        @loadedmetadata="tryPlay"
        @canplay="tryPlay"
      />
      <img v-else-if="recipe.thumbUrl" class="rcp-img" :src="recipe.thumbUrl" alt="" />
      <div v-else class="rcp-skel" />

      <div v-if="recipe.isNew" class="rcp-badge">New</div>
      <div v-if="selected" class="rcp-selected" aria-label="selected">✓</div>

      <div class="rcp-hover" :class="{ show: hovered }">
        <button class="rcp-cta" type="button" @click.stop="$emit('use')">
          Use this recipe ↗
        </button>
      </div>
    </div>

    <div class="rcp-name">{{ recipe.name }}</div>
  </button>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

export type MedeoRecipe = {
  id: string
  name: string
  thumbUrl?: string
  highlightVideoUrl?: string
  videoUrl?: string
  description?: string
  userPrompt?: string
  label?: string
  isNew?: boolean
}

defineProps<{
  recipe: MedeoRecipe
  selected: boolean
}>()

defineEmits<{
  (e: 'open'): void
  (e: 'use'): void
}>()

const hovered = ref(false)
const videoRef = ref<HTMLVideoElement | null>(null)
let observer: IntersectionObserver | null = null

function tryPlay(e: Event) {
  const el = e?.target as HTMLVideoElement | null
  if (!el) return
  // 强制设置关键属性，避免某些浏览器未能从 attribute 同步到 property
  try {
    el.muted = true
    ;(el as any).playsInline = true
    el.autoplay = true
    el.setAttribute('muted', '')
    el.setAttribute('playsinline', '')
  } catch {
    // ignore
  }
  try {
    const p = el.play()
    if (p && typeof (p as any).catch === 'function') {
      ;(p as any).catch(() => {})
    }
  } catch {
    // ignore
  }
}

function tryPlayRef() {
  const el = videoRef.value
  if (!el) return
  // 复用同一套逻辑
  tryPlay({ target: el } as any)
}

onMounted(() => {
  // 首次挂载主动尝试播放一次
  requestAnimationFrame(() => tryPlayRef())
  // 进入视口时再尝试一次（解决首个卡片偶发不播）
  if (videoRef.value && 'IntersectionObserver' in window) {
    observer = new IntersectionObserver(
      entries => {
        for (const en of entries) {
          if (en.isIntersecting && (en.intersectionRatio || 0) >= 0.5) {
            tryPlayRef()
          }
        }
      },
      { threshold: [0, 0.5, 1] }
    )
    observer.observe(videoRef.value)
  }
})

onBeforeUnmount(() => {
  try {
    observer?.disconnect()
  } catch {
    // ignore
  }
  observer = null
})
</script>

<style scoped>
.rcp-card {
  width: 168px;
  flex: 0 0 auto;
  text-align: left;
  border: 2px solid transparent;
  background: transparent;
  cursor: pointer;
}
.rcp-media {
  width: 168px;
  height: 168px;
  border-radius: 18px;
  overflow: hidden;
  background: #0b0f1a;
  position: relative;
}
.rcp-video,
.rcp-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.rcp-skel {
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, #111827, #1f2937, #111827);
  background-size: 200% 100%;
  animation: shimmer 1.2s infinite;
}
.rcp-badge {
  position: absolute;
  top: 10px;
  left: 10px;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 12px;
  background: rgba(255, 255, 255, 0.9);
  color: #111827;
}
.rcp-selected {
  position: absolute;
  top: 10px;
  right: 10px;
  width: 22px;
  height: 22px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 900;
  font-size: 12px;
  color: #ffffff;
  background: #22c55e;
  box-shadow: 0 10px 22px rgba(34, 197, 94, 0.35);
}
.rcp-card.active .rcp-media {
  outline: 3px solid rgba(124, 58, 237, 0.38);
}
.rcp-hover {
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, rgba(11, 15, 26, 0) 35%, rgba(11, 15, 26, 0.75) 100%);
  opacity: 0;
  transition: opacity 160ms ease;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  padding: 12px;
}
.rcp-hover.show {
  opacity: 1;
}
.rcp-cta {
  border: 1px solid rgba(255, 255, 255, 0.22);
  background: rgba(255, 255, 255, 0.14);
  color: #fff;
  padding: 8px 12px;
  border-radius: 999px;
  font-weight: 700;
  cursor: pointer;
  width: 100%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
  line-height: 1;
  font-size: 12px;
  padding: 7px 10px;
  width: auto;
  max-width: 100%;
}
.rcp-name {
  margin-top: 10px;
  font-weight: 700;
  color: #111827;
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

