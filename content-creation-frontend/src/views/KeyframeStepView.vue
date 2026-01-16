<template>
  <div class="keyframe-step-view">
    <KeyframeList 
      :project-id="projectId"
      @generate-video="handleGenerateVideo"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { videoApi, projectApi } from '@/api'
import { useProjectStore } from '@/stores'
import KeyframeList from '@/components/script-generation/KeyframeList.vue'

const route = useRoute()
const router = useRouter()
const projectStore = useProjectStore()

const projectId = computed(() => {
  const id = route.params.projectId
  return id ? parseInt(id as string, 10) : null
})

const ALLOWED_ASPECT_RATIOS = ['9:16', '16:9'] as const
const normalize_aspect_ratio = (ratio?: string): string => {
  const r = String(ratio || '')
  return (ALLOWED_ASPECT_RATIOS as unknown as string[]).includes(r) ? r : '16:9'
}

const handleGenerateVideo = async (params: { videoModel: string }) => {
  if (projectStore.projectCompletionStatus === 'completed') {
    ElMessage.warning('当前项目已完成（completed），关键帧页面不可重新生成视频')
    return
  }
  const scriptId = projectStore.currentScript?.id
  if (!scriptId) {
    ElMessage.error('脚本ID不存在')
    return
  }

  try {
    // 1. 清空旧视频 (store)
    projectStore.updateVideoSegments([])
    
    // 2. 调用API
    await videoApi.generateVideos({
      scriptId,
      model: params.videoModel,
      aspectRatio: normalize_aspect_ratio((projectStore.currentProject as any)?.aspectRatio),
      duration: 4.0
    })
    
    ElMessage.success('开始生成视频，正在跳转...')
    
    // 3. 跳转到视频页面
    router.push({
      name: 'VideoGeneration',
      params: { projectId: projectId.value }
    })
  } catch (error: any) {
    console.error('生成视频失败:', error)
    ElMessage.error(error?.message || '生成启动失败')
  }
}

onMounted(async () => {
    // 确保项目数据加载
    if (projectId.value && (!projectStore.currentProject || projectStore.currentProject.id !== projectId.value)) {
        try {
            const project = await projectApi.getProject(projectId.value)
            projectStore.setCurrentProject(project as any)
        } catch (e) { console.error(e) }
    }
})
</script>

<style scoped>
.keyframe-step-view {
  width: 100%;
  height: 100%;
  background-color: #fff; /* 面板背景 */
  box-sizing: border-box;
}
</style>
