// 项目状态管理

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Project, Script, Keyframe, VideoSegment, ProjectState } from '@/types'

export const useProjectStore = defineStore('project', () => {
  // 状态
  const currentProject = ref<Project | null>(null)
  const projects = ref<Project[]>([])
  const recentProjects = ref<Project[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const referenceImageUrls = ref<string[]>([])
  const completionStatusByProjectId = ref<Record<number, 'completed' | 'save'>>({})

  // 计算属性
  const get_exported_video_url = (project: Project | null | undefined): string => {
    const url =
      String((project as any)?.script?.exportedVideoUrl || '').trim() ||
      String((project as any)?.script?.exported_video_url || '').trim()
    return url
  }

  const projectCompletionStatus = computed<'completed' | 'save'>(() => {
    // 后端项目状态已完成也视为 completed（用于关键帧/视频页面锁定）
    if (currentProject.value?.status === 'completed') return 'completed'
    const url = get_exported_video_url(currentProject.value)
    return url ? 'completed' : 'save'
  })

  const isProjectCompleted = computed(() => {
    return projectCompletionStatus.value === 'completed'
  })

  const currentScript = computed(() => currentProject.value?.script)
  const currentKeyframes = computed(() => currentProject.value?.keyframes || [])
  const currentVideoSegments = computed(() => currentProject.value?.videoSegments || [])

  const keyframesCompleted = computed(() => {
    const keyframes = currentKeyframes.value
    return keyframes.length > 0 && keyframes.every(k => k.status === 'completed')
  })

  const videosCompleted = computed(() => {
    const videos = currentVideoSegments.value
    return videos.length > 0 && videos.every(v => v.status === 'completed')
  })

  // 动作
  const setCurrentProject = (project: Project | null) => {
    // 检查是否切换到不同的项目
    // 注意：只有当两个项目都有ID且ID不同时，才认为是切换项目
    // 如果从 null 切换到有ID的项目，或者从有ID的项目切换到 null，不清空参考图
    // 这样可以保留用户在创建项目过程中上传的参考图
    const oldProjectId = currentProject.value?.id
    const newProjectId = project?.id
    const isDifferentProject = oldProjectId && newProjectId && oldProjectId !== newProjectId
    
    currentProject.value = project
    error.value = null

    if (project?.id) {
      completionStatusByProjectId.value[project.id] = get_exported_video_url(project)
        ? 'completed'
        : 'save'
    }
    
    // 只在切换到不同项目时清空参考图
    if (isDifferentProject) {
      clearReferenceImages()
    }
  }

  const set_project_exported_video_url = (project_id: number, url: string) => {
    const trimmed = String(url || '').trim()
    completionStatusByProjectId.value[project_id] = trimmed ? 'completed' : 'save'
    if (currentProject.value?.id === project_id && currentProject.value.script) {
      ;(currentProject.value.script as any).exportedVideoUrl = trimmed
    }
  }

  const getProjectCompletionStatus = (project: Project | null | undefined): 'completed' | 'save' => {
    const id = Number(project?.id || 0)
    if (id && completionStatusByProjectId.value[id]) {
      return completionStatusByProjectId.value[id]
    }
    if ((project as any)?.status === 'completed') return 'completed'
    const url = get_exported_video_url(project || null)
    if (url) return 'completed'
    return 'save'
  }

  const updateCurrentProject = (updates: Partial<Project>) => {
    if (currentProject.value) {
      currentProject.value = { ...currentProject.value, ...updates }
    }
  }

  const setProjects = (projectList: Project[]) => {
    projects.value = projectList
    // 同时更新最近项目列表（显示全部，支持滚动）
    recentProjects.value = projectList
  }

  const addProject = (project: Project) => {
    // 检查项目是否已存在
    const existingIndex = projects.value.findIndex(p => p.id === project.id)
    if (existingIndex !== -1) {
      // 如果已存在，更新并移到最前面
      projects.value.splice(existingIndex, 1)
    }
    projects.value.unshift(project)
    recentProjects.value = projects.value
  }
  
  const loadRecentProjects = async () => {
    try {
      const { projectApi } = await import('@/api')
      const response = await projectApi.getProjects({ page: 1, pageSize: 10 })
      setProjects(response.items || [])
    } catch (error) {
      console.error('加载最近项目失败:', error)
    }
  }

  const updateProject = (projectId: number, updates: Partial<Project>) => {
    const index = projects.value.findIndex(p => p.id === projectId)
    if (index !== -1) {
      projects.value[index] = { ...projects.value[index], ...updates }
    }

    if (currentProject.value?.id === projectId) {
      updateCurrentProject(updates)
    }

    // 更新最近项目列表（显示全部，支持滚动）
    recentProjects.value = projects.value
  }

  const removeProject = (projectId: number) => {
    projects.value = projects.value.filter(p => p.id !== projectId)
    recentProjects.value = projects.value

    if (currentProject.value?.id === projectId) {
      currentProject.value = null
    }
  }

  const setLoading = (value: boolean) => {
    loading.value = value
  }

  const setError = (message: string | null) => {
    error.value = message
  }

  const updateScript = (script: Script) => {
    if (currentProject.value) {
      // 使用展开运算符确保响应式更新
      currentProject.value = {
        ...currentProject.value,
        script: script,
        status: 'script_generated'
      }
      // 确保脚本正确设置
    } else {
      console.error('updateScript - 当前项目不存在')
    }
  }

  const updateKeyframes = (keyframes: Keyframe[]) => {
    if (currentProject.value) {
      currentProject.value.keyframes = keyframes
      const allCompleted = keyframes.every(k => k.status === 'completed')
      if (allCompleted) {
        currentProject.value.status = 'keyframes_completed'
      } else if (keyframes.some(k => k.status === 'generating')) {
        currentProject.value.status = 'keyframes_generating'
      }
    }
  }

  const updateKeyframe = (keyframeId: number, updates: Partial<Keyframe>) => {
    if (currentProject.value?.keyframes) {
      const index = currentProject.value.keyframes.findIndex(k => k.id === keyframeId)
      if (index !== -1) {
        currentProject.value.keyframes[index] = {
          ...currentProject.value.keyframes[index],
          ...updates
        }
        updateKeyframes(currentProject.value.keyframes)
      }
    }
  }

  const updateVideoSegments = (videos: VideoSegment[]) => {
    if (currentProject.value) {
      currentProject.value.videoSegments = videos
      const allCompleted = videos.every(v => v.status === 'completed')
      if (allCompleted) {
        currentProject.value.status = 'completed'
      } else if (videos.some(v => v.status === 'generating')) {
        currentProject.value.status = 'video_generating'
      }
    }
  }

  const updateVideoSegment = (videoId: number, updates: Partial<VideoSegment>) => {
    if (currentProject.value?.videoSegments) {
      const index = currentProject.value.videoSegments.findIndex(v => v.id === videoId)
      if (index !== -1) {
        currentProject.value.videoSegments[index] = {
          ...currentProject.value.videoSegments[index],
          ...updates
        }
        updateVideoSegments(currentProject.value.videoSegments)
      }
    }
  }

  const resetProject = () => {
    currentProject.value = null
    error.value = null
    // 重置项目时清空参考图
    clearReferenceImages()
  }

  const setReferenceImages = (urls: string[]) => {
    referenceImageUrls.value = urls
  }

  const clearReferenceImages = () => {
    referenceImageUrls.value = []
  }

  return {
    // 状态
    currentProject,
    projects,
    recentProjects,
    loading,
    error,
    referenceImageUrls,
    completionStatusByProjectId,

    // 计算属性
    isProjectCompleted,
    projectCompletionStatus,
    currentScript,
    currentKeyframes,
    currentVideoSegments,
    keyframesCompleted,
    videosCompleted,

    // 动作
    setCurrentProject,
    updateCurrentProject,
    setProjects,
    addProject,
    updateProject,
    removeProject,
    setLoading,
    setError,
    updateScript,
    updateKeyframes,
    updateKeyframe,
    updateVideoSegments,
    updateVideoSegment,
    resetProject,
    loadRecentProjects,
    setReferenceImages,
    clearReferenceImages,
    set_project_exported_video_url,
    getProjectCompletionStatus
  }
})
