<template>
  <div class="sidebar" :class="{ collapsed: sidebarCollapsed }">
    <!-- 顶部栏 -->
    <div class="sidebar-header">
      <div class="logo">
        <span v-if="!sidebarCollapsed">内容创作</span>
        <span v-else>创作</span>
      </div>
    </div>

    <!-- 创作工具区域 -->
    <div class="sidebar-section">
      <div class="section-title" v-if="!sidebarCollapsed">创作工具</div>
      <div class="tool-list">
        <div
          class="tool-item"
          :class="{ active: $route.name === 'InspirationInput' }"
          @click="navigateTo('inspiration')"
        >
          <div class="tool-item-title">开始创作</div>
          <div class="tool-item-desc">从热点灵感或主题开始，AI将为您生成脚本、分镜和完整视频</div>
        </div>
        <div
          v-if="showStudioEntry"
          class="tool-item studio-item"
          :class="{ active: $route.name === 'Studio' || $route.name === 'StudioProject' }"
          @click="navigateTo('studio')"
        >
          <div class="tool-item-title">
            <span class="studio-badge">NEW</span>
            AI 创作工作室
          </div>
          <div class="tool-item-desc">Medeo 风格的全新体验：AI对话 + 时间线编辑 + 一键导出</div>
        </div>
        <!-- 隐藏"从脚本开始"入口，统一使用"从灵感开始" -->
        <!-- <div
          class="tool-item"
          :class="{ active: $route.name === 'ScriptStart' }"
          @click="navigateTo('script-start')"
        >
          <div class="tool-item-title">开始创作</div>
          <div class="tool-item-desc">从完整脚本开始，让AI为您生成分镜和视觉内容</div>
        </div> -->
      </div>
    </div>

    <!-- 最近项目区域 -->
    <div class="sidebar-section recent-projects">
      <div class="section-title" v-if="!sidebarCollapsed">
        最近项目
      </div>
      <div class="project-list">
        <div
          v-for="project in recentProjects"
          :key="project.id"
          class="project-item"
          @click="openProject(project)"
        >
          <div class="project-info">
            <div 
              v-if="editingProjectId !== project.id"
              class="project-name"
              @dblclick.stop="startEditProjectName(project)"
              :title="project.name"
            >
              {{ truncateProjectName(project.name) }}
            </div>
            <el-input
              v-else
              v-model="editingProjectName"
              size="small"
              class="project-name-input"
              @blur="saveProjectName(project)"
              @keyup.enter="saveProjectName(project)"
              @keyup.esc="cancelEditProjectName"
              ref="projectNameInputRef"
            />
            <div class="project-time" v-if="!sidebarCollapsed && editingProjectId !== project.id">
              {{ formatTime(project.firstScriptGeneratedAt || project.updatedAt) }}
            </div>
          </div>
          <div class="project-actions" v-if="editingProjectId !== project.id">
            <el-button
              link
              size="small"
              @click.stop="deleteProject(project)"
              class="delete-btn"
            >
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
        </div>
        <div v-if="recentProjects.length === 0" class="no-projects">
          <span v-if="!sidebarCollapsed">暂无项目</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, nextTick, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox, ElMessage } from 'element-plus'
import { Delete } from '@element-plus/icons-vue'
import { useUIStore } from '@/stores'
import { useProjectStore } from '@/stores'
import { projectApi } from '@/api'
import type { Project } from '@/types'
import dayjs from 'dayjs'

const router = useRouter()
const uiStore = useUIStore()
const projectStore = useProjectStore()

const sidebarCollapsed = computed(() => uiStore.sidebarCollapsed)
const recentProjects = computed(() => projectStore.recentProjects)
const showStudioEntry = computed(
  () => (import.meta as any).env?.VITE_ENABLE_STUDIO === 'true'
)

// 加载最近项目列表
const loadRecentProjects = async () => {
  try {
    const response = await projectApi.getProjects({ page: 1, pageSize: 10 })
    const projects = response.items || []
    projectStore.setProjects(projects)
  } catch (error) {
    console.error('加载最近项目失败:', error)
  }
}

