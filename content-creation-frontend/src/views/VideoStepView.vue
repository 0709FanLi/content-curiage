<template>
  <div class="video-step-view">
    <VideoList :project-id="projectId" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { projectApi } from '@/api'
import { useProjectStore } from '@/stores'
import VideoList from '@/components/script-generation/VideoList.vue'

const route = useRoute()
const projectStore = useProjectStore()

const projectId = computed(() => {
  const id = route.params.projectId
  return id ? parseInt(id as string, 10) : null
})

onMounted(async () => {
    if (projectId.value && (!projectStore.currentProject || projectStore.currentProject.id !== projectId.value)) {
        try {
            const project = await projectApi.getProject(projectId.value)
            projectStore.setCurrentProject(project as any)
        } catch (e) { console.error(e) }
    }
})
</script>

<style scoped>
.video-step-view {
  width: 100%;
  height: 100%;
  background-color: #fff;
  box-sizing: border-box;
}
</style>
