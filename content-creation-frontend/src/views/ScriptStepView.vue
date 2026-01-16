<template>
  <div class="script-step-view">
    <ScriptEditor :project-id="projectId" @generate-keyframes="handleGenerateKeyframes" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { keyframeApi, projectApi } from '@/api'
import { useProjectStore } from '@/stores'
import ScriptEditor from '@/components/script-generation/ScriptEditor.vue'

const route = useRoute()
const router = useRouter()
const projectStore = useProjectStore()

const projectId = computed(() => {
  const id = route.params.projectId
  return id ? parseInt(id as string, 10) : null
})

const handleGenerateKeyframes = async (params: { model: string, aspectRatio: string, quality: string }) => {
  if (projectStore.projectCompletionStatus === 'completed') {
    ElMessage.warning('当前项目已完成（completed），无法生成关键帧')
    return
  }
  if (!projectStore.currentScript?.id) {
    ElMessage.warning('请先生成脚本')
    return
  }
  
  try {
    // 1. 清空旧的关键帧 (store)
    projectStore.updateKeyframes([])

    // 同步保存项目配置到 store（双保险，确保关键帧页 continue 使用同一份比例）
    projectStore.updateCurrentProject({
      imageModel: params.model,
      aspectRatio: params.aspectRatio,
      quality: params.quality
    } as any)
    
    // 2. 调用生成接口（先只生成首段关键帧 segment_0，用于确认；确认后在关键帧页继续生成其余段）
    const request: any = {
      script_id: projectStore.currentScript.id,
      model: params.model,
      aspect_ratio: params.aspectRatio,
      only_first_frame: true
    }
    if (params.quality) request.quality = params.quality

    // 添加参考图URLs（如果有）
    if (projectStore.referenceImageUrls.length > 0) {
      request.reference_image_urls = projectStore.referenceImageUrls
    }

    // 3. 调用API
    await keyframeApi.generateKeyframes(request)
    ElMessage.success('开始生成关键帧，正在跳转...')
    
    // 4. 跳转到关键帧页面
    router.push({
      name: 'KeyframeGeneration',
      params: { projectId: projectId.value }
    })
  } catch (error: any) {
    console.error('生成关键帧失败:', error)
    ElMessage.error(error?.message || '生成启动失败')
  }
}

onMounted(async () => {
  if (projectId.value && (!projectStore.currentProject || projectStore.currentProject.id !== projectId.value)) {
     // 简单的加载逻辑，复杂逻辑在 store 中处理
     // 这里假设 App 或 layout 已经加载了项目，或者组件内部会自加载
     // 为了保险，重新加载项目信息
     try {
       const project = await projectApi.getProject(projectId.value)
       projectStore.setCurrentProject(project as any)
     } catch (e) {
       console.error('加载项目失败', e)
     }
  }
})
</script>

<style scoped>
.script-step-view {
  width: 100%;
  height: 100%;
  box-sizing: border-box;
}
</style>