// 组件挂载时加载最近项目
onMounted(() => {
  loadRecentProjects()
})

// 项目名称编辑相关
const editingProjectId = ref<number | null>(null)
const editingProjectName = ref<string>('')
const projectNameInputRef = ref<any>(null)

// 截断项目名称，最多显示10个字
const truncateProjectName = (name: string): string => {
  if (!name) return '未命名项目'
  if (name.length > 10) {
    return name.substring(0, 10) + '...'
  }
  return name
}

// 开始编辑项目名称
const startEditProjectName = async (project: Project) => {
  editingProjectId.value = project.id
  editingProjectName.value = project.name
  await nextTick()
  // 聚焦输入框
  if (projectNameInputRef.value && projectNameInputRef.value.length > 0) {
    projectNameInputRef.value[0].focus()
    projectNameInputRef.value[0].select()
  }
}

// 保存项目名称
const saveProjectName = async (project: Project) => {
  if (!editingProjectName.value.trim()) {
    ElMessage.warning('项目名称不能为空')
    editingProjectName.value = project.name
    editingProjectId.value = null
    return
  }
  
  try {
    const newName = editingProjectName.value.trim()
    await projectApi.updateProject(project.id, { name: newName })
    projectStore.updateProject(project.id, { name: newName })
    
    // 更新最近项目列表
    const response = await projectApi.getProjects({ page: 1, pageSize: 10 })
    projectStore.setProjects(response.items || [])
    
    editingProjectId.value = null
    ElMessage.success('项目名称已更新')
  } catch (error) {
    console.error('更新项目名称失败:', error)
    ElMessage.error('更新项目名称失败')
    editingProjectName.value = project.name
    editingProjectId.value = null
  }
}

// 取消编辑项目名称
const cancelEditProjectName = () => {
  editingProjectId.value = null
  editingProjectName.value = ''
}

const navigateTo = (type: string) => {
  if (type === 'inspiration') {
    router.push({ name: 'InspirationInput' })
  } else if (type === 'script-start') {
    router.push({ name: 'ScriptStart' })
  } else if (type === 'studio') {
    router.push({ name: 'Studio' })
  }
}

