<template>
  <CommonLoading :visible="global_loading_visible" :text="global_loading_text" />
  <aside class="sidebar">
    <div class="sidebar-top">
      <button class="start-btn" type="button" @click="goToStart">
        <img class="start-icon" :src="startIcon" alt="" />
        <span class="start-text">开始制作</span>
      </button>
    </div>

    <div class="sidebar-body">
      <div class="sidebar-scroll">
        <section class="panel">
          <button class="panel-header" type="button" @click="hotspotOpen = !hotspotOpen">
            <div class="panel-title">
              <img class="panel-title-icon" :src="startHotIcon" alt="" />
              <span class="panel-title-text">AI热点情报</span>
              <span class="panel-hot-tag">HOT</span>
            </div>
            <img
              class="panel-chevron"
              :src="hotspotOpen ? arrowTopIcon : arrowBottomIcon"
              alt=""
            />
          </button>

          <div v-if="hotspotOpen" class="panel-list">
            <button
              v-for="(item, idx) in hotspots"
              :key="item.title + idx"
              class="hotspot-card"
              type="button"
              :class="{ active: selectedHotspotTitle === item.title }"
              @click="selectHotspot(item.title)"
            >
              <div class="hotspot-card-title">
                <span class="hotspot-emoji">📰</span>
                <span class="hotspot-title">{{ item.title }}</span>
              </div>
              <div class="hotspot-tags">
                <span class="tag">{{ item.track }}</span>
                <span class="tag">{{ item.source }}</span>
              </div>
              <div class="hotspot-desc">{{ item.angle }}</div>
              <div class="hotspot-footnote">{{ item.source }}</div>
            </button>
          </div>
        </section>

        <section class="panel recent">
          <button class="panel-header" type="button" @click="recentOpen = !recentOpen">
            <div class="panel-title">
              <img class="panel-title-icon" :src="folderIcon" alt="" />
              <span class="panel-title-text">最近项目</span>
              <span class="panel-count">{{ recentProjects.length }}</span>
            </div>
            <img
              class="panel-chevron"
              :src="recentOpen ? arrowTopIcon : arrowBottomIcon"
              alt=""
            />
          </button>

          <div v-if="recentOpen" class="recent-list">
            <div
              v-for="p in recentProjects"
              :key="p.id"
              class="recent-card"
              :class="{ active: active_project_id === Number(p.id) }"
              role="button"
              tabindex="0"
              @click="openProject(p)"
              @keydown.enter.prevent="openProject(p)"
            >
              <button
                class="recent-delete"
                type="button"
                title="删除项目"
                :disabled="deletingProjectId === Number(p.id)"
                @click.stop="deleteProject(p)"
              >
                <el-icon><Delete /></el-icon>
              </button>
              <div class="recent-card-icon">
                <img :src="pageIcon" alt="" />
              </div>
              <div class="recent-card-main">
                <div class="recent-card-title">{{ p.name || '未命名项目' }}</div>
                <div class="recent-card-time">
                  {{ formatTime(p.firstScriptGeneratedAt || p.updatedAt) }}
                </div>
              </div>
            </div>
            <div v-if="recentProjects.length === 0" class="empty">暂无项目</div>
          </div>
        </section>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import dayjs from 'dayjs'
import { ElIcon, ElMessage, ElMessageBox } from 'element-plus'
import { Delete } from '@element-plus/icons-vue'
import { hotspotApi, projectApi, scriptApi } from '@/api'
import { useProjectStore } from '@/stores'
import CommonLoading from '@/components/common/CommonLoading.vue'

import folderIcon from '@/assets/icons/folder.png'
import pageIcon from '@/assets/icons/page.png'
import startIcon from '@/assets/icons/submit.png'
import startHotIcon from '@/assets/icons/star-hot.png'
import arrowTopIcon from '@/assets/icons/arrow-top.png'
import arrowBottomIcon from '@/assets/icons/arrow-bottom.png'

type HotspotItem = {
  title: string
  track: string
  source: string
  angle: string
}

const router = useRouter()
const route = useRoute()
const projectStore = useProjectStore()

const hotspotOpen = ref<boolean>(true)
const recentOpen = ref<boolean>(false)
const hotspots = ref<HotspotItem[]>([])
const deletingProjectId = ref<number | null>(null)
const global_loading_visible = ref(false)
const global_loading_text = ref('加载中...')
let open_project_seq = 0

const selectedHotspotTitle = computed(() => String(route.query.hotspot || ''))
const recentProjects = computed(() => projectStore.recentProjects || [])
const active_project_id = computed(() => {
  const from_route = (route.params as any)?.projectId
  const n = from_route ? Number(from_route) : Number.NaN
  if (!Number.isNaN(n) && n > 0) return n
  return Number((projectStore.currentProject as any)?.id || 0)
})

