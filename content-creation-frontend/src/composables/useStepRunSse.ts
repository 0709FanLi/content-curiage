import { computed, onBeforeUnmount, ref } from 'vue'
import { stepGenerateApi } from '@/api'

export type StepRunEvent = {
  id: number
  level: string
  event_type: string
  message: string
  data?: any
  created_at?: string
}

export function useStepRunSse(params: { runId: () => number | null }) {
  const events = ref<StepRunEvent[]>([])
  const lastEventId = ref(0)
  const connecting = ref(false)
  let abortController: AbortController | null = null

  const hasRun = computed(() => !!params.runId())

  function stop() {
    abortController?.abort()
    abortController = null
    connecting.value = false
  }

  async function start() {
    const runId = params.runId()
    if (!runId) return

    stop()
    connecting.value = true
    abortController = new AbortController()

    const url = stepGenerateApi.eventsUrl(runId, lastEventId.value || 0)
    const token = localStorage.getItem('accessToken')

    try {
      const resp = await fetch(url, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        signal: abortController.signal
      })

      if (!resp.ok || !resp.body) {
        connecting.value = false
        return
      }

      const reader = resp.body.getReader()
      const decoder = new TextDecoder('utf-8')
      let buffer = ''

      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        // SSE frame ends with \n\n
        const parts = buffer.split('\n\n')
        buffer = parts.pop() || ''

        for (const raw of parts) {
          const lines = raw.split('\n')
          const eventLine = lines.find(l => l.startsWith('event:')) || ''
          const dataLine = lines.find(l => l.startsWith('data:')) || ''
          const eventType = eventLine.replace('event:', '').trim()
          const dataStr = dataLine.replace('data:', '').trim()

          if (eventType === 'ping' || !dataStr) continue
          if (eventType !== 'message') continue

          try {
            const payload: StepRunEvent = JSON.parse(dataStr)
            events.value.push(payload)
            lastEventId.value = Math.max(lastEventId.value, payload.id || 0)
          } catch {
            // ignore malformed event
          }
        }
      }
    } catch {
      // ignore
    } finally {
      connecting.value = false
    }
  }

  onBeforeUnmount(() => stop())

  return {
    events,
    lastEventId,
    connecting,
    hasRun,
    start,
    stop
  }
}

