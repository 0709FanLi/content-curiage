<template>
  <div class="hotspot-list">
    <div class="hotspot-header">
      <h3 class="header-title">今日AI热点情报</h3>
      <el-button
        type="default"
        size="small"
        :loading="loading"
        :icon="Refresh"
        class="refresh-button"
        @click="loadHotspots"
      >
        刷新
      </el-button>
    </div>

    <!-- 每日总结 -->
    <div v-if="dailySummary" class="daily-summary">
      <div class="summary-title">📅 今日趋势</div>
      <div class="summary-content">{{ dailySummary }}</div>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-container">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>加载热点中...</span>
    </div>

    <!-- 错误信息 -->
    <el-alert
      v-else-if="error"
      type="error"
      :closable="false"
      class="error-alert"
      :title="error"
      show-icon
    />

    <!-- 热点列表 -->
    <div v-else-if="hotspots.length > 0" class="hotspot-items" :class="{ locked: uiStore.globalLoading }">
      <div
        v-for="(hotspot, index) in hotspots"
        :key="index"
        class="hotspot-item"
        :class="{ active: selectedId === index }"
        @click="selectHotspot(index)"
      >
        <div class="hotspot-title">{{ hotspot.title }}</div>
        <div class="hotspot-meta">
          <span class="meta-track">{{ hotspot.track }}</span>
          <span class="meta-source">{{ hotspot.source }}</span>
        </div>
        <div class="hotspot-angle">{{ hotspot.angle }}</div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="empty-state">
      <el-empty description="暂无热点数据" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Loading } from '@element-plus/icons-vue'
import { hotspotApi } from '@/api'
import { useUIStore } from '@/stores/ui'

interface HotspotItem {
  title: string
  track: string
  source: string
  angle: string
}

interface Props {
  selectedId?: number | null
}

const props = withDefaults(defineProps<Props>(), {
  selectedId: null
})

const uiStore = useUIStore()

const emit = defineEmits<{
  select: [index: number, hotspot: HotspotItem]
}>()

// 状态
const loading = ref(false)
const error = ref('')
const dailySummary = ref('')
const hotspots = ref<HotspotItem[]>([])

// 加载热点列表
const loadHotspots = async () => {
  loading.value = true
  error.value = ''

  try {
    const response = await hotspotApi.getHotspots()
    dailySummary.value = response.daily_summary || ''
    hotspots.value = response.hotspots || []
    
    if (hotspots.value.length === 0) {
      ElMessage.warning('暂无热点数据')
    }
  } catch (err: any) {
    console.error('加载热点列表失败:', err)
    error.value = err.message || '加载热点列表失败，请重试'
    ElMessage.error(error.value)
  } finally {
    loading.value = false
  }
}

// 选择热点
const selectHotspot = (index: number) => {
  if (uiStore.globalLoading) {
    return
  }
  if (index === props.selectedId) {
    // 取消选中
    return
  }
  emit('select', index, hotspots.value[index])
}

// 初始化加载
onMounted(() => {
  loadHotspots()
})
</script>

<style scoped>
.hotspot-list {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: #ffffff;
  border-right: 1px solid #e4e7ed;
}

.hotspot-header {
  padding: 16px;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}

.header-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.refresh-button {
  height: 28px;
  padding: 0 12px;
  font-size: 12px;
}

.daily-summary {
  padding: 12px 16px;
  background-color: #f0f9ff;
  border-bottom: 1px solid #e4e7ed;
  flex-shrink: 0;
}

.summary-title {
  font-size: 13px;
  font-weight: 600;
  color: #409eff;
  margin-bottom: 6px;
}

.summary-content {
  font-size: 12px;
  color: #606266;
  line-height: 1.6;
}

.loading-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 12px;
  color: #909399;
  font-size: 14px;
}

.error-alert {
  margin: 16px;
}

.hotspot-items {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

.hotspot-items.locked {
  pointer-events: none;
  opacity: 0.75;
}

.hotspot-item {
  padding: 12px 16px;
  border-bottom: 1px solid #f0f0f0;
  cursor: pointer;
  transition: all 0.3s;
}

.hotspot-item:hover {
  background-color: #f5f7fa;
}

.hotspot-item.active {
  background-color: #e6f7ff;
  border-left: 3px solid #00aaaa;
  padding-left: 13px;
}

.hotspot-title {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
  margin-bottom: 8px;
  line-height: 1.4;
}

.hotspot-meta {
  display: flex;
  gap: 12px;
  margin-bottom: 6px;
}

.meta-track {
  font-size: 12px;
  color: #409eff;
  background-color: #ecf5ff;
  padding: 2px 8px;
  border-radius: 3px;
}

.meta-source {
  font-size: 12px;
  color: #67c23a;
  background-color: #f0f9ff;
  padding: 2px 8px;
  border-radius: 3px;
}

.hotspot-angle {
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
}

.empty-state {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
}

/* 滚动条样式 */
.hotspot-items::-webkit-scrollbar {
  width: 6px;
}

.hotspot-items::-webkit-scrollbar-thumb {
  background-color: #dcdfe6;
  border-radius: 3px;
}

.hotspot-items::-webkit-scrollbar-thumb:hover {
  background-color: #c0c4cc;
}
</style>

