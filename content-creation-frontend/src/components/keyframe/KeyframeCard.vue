<template>
  <div class="keyframe-card">
    <!-- 时间段显示 -->
    <div class="time-range">
      {{ timeRange }}
    </div>

    <!-- 图片预览区域 -->
    <div class="image-section">
      <div
        v-if="keyframe.imageUrl && keyframe.status === 'completed'"
        class="image-preview"
        @click="handleImageClick"
      >
        <img :src="keyframe.imageUrl" alt="关键帧图片" />
      </div>
      <div
        v-else-if="keyframe.status === 'generating'"
        class="image-placeholder generating"
      >
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>生成中...</span>
      </div>
      <div
        v-else-if="keyframe.status === 'failed'"
        class="image-placeholder failed"
      >
        <el-icon><Loading /></el-icon>
        <span>模型维护中</span>
        <p class="error-message">
          请稍后重试
        </p>
      </div>
      <div v-else class="image-placeholder">
        <el-icon><Picture /></el-icon>
        <span>等待生成</span>
      </div>

      <!-- 隐藏的文件输入 -->
      <input
        ref="fileInputRef"
        type="file"
        accept="image/*"
        style="display: none"
        @change="handleFileChange"
      />
    </div>

    <!-- 提示词输入框 -->
    <div class="prompt-section">
      <label class="prompt-label">提示词：</label>
      <el-input
        v-model="promptText"
        type="textarea"
        :rows="2"
        placeholder="输入提示词..."
        @blur="handlePromptBlur"
      />
    </div>

    <!-- 操作按钮 -->
    <div class="actions">
      <el-button
        size="small"
        :disabled="keyframe.status === 'generating'"
        @click="handleRegenerate"
      >
        重新生成
      </el-button>
      <el-button
        size="small"
        type="primary"
        @click="handleImageClick"
      >
        重新上传
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElButton, ElInput, ElIcon } from 'element-plus'
import { Loading, Picture } from '@element-plus/icons-vue'
import type { Keyframe } from '@/types'

interface Props {
  keyframe: Keyframe
  projectModel?: string
  projectAspectRatio?: string
  projectQuality?: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  regenerate: [keyframeId: number]
  upload: [keyframeId: number, file: File]
  'update-prompt': [keyframeId: number, prompt: string]
}>()

const fileInputRef = ref<HTMLInputElement>()
const promptText = ref<string>(props.keyframe.prompt || '')

// 计算时间段显示
const timeRange = computed(() => {
  // 从segmentId中提取时间段信息
  // segmentId格式: segment_0, segment_0_first_frame
  const segmentId = props.keyframe.segmentId
  
  if (segmentId.includes('_first_frame')) {
    return '历史首帧（兼容）'
  }
  
  // 尝试从segmentId提取索引
  const match = segmentId.match(/segment_(\d+)/)
  if (match) {
    return `段落 ${parseInt(match[1]) + 1}`
  }
  
  return segmentId
})

// 监听keyframe变化，更新提示词
watch(
  () => props.keyframe.prompt,
  (newPrompt) => {
    if (newPrompt !== promptText.value) {
      promptText.value = newPrompt || ''
    }
  }
)

// 处理图片点击（上传）
const handleImageClick = () => {
  fileInputRef.value?.click()
}

// 处理文件选择
const handleFileChange = (event: Event) => {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  
  if (file) {
    emit('upload', props.keyframe.id, file)
    // 清空input，以便可以重复选择同一文件
    target.value = ''
  }
}

// 处理提示词失焦
const handlePromptBlur = () => {
  if (promptText.value !== props.keyframe.prompt) {
    emit('update-prompt', props.keyframe.id, promptText.value)
  }
}

// 处理重新生成
const handleRegenerate = () => {
  emit('regenerate', props.keyframe.id)
}
</script>

<style scoped>
.keyframe-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.time-range {
  font-family: 'PingFangSC-Regular', 'PingFang SC', sans-serif;
  font-size: 14px;
  font-weight: 500;
  color: #00aaaa;
}

.image-section {
  width: 100%;
  aspect-ratio: 16 / 9;
  border-radius: 8px;
  overflow: hidden;
  background-color: #2a2a2a;
  position: relative;
}

.image-preview {
  width: 100%;
  height: 100%;
  cursor: pointer;
  transition: opacity 0.3s;
}

.image-preview:hover {
  opacity: 0.8;
}

.image-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.image-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #999999;
  font-family: 'PingFangSC-Regular', 'PingFang SC', sans-serif;
  font-size: 14px;
}

.image-placeholder.generating {
  color: #00aaaa;
}

.image-placeholder.failed {
  color: #ff6b6b;
}

.error-message {
  font-size: 12px;
  color: #ff6b6b;
  margin-top: 4px;
  text-align: center;
  max-width: 80%;
}

.prompt-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.prompt-label {
  font-family: 'PingFangSC-Regular', 'PingFang SC', sans-serif;
  font-size: 12px;
  color: #999999;
}

.prompt-section :deep(.el-textarea__inner) {
  background-color: #ffffff;
  border: 1px solid #d9d9d9;
  border-radius: 4px;
  font-family: 'PingFangSC-Regular', 'PingFang SC', sans-serif;
  font-size: 14px;
  color: #333333;
}

.actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

.actions .el-button {
  font-family: 'PingFangSC-Regular', 'PingFang SC', sans-serif;
  font-size: 12px;
}

.actions .el-button--small {
  height: 28px;
  padding: 0 12px;
}
</style>

