// API接口统一出口

import request from '@/utils/request'
import type {
  LoginRequest,
  LoginResponse,
  Project,
  CreateProjectRequest,
  Script,
  GenerateScriptRequest,
  Keyframe,
  GenerateKeyframeRequest,
  GenerateKeyframesResponse,
  VideoSegment,
  GenerateVideoRequest,
  FileUploadResponse
} from '@/types'

// 认证相关API
export const authApi = {
  register: (data: { username: string; email: string; password: string }): Promise<any> =>
    request.post('/auth/register', data),

  login: (data: LoginRequest): Promise<LoginResponse> =>
    request.post('/auth/login', data),

  refreshToken: (): Promise<{ accessToken: string }> =>
    request.post('/auth/refresh'),

  logout: (): Promise<void> =>
    // 登出应快速失败，避免后端卡住时前端无法退出
    request.post('/auth/logout', undefined, { timeout: 5000 }),

  getCurrentUser: (): Promise<any> =>
    request.get('/auth/me')
}

// 项目管理API
export const projectApi = {
  getProjects: (params?: { page?: number; pageSize?: number }): Promise<{ items: Project[]; total: number }> =>
    request.get('/projects', { params }),

  getProject: (id: number): Promise<Project> =>
    request.get(`/projects/${id}`),

  createProject: (data: CreateProjectRequest): Promise<Project> =>
    request.post('/projects', data),

  updateProject: (id: number, data: Partial<Project>): Promise<Project> =>
    request.put(`/projects/${id}`, data),

  deleteProject: (id: number): Promise<void> =>
    request.delete(`/projects/${id}`),

  getRecentProjects: (): Promise<{ items: Project[]; total: number }> =>
    request.get('/projects', { params: { page: 1, pageSize: 10 } })
}

// 脚本管理API
export const scriptApi = {
  generateScript: (data: GenerateScriptRequest, model?: string): Promise<Script> => {
    const url = model ? `/scripts/generate?model=${encodeURIComponent(model)}` : '/scripts/generate'
    return request.post(url, data, { timeout: 180000 })
  },

  optimizeScript: (scriptId: number, optimization: string, model?: string, enableSearch?: boolean): Promise<Script> => {
    const url = model ? `/scripts/${scriptId}/optimize?model=${encodeURIComponent(model)}` : `/scripts/${scriptId}/optimize`
    return request.post(url, { optimization, enableSearch: !!enableSearch }, { timeout: 180000 })
  },

  getScript: (id: number): Promise<Script> =>
    request.get(`/scripts/${id}`),

  updateScript: (id: number, data: Partial<Script>): Promise<Script> =>
    request.put(`/scripts/${id}`, data),

  cancelGeneration: (scriptId: number): Promise<{ message: string; scriptId: number }> =>
    request.post(`/scripts/${scriptId}/cancel`)
}

// 关键帧管理API
export const keyframeApi = {
  generateKeyframes: (data: GenerateKeyframeRequest): Promise<{ keyframes: Keyframe[]; totalCount: number }> =>
    request.post('/keyframes/generate', data, { timeout: 300000 }),

  continueGenerateKeyframes: (scriptId: number, data: GenerateKeyframeRequest): Promise<{ keyframes: Keyframe[]; totalCount: number }> =>
    request.post(`/keyframes/continue/${scriptId}`, data, { timeout: 300000 }),

  getKeyframesByScript: (scriptId: number): Promise<{ keyframes: Keyframe[]; totalCount: number }> =>
    request.get(`/keyframes/script/${scriptId}`),

  getKeyframe: (id: number): Promise<Keyframe> =>
    request.get(`/keyframes/${id}`),

  regenerateKeyframe: (id: number, model?: string, aspectRatio?: string, quality?: string): Promise<Keyframe> => {
    const data: any = {}
    if (model) data.model = model
    if (aspectRatio) data.aspectRatio = aspectRatio
    if (quality) data.quality = quality
    return request.post(`/keyframes/${id}/regenerate`, Object.keys(data).length > 0 ? data : {})
  },

  updateKeyframe: (id: number, data: Partial<Keyframe>): Promise<Keyframe> =>
    request.put(`/keyframes/${id}`, data),

  uploadKeyframeImage: (id: number, file: File): Promise<Keyframe> =>
    request.upload(`/keyframes/${id}/upload`, file)
}

// 视频管理API
export const videoApi = {
  getVideoModels: (): Promise<{ models: Array<{ id: string; name: string; description: string; supportsFirstLastFrame: boolean }> }> =>
    request.get('/videos/models'),

  generateVideos: (data: GenerateVideoRequest): Promise<{ videoSegments: VideoSegment[]; totalCount: number }> =>
    request.post('/videos/generate', data, { timeout: 300000 }),

  getVideoSegmentsByScript: (scriptId: number): Promise<{ videoSegments: VideoSegment[]; totalCount: number }> =>
    request.get(`/videos/script/${scriptId}`),

  getVideoSegment: (id: number): Promise<VideoSegment> =>
    request.get(`/videos/${id}`),

  regenerateVideoSegment: (id: number, model?: string): Promise<VideoSegment> => {
    const data: any = {}
    if (model) data.model = model
    return request.post(`/videos/${id}/regenerate`, data)
  },

  updateVideoSegment: (
    id: number,
    data: { prompt?: string; videoUrl?: string; status?: string; errorMessage?: string }
  ): Promise<VideoSegment> =>
    request.put(`/videos/${id}`, data),

  exportVideos: (scriptId: number, exportType?: 'separate' | 'concatenated'): Promise<{ downloadUrl: string; expiresIn: number }> =>
    request.post('/videos/export', { scriptId, exportType: exportType || 'separate' }, { timeout: 900000 }),

  prepareAudioForExport: (scriptId: number): Promise<{ scriptId: number }> =>
    request.post(`/videos/script/${scriptId}/prepare-audio`, undefined, { timeout: 900000 })
}

