import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { title: '登录', requiresAuth: false }
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/Register.vue'),
    meta: { title: '注册', requiresAuth: false }
  },
  {
    path: '/',
    redirect: '/inspiration'
  },
  {
    path: '/inspiration',
    name: 'InspirationInput',
    component: () => import('@/views/InspirationInput.vue'),
    meta: { title: '开始创作', requiresAuth: true }
  },
  {
    path: '/medeo',
    name: 'MedeoStart',
    component: () => import('@/views/MedeoStartView.vue'),
    meta: { title: 'Medeo - 开始', requiresAuth: true }
  },
  {
    path: '/medeo/project/:projectId',
    name: 'MedeoPreviewProject',
    component: () => import('@/views/MedeoPreviewView.vue'),
    meta: { title: 'Medeo - 预览', requiresAuth: true }
  },
  {
    path: '/script-start',
    name: 'ScriptStart',
    component: () => import('@/views/ScriptStart.vue'),
    meta: { title: '开始创作', requiresAuth: true }
  },
  // 旧路由重定向
  {
    path: '/script-generation/:projectId?',
    redirect: to => {
      const projectId = to.params.projectId
      if (projectId) {
        return `/project/${projectId}/script`
      }
      return '/inspiration'
    }
  },
  // 新的分步路由
  {
    path: '/project/:projectId/script',
    name: 'ScriptGenerationStep',
    component: () => import('@/views/ScriptStepView.vue'),
    meta: { title: '编辑脚本', requiresAuth: true }
  },
  {
    path: '/project/:projectId/keyframes',
    name: 'KeyframeGeneration',
    component: () => import('@/views/KeyframeStepView.vue'),
    meta: { title: '生成关键帧', requiresAuth: true }
  },
  {
    path: '/project/:projectId/video',
    name: 'VideoGeneration',
    component: () => import('@/views/VideoStepView.vue'),
    meta: { title: '生成视频', requiresAuth: true }
  },
  {
    path: '/project/:projectId/one-click',
    name: 'OneClickGenerate',
    component: () => import('@/views/OneClickGenerateView.vue'),
    meta: { title: '一键生成', requiresAuth: true }
  },
  {
    path: '/project/:projectId',
    redirect: to => `/project/${to.params.projectId}/script`
  },
  // Medeo 风格的时间线编辑器
  {
    path: '/studio',
    name: 'Studio',
    component: () => import('@/views/StudioView.vue'),
    meta: { title: 'AI 创作工作室', requiresAuth: true }
  },
  {
    path: '/studio/:projectId',
    name: 'StudioProject',
    component: () => import('@/views/StudioView.vue'),
    meta: { title: 'AI 创作工作室', requiresAuth: true }
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

// 路由守卫
router.beforeEach((to, from, next) => {
  // 设置页面标题
  if (to.meta.title) {
    document.title = `${to.meta.title} - 内容创作`
  }

  // 检查认证状态
  const requiresAuth = to.meta.requiresAuth !== false // 默认需要认证
  const isAuthenticated = !!localStorage.getItem('accessToken')


  if (requiresAuth && !isAuthenticated) {
    // 需要认证但未登录，跳转到登录页面
    next({ name: 'Login', query: { redirect: to.fullPath } })
  } else if (!requiresAuth && isAuthenticated && (to.name === 'Login' || to.name === 'Register')) {
    // 已登录用户访问登录/注册页面，跳转到输入灵感页面
    next({ name: 'InspirationInput' })
  } else {
    next()
  }
})

export default router
