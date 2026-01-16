<template>
  <div id="app">
    <!-- 认证页面（登录/注册） -->
    <router-view v-if="isAuthPage" v-slot="{ Component }">
      <transition name="fade" mode="out-in">
        <component :is="Component" />
      </transition>
    </router-view>

    <!-- 全屏页面（Studio / 新创意页等） -->
    <router-view v-else-if="isFullscreenPage" v-slot="{ Component }">
      <transition name="fade" mode="out-in">
        <component :is="Component" />
      </transition>
    </router-view>

    <!-- 应用主页面 -->
    <MainContent v-else>
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </MainContent>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import MainContent from '@/components/layout/MainContent.vue'

// 全局样式
import './styles/index.css'

const route = useRoute()

// 判断是否为认证页面
const isAuthPage = computed(() => {
  return route.name === 'Login' || route.name === 'Register'
})

// 判断是否为全屏页面（Studio 等）
const isFullscreenPage = computed(() => {
  return (
    route.name === 'Studio' ||
    route.name === 'StudioProject'
  )
})
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0
}
</style>
