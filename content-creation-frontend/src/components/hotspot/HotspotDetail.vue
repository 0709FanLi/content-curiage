<template>
  <div class="hotspot-detail">
    <div class="detail-card">
      <!-- 标题栏 -->
      <div class="detail-header">
        <h3 class="detail-title">🔥 {{ hotspot.title }}</h3>
        <el-button
          type="default"
          size="small"
          :icon="Close"
          circle
          @click="handleClose"
        />
      </div>

      <!-- 加载状态 -->
      <div v-if="loading" class="detail-loading">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>正在分析热点策略...</span>
      </div>

      <!-- 详情内容 -->
      <div v-else-if="detail" class="detail-content">
        <!-- 科学支撑 (TRUST) -->
        <div class="detail-section">
          <div class="section-header">
            <div class="section-icon trust-icon">🔬</div>
            <div class="section-title">{{ detail.trust.title }}</div>
          </div>
          <div class="section-content">
            <div class="content-text">{{ detail.trust.content }}</div>
          </div>
        </div>

        <!-- 转化策略 (CONVERSION) -->
        <div class="detail-section">
          <div class="section-header">
            <div class="section-icon conversion-icon">💡</div>
            <div class="section-title">{{ detail.conversion.title }}</div>
          </div>
          <div class="section-content">
            <div class="content-text">{{ detail.conversion.content }}</div>
          </div>
        </div>

        <!-- 建议结构 (STRUCTURE) -->
        <div class="detail-section">
          <div class="section-header">
            <div class="section-icon structure-icon">📋</div>
            <div class="section-title">{{ detail.structure.title }}</div>
          </div>
          <div class="section-content">
            <div class="content-text">{{ detail.structure.content }}</div>
          </div>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div v-if="detail" class="detail-footer">
        <el-button
          type="primary"
          size="default"
          class="apply-button"
          @click="handleApply"
        >
          <el-icon><MagicStick /></el-icon>
          应用此策略，立即生成脚本
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Close, Loading, MagicStick } from '@element-plus/icons-vue'
import { hotspotApi } from '@/api'
import { useUIStore } from '@/stores/ui'

interface HotspotItem {
  title: string
  track: string
  source: string
  angle: string
}

interface HotspotDetail {
  title: string
  trust: {
    title: string
    content: string
    items?: string[]
  }
  conversion: {
    title: string
    content: string
    items?: string[]
  }
  structure: {
    title: string
    content: string
    items?: string[]
  }
  raw_content?: string
}

interface Props {
  hotspot: HotspotItem
}

const props = defineProps<Props>()

const emit = defineEmits<{
  apply: [content: string]
  close: []
}>()

const uiStore = useUIStore()

// 状态
const loading = ref(false)
const detail = ref<HotspotDetail | null>(null)

// 加载热点详情
const loadDetail = async () => {
  loading.value = true
  uiStore.setGlobalLoading(true)
  detail.value = null

  try {
    const response = await hotspotApi.getHotspotDetail(props.hotspot.title)
    detail.value = response
  } catch (err: any) {
    console.error('加载热点详情失败:', err)
    ElMessage.error(err.message || '加载热点详情失败，请重试')
  } finally {
    loading.value = false
    uiStore.setGlobalLoading(false)
  }
}

// 应用策略
const handleApply = () => {
  if (!detail.value) return

  // 构建完整的策略内容
  const content = `
# ${detail.value.title}

## ${detail.value.trust.title}
${detail.value.trust.content}

## ${detail.value.conversion.title}
${detail.value.conversion.content}

## ${detail.value.structure.title}
${detail.value.structure.content}
`.trim()

  emit('apply', content)
  ElMessage.success('策略已应用到输入框')
}

// 关闭详情
const handleClose = () => {
  emit('close')
}

// 监听 hotspot 变化，重新加载详情
// immediate: true 会在组件挂载时立即执行，所以不需要 onMounted
watch(() => props.hotspot, () => {
  loadDetail()
}, { immediate: true })
</script>

<style scoped>
.hotspot-detail {
  margin-bottom: 20px;
}

.detail-card {
  background-color: #ffffff;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.detail-header {
  padding: 16px 20px;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.detail-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #ffffff;
  flex: 1;
}

.detail-loading {
  padding: 40px 20px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 12px;
  color: #909399;
  font-size: 14px;
}

.detail-content {
  padding: 20px;
  max-height: 400px;
  overflow-y: auto;
}

.detail-section {
  margin-bottom: 24px;
}

.detail-section:last-child {
  margin-bottom: 0;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.section-icon {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  display: flex;
  justify-content: center;
  align-items: center;
  font-size: 18px;
}

.trust-icon {
  background-color: #e6f7ff;
}

.conversion-icon {
  background-color: #fff7e6;
}

.structure-icon {
  background-color: #f0f9ff;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.section-content {
  padding-left: 42px;
}

.content-text {
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
  margin-bottom: 8px;
  white-space: pre-wrap;
}

.content-list {
  margin: 8px 0 0 0;
  padding-left: 20px;
  list-style: disc;
}

.content-list li {
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
  margin-bottom: 6px;
}

.detail-footer {
  padding: 16px 20px;
  border-top: 1px solid #e4e7ed;
  background-color: #fafafa;
  display: flex;
  justify-content: flex-end;
}

.apply-button {
  background: linear-gradient(135deg, #00aaaa 0%, #008888 100%);
  border: none;
  color: #ffffff;
  font-size: 14px;
  font-weight: 500;
  height: 40px;
  padding: 0 24px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.apply-button:hover {
  background: linear-gradient(135deg, #009999 0%, #007777 100%);
}

/* 滚动条样式 */
.detail-content::-webkit-scrollbar {
  width: 6px;
}

.detail-content::-webkit-scrollbar-thumb {
  background-color: #dcdfe6;
  border-radius: 3px;
}

.detail-content::-webkit-scrollbar-thumb:hover {
  background-color: #c0c4cc;
}
</style>

