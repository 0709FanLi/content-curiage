<template>
  <div class="script-start">
    <ScriptOptimization
      placeholder="粘贴你的脚本，输入优化需求···"
      button-text="优化脚本"
      mode="script"
      @success="handleSuccess"
      @error="handleError"
    />
  </div>
</template>

<script setup lang="ts">
import ScriptOptimization from '@/components/common/ScriptOptimization.vue'
import { useProjectStore } from '@/stores'

const projectStore = useProjectStore()

// 进入“从脚本开始”入口页时，清空上一次的参考图，避免状态串联
projectStore.clearReferenceImages()

const handleSuccess = (data: any) => {
  // 脚本优化成功后的处理
}

const handleError = (error: string) => {
  // 错误处理
  console.error('脚本优化失败:', error)
}
</script>

<style scoped>
.script-start {
  width: 100%;
  height: 100%;
}
</style>
