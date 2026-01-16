// API相关类型定义

export interface ApiResponse<T = any> {
  code: number
  message: string
  data: T
}

export interface PageResponse<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
  totalPages: number
}

// 用户相关
export interface User {
  id: number
  username: string
  email: string
  avatar?: string
  createdAt: string
  updatedAt: string
}

export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  user: User
  accessToken: string
  refreshToken: string
}

export interface CreateProjectRequest {
  name: string
  description?: string
}

export interface GenerateScriptRequest {
  inspiration: string
  style: string
  totalDuration: number
  segmentDuration: number
  projectId?: number
  generationMode?: string  // 'one_click' 或 'step_by_step'
  referenceImageUrls?: string[]  // 参考图URL列表
  enableSearch?: boolean  // 是否启用联网搜索（后端: enable_search）
}

export interface GenerateKeyframesResponse {
  keyframes: any[] // Keyframe[] is in project.ts
  totalCount: number
}

export interface GenerateKeyframeRequest {
  scriptId: number
  model: string
  aspectRatio: string
  quality: string
  onlyFirstFrame?: boolean  // 是否只生成首段关键帧 segment_0（用于确认），确认后继续生成其余段
}

export interface GenerateVideoRequest {
  scriptId: number
  model?: string
  aspectRatio?: string
  duration?: number
}

// 文件相关
export interface FileUploadResponse {
  fileId: number
  fileName: string
  fileUrl: string
  fileSize: number
  mimeType: string
}