const openProject = async (project: Project) => {
  try {
    
    // 检查是否已经在目标页面且项目相同，避免重复请求
    const currentRoute = router.currentRoute.value
    const currentProjectId = projectStore.currentProject?.id
    
    // 先获取项目详情以确定状态
    const fullProject = await projectApi.getProject(project.id)
    
    // 处理脚本数据：如果返回的是 scripts 数组，取最新的一个作为 script
    const projectData = fullProject as any
    if (projectData.scripts && Array.isArray(projectData.scripts) && projectData.scripts.length > 0) {
      // 按创建时间排序，取最新的脚本
      const sortedScripts = [...projectData.scripts].sort((a, b) => {
        const timeA = new Date(a.createdAt || a.created_at || 0).getTime()
        const timeB = new Date(b.createdAt || b.created_at || 0).getTime()
        return timeB - timeA // 降序，最新的在前
      })
      projectData.script = sortedScripts[0]
    }
    
    // 确保项目数据格式正确
    if (!projectData.status) {
      // 如果没有状态，根据是否有脚本来判断
      if (projectData.script) {
        projectData.status = 'script_generated'
      } else {
        projectData.status = 'draft'
      }
    }
    
    // 设置项目到 store，这样目标页面就不需要再次请求
    console.log('[Sidebar.openProject] 设置项目前:', {
      hasScript: !!projectData.script,
      scriptId: projectData.script?.id
    })
    
    projectStore.setCurrentProject(projectData)
    
    console.log('[Sidebar.openProject] 设置项目后:', {
      currentProjectId: projectStore.currentProject?.id,
      hasScript: !!projectStore.currentScript,
      scriptId: projectStore.currentScript?.id
    })

    // 项目详情获取成功后刷新最近项目列表，确保时间排序和状态最新
    await projectStore.loadRecentProjects()
    
    console.log('[Sidebar.openProject] 刷新项目列表后:', {
      currentProjectId: projectStore.currentProject?.id,
      hasScript: !!projectStore.currentScript,
      scriptId: projectStore.currentScript?.id
    })
    
    // 根据项目的生成模式和状态跳转到对应页面
    let targetRoute: string
    
    const mode = String(projectData?.generationMode || projectData?.generation_mode || '')

    // 如果是一键生成模式，始终跳转到一键生成页面
    if (mode === 'one_click') {
      targetRoute = 'OneClickGenerate'
    } else if (mode === 'one_step') {
      // 一步生成项目：进入一步生成页面（页面内按 projectId 自动恢复最新 run）
      targetRoute = 'OneStepGenerateProject'
    } else {
      // 分步生成模式，根据状态跳转
      switch (projectData.status) {
        case 'draft':
        case 'script_generated':
          targetRoute = 'ScriptGenerationStep'
          break
        case 'keyframes_generating':
        case 'keyframes_completed':
          targetRoute = 'KeyframeGeneration'
          break
        case 'video_generating':
        case 'completed':
          targetRoute = 'VideoGeneration'
          break
        default:
          targetRoute = 'InspirationInput'
      }
    }
    
    
    // 如果已经在目标页面且项目相同，不需要跳转
    if (currentRoute.name === targetRoute && currentProjectId === project.id) {
      console.log('[Sidebar.openProject] 已在目标页面且项目相同，不跳转')
      return
    }
    
    console.log('[Sidebar.openProject] 准备跳转:', {
      targetRoute,
      projectId: project.id,
      hasScript: !!projectData.script
    })
    
    // 跳转到目标路由，并传递项目ID作为参数
    // 即使路由相同，也通过改变参数来强制组件重新渲染
    await router.replace({ 
      name: targetRoute,
      params: { projectId: project.id.toString() }
    })
    
    // 等待路由跳转完成
    await nextTick()
    await new Promise(resolve => setTimeout(resolve, 100))
    
  } catch (error) {
    console.error('加载项目详情失败:', error)
    uiStore.showError('加载项目详情失败: ' + (error instanceof Error ? error.message : String(error)))
    
    // 如果加载失败，跳转到首页
    try {
      await router.push({ name: 'InspirationInput' })
    } catch (routerError) {
      console.error('跳转路由失败:', routerError)
    }
  }
}