const goToStart = () => {
  router.push({ name: 'InspirationInput' })
}

const selectHotspot = async (title: string) => {
  await router.replace({
    name: 'InspirationInput',
    query: {
      ...route.query,
      hotspot: title
    }
  })
}

const loadHotspots = async () => {
  try {
    const resp = await hotspotApi.getHotspots()
    const list = resp.hotspots || []
    hotspots.value = list.slice(0, 3)
  } catch (e) {
    console.error('加载热点列表失败:', e)
  }
}

const loadRecentProjects = async () => {
  await projectStore.loadRecentProjects()
}

const formatTime = (dateString: string) => {
  const date = dayjs(dateString)
  const now = dayjs()
  const diff = now.diff(date, 'day')
  if (diff === 0) return `今天 ${date.format('HH:mm')}`
  if (diff === 1) return `昨天 ${date.format('HH:mm')}`
  if (diff < 7) return `${diff}天前`
  return date.format('MM-DD HH:mm')
}

const openProject = async (project: any) => {
  if (!project?.id) return

  // 先跳转（让用户有反馈），再加载数据并用通用 loading 覆盖页面
  global_loading_text.value = '正在加载项目...'
  global_loading_visible.value = true
  open_project_seq += 1
  const seq = open_project_seq

  // 先默认进入脚本页，让用户立刻看到跳转 + loading
  await router.push({
    name: 'ScriptGenerationStep',
    params: { projectId: project.id.toString() }
  })

  try {
    const fullProject = await projectApi.getProject(project.id)
    const projectData = fullProject as any

    if (
      projectData.scripts &&
      Array.isArray(projectData.scripts) &&
      projectData.scripts.length > 0
    ) {
      const sortedScripts = [...projectData.scripts].sort((a, b) => {
        const timeA = new Date(a.createdAt || a.created_at || 0).getTime()
        const timeB = new Date(b.createdAt || b.created_at || 0).getTime()
        return timeB - timeA
      })
      projectData.script = sortedScripts[0]
    }

    if (!projectData.status) {
      projectData.status = projectData.script ? 'script_generated' : 'draft'
    }

    projectStore.setCurrentProject(projectData)

    // 拉取脚本详情以拿到 exportedVideoUrl（项目详情接口不返回）
    try {
      const script_id = Number(projectData?.script?.id || 0)
      if (script_id && Number.isFinite(script_id)) {
        const script = await scriptApi.getScript(script_id)
        const exported_url = String((script as any)?.exportedVideoUrl || '').trim()
        projectStore.set_project_exported_video_url(Number(project.id), exported_url)
      }
    } catch (e) {
      // 不阻断打开项目，只影响 completed/save 判定
      console.warn('拉取脚本导出视频地址失败:', e)
    }

    await loadRecentProjects()

    // 一键生成项目应进入一键生成页，否则会被当作“分步生成”展示
    const mode = String(projectData?.generationMode || projectData?.generation_mode || '')
    if (mode === 'one_click') {
      await router.replace({
        name: 'OneClickGenerate',
        params: { projectId: project.id.toString() }
      })
    }

    if (seq === open_project_seq) {
      global_loading_visible.value = false
    }
  } catch (error) {
    console.error('加载项目详情失败:', error)
    if (seq === open_project_seq) {
      global_loading_visible.value = false
      ElMessage.error('加载项目详情失败')
    }
  }
}

