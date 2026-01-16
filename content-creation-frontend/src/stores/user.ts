// 用户状态管理

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api'
import type { User } from '@/types'

export interface UserState {
  currentUser: User | null
  isAuthenticated: boolean
  loading: boolean
  error: string | null
}

export const useUserStore = defineStore('user', () => {
  // 状态
  const currentUser = ref<User | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // 计算属性
  const isAuthenticated = computed(() => !!currentUser.value)

  const displayName = computed(() => {
    return currentUser.value?.username || '未登录用户'
  })

  const avatarUrl = computed(() => {
    return currentUser.value?.avatar || '/default-avatar.png'
  })

  // 动作
  const setUser = (user: User | null) => {
    currentUser.value = user
    error.value = null
  }

  const setLoading = (value: boolean) => {
    loading.value = value
  }

  const setError = (message: string | null) => {
    error.value = message
  }

  const updateUser = (updates: Partial<User>) => {
    if (currentUser.value) {
      currentUser.value = { ...currentUser.value, ...updates }
    }
  }

  const logout = async () => {
    // 无论后端是否可用，都保证前端能立即“退出登录”
    currentUser.value = null
    error.value = null

    localStorage.removeItem('accessToken')
    localStorage.removeItem('refreshToken')

    try {
      // 调用后端退出接口
      await authApi.logout()
    } catch (error) {
      // 即使API调用失败，也清除本地状态
      console.error('退出登录API调用失败:', error)
    }
  }

  const initializeAuth = () => {
    const token = localStorage.getItem('accessToken')
    if (token) {
      // 这里可以添加token验证逻辑
      // 暂时设置一个空的user表示已登录状态
      // 实际项目中应该从token解析用户信息或调用API获取
      currentUser.value = {
        id: 1,
        username: 'testuser',
        email: 'test@example.com',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      }
    }
  }

  return {
    // 状态
    currentUser,
    loading,
    error,

    // 计算属性
    isAuthenticated,
    displayName,
    avatarUrl,

    // 动作
    setUser,
    setLoading,
    setError,
    updateUser,
    logout,
    initializeAuth
  }
})
