import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { keyframeApi, scriptApi, videoApi } from '@/api'
import type { Keyframe, Script, VideoSegment } from '@/types'

export function useOneStepResources(params: {
  scriptId: () => number | null
  pollingEnabled: () => boolean
}) {
  const script = ref<Script | null>(null)
  const keyframes = ref<Keyframe[]>([])
  const videos = ref<VideoSegment[]>([])
  const loading = ref(false)

  const sortedVideos = computed(() =>
    [...videos.value].sort((a, b) => (a.segmentIndex ?? 0) - (b.segmentIndex ?? 0))
  )

  const keyframeBySegmentId = computed(() => {
    const map = new Map<string, Keyframe>()
    for (const kf of keyframes.value) {
      if (kf?.segmentId) map.set(kf.segmentId, kf)
    }
    return map
  })

  // 防止轮询叠加：同一时刻只允许一个 refreshAll 在飞行中
  const inFlight = ref(false)

  async function refreshAll() {
    const sid = params.scriptId()
    if (!sid) return
    if (inFlight.value) return
    inFlight.value = true
    loading.value = true
    try {
      const [s, kf, vd] = await Promise.all([
        scriptApi.getScript(sid),
        keyframeApi.getKeyframesByScript(sid),
        videoApi.getVideoSegmentsByScript(sid)
      ])
      script.value = s as any
      keyframes.value = (kf as any)?.keyframes || []
      videos.value = (vd as any)?.videoSegments || []
    } finally {
      loading.value = false
      inFlight.value = false
    }
  }

  let timer: number | null = null
  function stopPolling() {
    if (timer) window.clearTimeout(timer)
    timer = null
  }

  async function pollLoop() {
    stopPolling()
    const sid = params.scriptId()
    if (!sid) return
    if (!params.pollingEnabled()) return

    await refreshAll()
    // 递归 setTimeout：避免 setInterval 在慢请求时不断堆积
    timer = window.setTimeout(() => {
      pollLoop()
    }, 2500)
  }

  function startPolling() {
    stopPolling()
    timer = window.setTimeout(() => {
      pollLoop()
    }, 2500)
  }

  watch(
    () => params.scriptId(),
    () => {
      refreshAll()
      // 只有需要轮询时才启动，避免无意义请求
      if (params.pollingEnabled()) startPolling()
    },
    { immediate: true }
  )

  watch(
    () => params.pollingEnabled(),
    enabled => {
      if (!enabled) stopPolling()
      else startPolling()
    }
  )

  onBeforeUnmount(() => stopPolling())

  return {
    script,
    keyframes,
    videos,
    sortedVideos,
    keyframeBySegmentId,
    loading,
    refreshAll
  }
}