const deleteProject = async (project: any) => {
  const id = Number(project?.id)
  if (!id) return
  if (deletingProjectId.value === id) return

  try {
    await ElMessageBox.confirm(
      `确定删除项目「${project?.name || '未命名项目'}」吗？删除后无法恢复。`,
      '确认删除',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
  } catch {
    return
  }

  try {
    deletingProjectId.value = id
    await projectApi.deleteProject(id)
    projectStore.removeProject(id)
    ElMessage.success('项目已删除')

    // 删除后刷新项目列表（按你的要求）
    await loadRecentProjects()

    // 如果当前正在查看被删除的项目，跳回创意页
    if (active_project_id.value === id) {
      projectStore.setCurrentProject(null)
      await router.replace({ name: 'InspirationInput' })
    }
  } catch (e: any) {
    console.error('删除项目失败:', e)
    ElMessage.error(e?.message || '删除项目失败，请重试')
  } finally {
    if (deletingProjectId.value === id) deletingProjectId.value = null
  }
}

onMounted(async () => {
  await loadRecentProjects()
  await loadHotspots()
})

watch(
  () => route.name,
  async () => {
    if (hotspots.value.length === 0) {
      await loadHotspots()
    }
  }
)
</script>

<style scoped>
.sidebar {
  width: 256px;
  flex: 0 0 256px;
  background: rgba(0, 211, 242, 0.07);
  border-right: 1px solid rgba(206, 250, 254, 0.2);
  display: flex;
  flex-direction: column;
  height: 100%;
}

.sidebar-top {
  height: 88px;
  padding: 18px 16px 0 16px;
  box-sizing: border-box;
}

.start-btn {
  width: 223px;
  height: 36px;
  border-radius: 8px;
  border: none;
  cursor: pointer;
  background: linear-gradient(180deg, #2b7fff 0%, #00b8db 100%);
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.start-icon {
  width: 16px;
  height: 16px;
}

.start-text {
  font-size: 14px;
  font-weight: 500;
}

.sidebar-body {
  flex: 1;
  overflow: hidden;
}

.sidebar-scroll {
  height: 100%;
  overflow: auto;
  padding: 0 16px 16px 16px;
  box-sizing: border-box;
}

.panel {
  margin-bottom: 16px;
}

.panel-header {
  width: 100%;
  border: none;
  background: transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 8px;
  border-radius: 10px;
}

.panel-header:hover {
  background: rgba(255, 255, 255, 0.5);
}

.panel-title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #4a5565;
  font-size: 14px;
  font-weight: 500;
}

.panel-title-icon {
  width: 16px;
  height: 16px;
}

.panel-hot-tag {
  font-size: 10px;
  font-weight: 600;
  color: #ca3500;
  background: #ffedd4;
  border: 1px solid #ffd6a7;
  padding: 2px 6px;
  border-radius: 999px;
}

.panel-count {
  font-size: 12px;
  color: #6a7282;
}

.panel-chevron {
  width: 16px;
  height: 16px;
  opacity: 0.7;
  transition: opacity 0.15s ease;
}

.panel-list,
.recent-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 8px;
}

.hotspot-card {
  text-align: left;
  border: 1px solid rgba(229, 231, 235, 0.5);
  background: rgba(255, 255, 255, 0.8);
  border-radius: 14px;
  padding: 12px;
  cursor: pointer;
}

.hotspot-card.active {
  border-color: rgba(43, 127, 255, 0.6);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.hotspot-card-title {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 14px;
  font-weight: 600;
  color: #101828;
}

.hotspot-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hotspot-tags {
  margin-top: 6px;
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.tag {
  font-size: 10px;
  color: #4a5565;
  background: #f3f4f6;
  border: 1px solid #e5e7eb;
  padding: 2px 6px;
  border-radius: 999px;
}

.hotspot-desc {
  margin-top: 6px;
  font-size: 12px;
  color: #4a5565;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hotspot-footnote {
  margin-top: 6px;
  font-size: 12px;
  color: #6a7282;
}

.recent-card {
  width: 100%;
  text-align: left;
  background: rgba(255, 255, 255, 0.8);
  border: 1px solid rgba(229, 231, 235, 0.5);
  border-radius: 14px;
  padding: 13px;
  cursor: pointer;
  display: flex;
  gap: 12px;
  position: relative;
}

.recent-card.active {
  border-color: rgba(43, 127, 255, 0.45);
  background: rgba(0, 184, 219, 0.08);
}

.recent-delete {
  position: absolute;
  top: 10px;
  right: 10px;
  width: 26px;
  height: 26px;
  border-radius: 8px;
  border: 1px solid rgba(229, 231, 235, 0.8);
  background: rgba(255, 255, 255, 0.9);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: #6a7282;
  opacity: 0;
  transition: opacity 0.15s ease, background 0.15s ease, border-color 0.15s ease,
    color 0.15s ease;
}

.recent-card:hover .recent-delete {
  opacity: 1;
}

.recent-delete:hover {
  background: rgba(255, 69, 0, 0.08);
  border-color: rgba(255, 69, 0, 0.35);
  color: #ff4500;
}

.recent-card-icon {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: rgba(0, 184, 219, 0.15);
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 32px;
}

.recent-card-icon img {
  width: 16px;
  height: 16px;
}

.recent-card-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.recent-card-title {
  font-size: 14px;
  font-weight: 500;
  color: #101828;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.recent-card-desc {
  font-size: 12px;
  color: #4a5565;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.recent-card-time {
  font-size: 12px;
  color: #6a7282;
}

.empty {
  padding: 10px 8px;
  font-size: 12px;
  color: #6a7282;
}
</style>

