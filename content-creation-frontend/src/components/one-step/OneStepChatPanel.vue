<template>
  <div class="os-chat">
    <div class="os-chat-head">
      <div class="os-chat-title">对话</div>
      <div class="os-chat-sub">一步生成 Agent（生成中不干预，完成后可指令修改）</div>
    </div>

    <div v-if="!runId" class="os-create">
      <el-form label-position="top" :disabled="creating">
        <el-form-item label="创意/需求描述">
          <el-input v-model="localInspiration" type="textarea" :rows="5" placeholder="例如：做一个关于XX的科普短视频…" />
        </el-form-item>

        <div class="os-grid">
          <el-form-item label="总时长（秒）">
            <el-input-number v-model="localTotal" :min="4" :max="3600" />
          </el-form-item>
          <el-form-item label="单段时长（秒）">
            <el-input-number v-model="localSeg" :min="1" :max="60" />
          </el-form-item>
          <el-form-item label="画幅">
            <el-select v-model="localRatio" style="width: 100%">
              <el-option label="16:9" value="16:9" />
              <el-option label="9:16" value="9:16" />
            </el-select>
          </el-form-item>
        </div>

        <div class="os-grid">
          <el-form-item label="智能分镜（多图一致性 + 首帧图生视频）">
            <el-switch v-model="localStoryboard" />
          </el-form-item>
        </div>

        <el-button
          type="primary"
          class="os-primary"
          :loading="creating"
          :disabled="!localInspiration.trim()"
          @click="submitCreate"
        >
          开始一步生成
        </el-button>
      </el-form>
    </div>

    <div v-else class="os-thread">
      <OneStepChatMessages
        :inspiration="inspiration"
        :total-duration-sec="totalDurationSec"
        :aspect-ratio="aspectRatio"
        :run-status="runStatus"
        :events="events"
        :keyframes="keyframes"
        :videos="videos"
        :final-video-url="finalVideoUrl"
      />

      <div class="os-input">
        <el-input
          v-model="command"
          placeholder="Ask me anything..."
          :disabled="!canChat"
          @keydown.enter.prevent="send"
        />
        <el-button :disabled="!canChat || !command.trim()" @click="send">发送</el-button>
      </div>
      <div v-if="!canChat" class="os-muted os-pad">
        运行中暂不支持干预；失败或完成后可输入如“重试 / 重新导出成片 / 第10s视频重新生成”。
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { StepRunEvent } from '@/composables/useStepRunSse'
import OneStepChatMessages from '@/components/one-step/OneStepChatMessages.vue'
import type { Keyframe, VideoSegment } from '@/types'

const props = defineProps<{
  runId: number | null
  inspiration: string
  totalDurationSec: number
  segmentDurationSec: number
  aspectRatio: '16:9' | '9:16'
  enableStoryboard: boolean
  creating: boolean
  runStatus: string
  events: StepRunEvent[]
  keyframes: Keyframe[]
  videos: VideoSegment[]
  finalVideoUrl?: string
}>()

const emit = defineEmits<{
  (e: 'create', payload: { inspiration: string; total: number; seg: number; ratio: '16:9' | '9:16'; storyboard: boolean }): void
  (e: 'command', message: string): void
}>()

const localInspiration = ref(props.inspiration)
const localTotal = ref(props.totalDurationSec)
const localSeg = ref(props.segmentDurationSec)
const localRatio = ref<'16:9' | '9:16'>(props.aspectRatio)
const localStoryboard = ref(props.enableStoryboard)

watch(
  () => props.inspiration,
  v => (localInspiration.value = v)
)

const command = ref('')

const canChat = computed(() => {
  const st = (props.runStatus || '').toLowerCase()
  return st === 'completed' || st === 'failed' || st === 'cancelled'
})

function submitCreate() {
  emit('create', {
    inspiration: localInspiration.value.trim(),
    total: localTotal.value,
    seg: localSeg.value,
    ratio: localRatio.value,
    storyboard: localStoryboard.value
  })
}

function send() {
  if (!command.value.trim()) return
  emit('command', command.value.trim())
  command.value = ''
}
</script>

<style scoped>
.os-chat {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}
.os-chat-head {
  padding: 14px 14px 10px 14px;
  border-bottom: 1px solid #f1f5f9;
}
.os-chat-title {
  font-weight: 700;
  color: #111827;
}
.os-chat-sub {
  margin-top: 4px;
  font-size: 12px;
  color: #6b7280;
}
.os-create {
  padding: 14px;
  overflow: auto;
}
.os-thread {
  padding: 14px;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.os-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.os-primary {
  width: 100%;
  margin-top: 8px;
}
.os-input {
  margin-top: 12px;
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
  align-items: center;
}
.os-muted {
  color: #6b7280;
  font-size: 12px;
}
.os-pad {
  padding-top: 8px;
}
@media (max-width: 1200px) {
  .os-grid {
    grid-template-columns: 1fr;
  }
}
</style>

