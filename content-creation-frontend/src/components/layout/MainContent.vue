<template>
  <div class="main-shell">
    <!-- 顶部栏：铺满整个顶部 -->
    <FigmaHeader />

    <!-- 主体：侧边栏在 Header 之下 -->
    <div class="main-body">
      <FigmaSidebar />
      <div class="content-area">
        <slot />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import FigmaHeader from './FigmaHeader.vue'
import FigmaSidebar from './FigmaSidebar.vue'
</script>

<style scoped>
.main-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100%;
  background: #f3f4f6;
  gap: 0;
  padding: 0;
  overflow: hidden;
}

.main-body {
  height: calc(100vh - 56px);
  display: flex;
  flex-direction: row;
  min-width: 0;
  overflow: hidden;
  background: #f3f4f6;
}

.content-area {
  flex: 1;
  min-width: 0;
  padding: 0;
  overflow: hidden;
  background-color: #f3f4f6;
}

/* 响应式 */
@media (max-width: 768px) {
  .content-area {
    padding: 0;
  }
}
</style>