const deleteProject = async (project: Project) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除项目"${project.name}"吗？此操作不可撤销。`,
      '确认删除',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    await projectApi.deleteProject(project.id)
    
    // 先从store中移除项目（立即更新UI）
    projectStore.removeProject(project.id)
    
    // 然后从后端重新获取项目列表，确保数据同步
    await loadRecentProjects()
    
    uiStore.showSuccess('项目已删除')
  } catch (error) {
    if (error !== 'cancel') {
      uiStore.showError('删除项目失败')
      // 如果删除失败，也刷新列表以确保数据一致性
      await loadRecentProjects()
    }
  }
}

const formatTime = (dateString: string) => {
  const date = dayjs(dateString)
  const now = dayjs()
  const diff = now.diff(date, 'day')

  if (diff === 0) {
    return `今天 ${date.format('HH:mm')}`
  } else if (diff === 1) {
    return `昨天 ${date.format('HH:mm')}`
  } else if (diff < 7) {
    return `${diff}天前`
  } else {
    return date.format('MM-DD HH:mm')
  }
}
</script>

<style scoped>
.sidebar {
  width: 214px;
  background-color: #555555;
  border: none;
  border-radius: 0;
  display: flex;
  flex-direction: column;
  transition: width 0.3s ease;
  flex-shrink: 0;
}

.sidebar.collapsed {
  width: 60px;
}

.sidebar-header {
  padding: 20px 14px;
  border-bottom: none;
}

.logo {
  font-family: 'PingFangSC-Regular', 'PingFang SC', sans-serif;
  font-size: 15px;
  font-weight: 400;
  color: #00aaaa;
}

.sidebar-section {
  padding: 14px;
  border-bottom: none;
}

.section-title {
  font-family: 'PingFangSC-Regular', 'PingFang SC', sans-serif;
  font-size: 15px;
  font-weight: 400;
  color: #00aaaa;
  margin-bottom: 12px;
  padding-left: 0;
}

.tool-list {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.tool-item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  padding: 14px 14px 14px 14px;
  border-radius: 0;
  cursor: pointer;
  transition: all 0.2s ease;
  color: #ffffff;
  background-color: transparent;
  position: relative;
  margin-bottom: 12px;
}

.tool-item:hover {
  background: transparent;
  color: #ffffff;
}

.tool-item.active {
  background-color: #6b8e8e;
  color: #ffffff;
  border-radius: 4px;
}

.tool-item.active::before {
  display: none;
}

.tool-item .el-icon {
  display: none;
}

.tool-item-title {
  font-family: 'PingFangSC-Regular', 'PingFang SC', sans-serif;
  font-size: 14px;
  font-weight: 400;
  color: inherit;
  margin-bottom: 4px;
}

.tool-item-desc {
  font-family: 'PingFangSC-Regular', 'PingFang SC', sans-serif;
  font-size: 10px;
  font-weight: 400;
  color: #aaaaaa;
  line-height: 1.4;
}

.studio-item {
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.15) 0%, rgba(139, 92, 246, 0.15) 100%);
  border: 1px solid rgba(99, 102, 241, 0.3);
  border-radius: 8px !important;
}

.studio-item:hover {
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.25) 0%, rgba(139, 92, 246, 0.25) 100%);
  border-color: rgba(99, 102, 241, 0.5);
}

.studio-item.active {
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.4) 0%, rgba(139, 92, 246, 0.4) 100%);
  border-color: #6366f1;
}

.studio-badge {
  display: inline-block;
  padding: 2px 6px;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
  color: white;
  margin-right: 6px;
  vertical-align: middle;
}

.recent-projects {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.project-list {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0;
  overflow-y: auto;
}

.project-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 0;
  border-radius: 0;
  cursor: pointer;
  transition: background 0.2s ease;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.project-item:hover {
  background: rgba(255, 255, 255, 0.05);
}

.project-info {
  flex: 1;
  min-width: 0;
}

.project-name {
  font-family: 'PingFangSC-Regular', 'PingFang SC', sans-serif;
  font-size: 14px;
  font-weight: 400;
  color: #ffffff;
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  cursor: pointer;
  padding: 2px 4px;
  border-radius: 2px;
  transition: background-color 0.2s;
}

.project-name:hover {
  background-color: rgba(255, 255, 255, 0.1);
}

.project-name-input {
  margin-bottom: 4px;
}

.project-name-input :deep(.el-input__wrapper) {
  background-color: rgba(255, 255, 255, 0.1);
  border: 1px solid #00aaaa;
  border-radius: 2px;
  padding: 2px 8px;
}

.project-name-input :deep(.el-input__inner) {
  font-family: 'PingFangSC-Regular', 'PingFang SC', sans-serif;
  font-size: 14px;
  color: #ffffff;
  height: 20px;
  line-height: 20px;
}

.project-actions {
  display: flex;
  align-items: center;
}

.project-time {
  font-family: 'PingFangSC-Regular', 'PingFang SC', sans-serif;
  font-size: 10px;
  color: #aaaaaa;
}

.delete-btn {
  color: #ffffff;
  padding: 4px;
  margin-left: 8px;
  opacity: 0.6;
}

.delete-btn:hover {
  opacity: 1;
  color: #ffffff;
}

.delete-btn :deep(.el-icon) {
  font-size: 16px;
}

.no-projects {
  padding: 20px 0;
  text-align: center;
  color: #aaaaaa;
  font-family: 'PingFangSC-Regular', 'PingFang SC', sans-serif;
  font-size: 12px;
}

/* 响应式 */
@media (max-width: 768px) {
  .sidebar {
    position: fixed;
    top: 0;
    left: 0;
    height: 100vh;
    z-index: 1000;
    box-shadow: 2px 0 8px rgba(0, 0, 0, 0.1);
  }

  .sidebar.collapsed {
    transform: translateX(-100%);
  }
}
</style>
