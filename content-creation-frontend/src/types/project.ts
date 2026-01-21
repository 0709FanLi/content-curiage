// 项目状态管理相关类型

export interface ProjectState {
  currentProject: Project | null
  projects: Project[]
  recentProjects: Project[]
  loading: boolean
  error: string | null
}

export interface Project {
  id: number
  name: string
  description?: string
  status: ProjectStatus
  conversationContent?: string
  imageModel?: string
  aspectRatio?: string
  quality?: string
  generationMode?: string  // 'one_click' 或 'step_by_step'
  referenceImageUrls?: string[] // 参考图URL列表（用于关键帧 segment_0 定调）
  script?: Script
  keyframes?: Keyframe[]
  videoSegments?: VideoSegment[]
  createdAt: string
  updatedAt: string
  firstScriptGeneratedAt?: string
}

export type ProjectStatus = 'draft' | 'script_generated' | 'keyframes_generating' | 'keyframes_completed' | 'video_generating' | 'completed'

export interface Script {
  id: number
  projectId: number
  content: string
  style?: string
  totalDuration?: number
  segmentDuration?: number
  segments: ScriptSegment[]
  optimizedContent?: string
  exportedVideoUrl?: string
  exported_video_url?: string
  // 可观测：参考图是否参与“脚本生成”的视觉解析与注入（dev 环境可能包含 errorMessage）
  visionAnalysis?: {
    attempted: boolean
    status: 'skipped' | 'success' | 'empty' | 'failed'
    used: boolean
    guidanceLength: number
    errorType?: string
    errorMessage?: string
  }
}

export interface ScriptSegment {
  id: string
  timeStart: number
  timeEnd: number
  content: string
  scene?: string
  presenter?: string
  subtitle?: string
  keyframe?: Keyframe
  videoSegment?: VideoSegment
}

export interface Keyframe {
  id: number
  segmentId: string
  imageUrl?: string
  prompt?: string
  status: KeyframeStatus
  error?: string
  // 与后端字段对齐（KeyframeResponse: errorMessage）
  errorMessage?: string
}

export type KeyframeStatus = 'pending' | 'generating' | 'completed' | 'failed'

export interface VideoSegment {
  id: number
  scriptId: number
  segmentIndex: number
  firstFrameUrl?: string
  lastFrameUrl?: string
  prompt?: string
  narration?: string
  videoUrl?: string
  model?: string
  aspectRatio?: string
  status: VideoStatus
  duration: number
  errorMessage?: string
  createdAt: string
  updatedAt: string
}

export type VideoStatus = 'pending' | 'generating' | 'completed' | 'failed'

// UI 状态
export interface UIState {
  sidebarCollapsed: boolean
  loading: boolean
  globalLoading: boolean
  currentModal: string | null
  notifications: Notification[]
}

export interface Notification {
  id: string
  type: 'success' | 'warning' | 'error' | 'info'
  title: string
  message: string
  duration?: number
  timestamp: number
}
