// UI状态管理

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Notification, UIState } from '@/types'

export const useUIStore = defineStore('ui', () => {
  // 状态
  const sidebarCollapsed = ref(false)
  const loading = ref(false)
  const globalLoading = ref(false)
  const currentModal = ref<string | null>(null)
  const notifications = ref<Notification[]>([])

  // 计算属性
  const hasActiveModal = computed(() => !!currentModal.value)

  const activeNotifications = computed(() =>
    notifications.value.filter(n => !n.duration || Date.now() - n.timestamp < n.duration)
  )

  // 动作
  const toggleSidebar = () => {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  const setSidebarCollapsed = (collapsed: boolean) => {
    sidebarCollapsed.value = collapsed
  }

  const setLoading = (value: boolean) => {
    loading.value = value
  }

  const setGlobalLoading = (value: boolean) => {
    globalLoading.value = value
  }

  const openModal = (modalName: string) => {
    currentModal.value = modalName
  }

  const closeModal = () => {
    currentModal.value = null
  }

  const addNotification = (notification: Omit<Notification, 'id' | 'timestamp'>) => {
    const id = Date.now().toString()
    const newNotification: Notification = {
      id,
      timestamp: Date.now(),
      duration: 5000, // 默认5秒
      ...notification
    }

    notifications.value.push(newNotification)

    // 自动移除过期通知
    if (newNotification.duration) {
      setTimeout(() => {
        removeNotification(id)
      }, newNotification.duration)
    }
  }

  const removeNotification = (id: string) => {
    const index = notifications.value.findIndex(n => n.id === id)
    if (index !== -1) {
      notifications.value.splice(index, 1)
    }
  }

  const clearNotifications = () => {
    notifications.value = []
  }

  const showSuccess = (message: string, title = '成功') => {
    addNotification({
      type: 'success',
      title,
      message
    })
  }

  const showError = (message: string, title = '错误') => {
    addNotification({
      type: 'error',
      title,
      message
    })
  }

  const showWarning = (message: string, title = '警告') => {
    addNotification({
      type: 'warning',
      title,
      message
    })
  }

  const showInfo = (message: string, title = '提示') => {
    addNotification({
      type: 'info',
      title,
      message
    })
  }

  return {
    // 状态
    sidebarCollapsed,
    loading,
    globalLoading,
    currentModal,
    notifications,

    // 计算属性
    hasActiveModal,
    activeNotifications,

    // 动作
    toggleSidebar,
    setSidebarCollapsed,
    setLoading,
    setGlobalLoading,
    openModal,
    closeModal,
    addNotification,
    removeNotification,
    clearNotifications,
    showSuccess,
    showError,
    showWarning,
    showInfo
  }
})
