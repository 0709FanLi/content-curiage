import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { stepGenerateApi } from '@/api'
import type { Keyframe, Script, VideoSegment } from '@/types'

export function useStepRunSnapshot(params: {
  runId: () => number | null
  pollingEnabled: () => boolean
}) {
  const loading = ref(false)
  const inFlight = ref(false)

  const run = ref<any | null>(null)
  const script = ref<Script | null>(null)
  const stepSegments = ref<any[]>([])
  const keyframes = ref<Keyframe[]>([])
  const videos = ref<VideoSegment[]>([])

  const sortedVideos = computed(() =>
    [...videos.value].sort((a, b) => (a.segmentIndex ?? 0) - (b.segmentIndex ?? 0))
  )

  async function refresh() {
    const rid = params.runId()
    if (!rid) return
    if (inFlight.value) return
    inFlight.value = true
    loading.value = true
    try {
      const snap = await stepGenerateApi.getSnapshot(rid)
      // snap: { run, script, step_segments, keyframes, videos }
      run.value = snap?.run || null
      script.value = snap?.script ? ({ id: snap.script.id, content: snap.script.content, segments: snap.script.segments } as any) : null
      stepSegments.value = snap?.step_segments || []

      keyframes.value = (snap?.keyframes || []).map((k: any) => ({
        id: k.id,
        segmentId: k.segment_id,
        imageUrl: k.image_url,
        status: k.status,
        errorMessage: k.error_message
      }))

      videos.value = (snap?.videos || []).map((v: any) => ({
        id: v.id,
        scriptId: snap?.run?.script_id || 0,
        segmentIndex: v.segment_index,
        firstFrameUrl: v.first_frame_url,
        videoUrl: v.video_url,
        status: v.status,
        duration: Number(v.duration || 0),
        errorMessage: v.error_message,
        createdAt: '',
        updatedAt: ''
      }))
    } finally {
      loading.value = false
      inFlight.value = false
    }
  }

  let timer: number | null = null
  function stop() {
    if (timer) window.clearTimeout(timer)
    timer = null
  }

  async function loop() {
    stop()
    if (!params.pollingEnabled()) return
    await refresh()
    timer = window.setTimeout(() => loop(), 2500)
  }

  watch(
    () => params.runId(),
    () => {
      refresh()
      if (params.pollingEnabled()) loop()
    }
  )
  watch(
    () => params.pollingEnabled(),
    enabled => {
      if (!enabled) stop()
      else loop()
    }
  )

  onBeforeUnmount(() => stop())

  return {
    loading,
    run,
    script,
    stepSegments,
    keyframes,
    videos,
    sortedVideos,
    refresh
  }
}

