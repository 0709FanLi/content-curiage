// 类型定义统一出口

export * from './api'
export * from './project'

// 通用工具类型
export type Nullable<T> = T | null
export type Optional<T, K extends keyof T> = Omit<T, K> & Partial<Pick<T, K>>
export type RequiredField<T, K extends keyof T> = T & Required<Pick<T, K>>

// Vue 相关类型
export type ComponentRef<T = any> = T
export type VueInstance = any

// 文件相关类型
export interface FileItem {
  id: string
  name: string
  size: number
  type: string
  url?: string
  status: 'uploading' | 'completed' | 'failed'
  progress?: number
  error?: string
}

// 表单验证类型
export interface ValidationRule {
  required?: boolean
  min?: number
  max?: number
  pattern?: RegExp
  message: string
}

export interface FormItem {
  value: any
  rules?: ValidationRule[]
  error?: string
  valid: boolean
}