// 文件管理API
export const fileApi = {
  uploadFile: (file: File, type?: string): Promise<FileUploadResponse> =>
    request.upload('/files/upload', file, {
      params: { type }
    }),

  getFileUrl: (fileId: number): Promise<{ url: string }> =>
    request.get(`/files/${fileId}/url`),

  deleteFile: (fileId: number): Promise<void> =>
    request.delete(`/files/${fileId}`)
}

// AI模型配置API
export const modelApi = {
  getScriptModels: (): Promise<{ code: number; message: string; data: { id: string; name: string; supports_web_search?: boolean; supportsWebSearch?: boolean }[] }> =>
    request.get('/models/script'),

  getScriptStyles: (): Promise<{ code: number; message: string; data: { id: string; name: string; description: string; usage?: string }[] }> =>
    request.get('/models/script-styles'),

  updateScriptStyles: (styles: { id: string; name: string; description: string; usage?: string }[]): Promise<{ code: number; message: string; data: { id: string; name: string; description: string; usage?: string }[] }> =>
    request.put('/models/script-styles', { styles }),

  getVideoModels: (): Promise<{ id: string; name: string; aspectRatios: string[]; qualities: string[] }[]> =>
    request.get('/models/video'),

  getImageModels: (): Promise<{
    code: number;
    message: string;
    data: {
      id: string;
      name: string;
      description: string;
      aspect_ratios: string[];
      qualities: string[];
      has_quality_selector: boolean;
      supports_reference: boolean;
    }[]
  }> =>
    request.get('/models/image'),

  getSegmentDurations: (): Promise<{ value: number; label: string }[]> =>
    request.get('/models/segment-durations')
}

// 系统配置API
export const configApi = {
  // 响应拦截器会返回 data.data，所以这里的类型是内层 data 的类型
  getScriptPrompt: (): Promise<{ prompt: string }> =>
    request.get('/config/script-prompt'),

  updateScriptPrompt: (prompt: string): Promise<{ prompt: string; updated_at: string }> =>
    request.put('/config/script-prompt', { prompt }),

  auditKfVideoRulesSnippet: (scriptId: number): Promise<{ changed: boolean; version?: number }> =>
    request.post('/config/kf-video-rules/audit', { scriptId })
}

// 热点情报API
export const hotspotApi = {
  getHotspots: (): Promise<{
    daily_summary: string
    hotspots: Array<{
      title: string
      track: string
      source: string
      angle: string
    }>
  }> =>
    request.get('/hotspots'),

  getHotspotDetail: (title: string): Promise<{
    title: string
    trust: {
      title: string
      content: string
      items?: string[]
    }
    conversion: {
      title: string
      content: string
      items?: string[]
    }
    structure: {
      title: string
      content: string
      items?: string[]
    }
    raw_content?: string
  }> =>
    // 热点详情会调用外部服务分析，可能需要较长时间；单独提高超时避免前端 30s 默认超时
    request.post('/hotspots/detail', { title }, { timeout: 600_000 })
}

// Medeo（后端代理）
export const medeoApi = {
  listRecipes: (params?: { limit?: number; order?: 'asc' | 'desc' }): Promise<any> =>
    request.get('/medeo/recipes', { params }),

  createMediaFromUrl: (data: { url: string; project_id?: string }): Promise<{ id: string; state: string; media_ids?: string[] }> =>
    request.post('/medeo/medias:create_from_url', data),

  getMediaCreationJob: (jobId: string): Promise<{ id: string; state: string; media_ids?: string[] }> =>
    request.get('/medeo/medias:create_medias_job', { params: { job_id: jobId } }),

  initiateProject: (data: {
    prompt: string
    settings: {
      duration_ms: number
      aspect_ratio: '16:9' | '9:16'
      recipe_id?: string
      voice_id?: string
      video_style_id?: string
      asset_sources?: string[]
    }
    media_ids?: string[]
  }): Promise<{ project_id: number; chat_session_id: string; video_draft_id: string; medeo_project_id: string }> =>
    request.post('/medeo/projects/initiate', data),

  getProject: (projectId: number): Promise<any> =>
    request.get(`/medeo/projects/${projectId}`),

  patchProject: (projectId: number, data: any): Promise<any> =>
    request.patch(`/medeo/projects/${projectId}`, data),

  getLastTaskStatus: (chatSessionId: string): Promise<{ status: string; video_draft_op_record_id?: string }> =>
    request.get(`/medeo/chat-sessions/${chatSessionId}/last-task-status`),

  createRenderJob: (videoDraftOpRecordId: string): Promise<any> =>
    request.post('/medeo/render-video-jobs', { video_draft_op_record_id: videoDraftOpRecordId }),

  queryRenderJob: (videoDraftOpRecordId: string): Promise<any> =>
    request.get('/medeo/render-video-jobs', { params: { video_draft_op_record_id: videoDraftOpRecordId } })
}
