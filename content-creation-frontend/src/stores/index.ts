// Pinia stores 统一出口

import { useProjectStore } from './project'
import { useUserStore } from './user'
import { useUIStore } from './ui'

export {
  useProjectStore,
  useUserStore,
  useUIStore
}

// 导出类型
export type { ProjectState } from './project'
export type { UserState } from './user'
export type { UIState } from './ui'
