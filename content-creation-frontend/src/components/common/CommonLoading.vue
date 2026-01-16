<template>
  <div v-if="visible" class="common-loading-overlay" role="status" aria-live="polite">
    <div class="common-loading-card">
      <div class="common-loading-spinner" />
      <div class="common-loading-text">{{ text }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  visible: boolean
  text?: string
}>()
</script>

<style scoped>
.common-loading-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(10, 18, 28, 0.28);
  backdrop-filter: blur(3px);
}

.common-loading-card {
  min-width: 260px;
  max-width: 520px;
  padding: 18px 20px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.92);
  box-shadow:
    0 18px 50px rgba(15, 23, 42, 0.18),
    0 8px 20px rgba(15, 23, 42, 0.12);
  display: flex;
  align-items: center;
  gap: 12px;
}

.common-loading-spinner {
  width: 18px;
  height: 18px;
  border-radius: 999px;
  border: 2px solid rgba(59, 130, 246, 0.25);
  border-top-color: rgba(59, 130, 246, 0.95);
  animation: common-loading-spin 0.9s linear infinite;
}

.common-loading-text {
  color: rgba(15, 23, 42, 0.9);
  font-size: 14px;
  line-height: 20px;
  font-weight: 600;
  letter-spacing: 0.2px;
}

@keyframes common-loading-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>

