// HTTP请求封装

import axios, { type AxiosInstance, type AxiosRequestConfig, type AxiosResponse } from 'axios'
import type { ApiResponse } from '@/types'

class Request {
  private instance: AxiosInstance

  constructor() {
    this.instance = axios.create({
      baseURL: import.meta.env.VITE_APP_API_BASE_URL || '/api',
      // 默认超时：避免接口卡死导致前端“永远等待”（长耗时接口在调用处单独提升超时）
      timeout: 30000, // 30秒
      headers: {
        'Content-Type': 'application/json'
      }
    })

    this.setupInterceptors()
  }

  private setupInterceptors() {
    // 请求拦截器
    this.instance.interceptors.request.use(
      (config) => {
        // 添加认证token
        const token = localStorage.getItem('accessToken')
        if (token) {
          config.headers.Authorization = `Bearer ${token}`
        }

        // 添加请求ID用于日志追踪
        config.headers['X-Request-ID'] = Date.now().toString()

        return config
      },
      (error) => {
        return Promise.reject(error)
      }
    )

    // 响应拦截器
    this.instance.interceptors.response.use(
      (response: AxiosResponse<any>) => {
        const { data } = response

        // 兼容：204 No Content（例如 DELETE 成功时后端无响应体）
        if (response.status === 204 || data === '' || data === null || data === undefined) {
          console.log('[Request Interceptor] 204/空响应体，直接视为成功:', {
            url: response.config?.url,
            status: response.status
          })
          return undefined
        }
        
        console.log('[Request Interceptor] 成功响应:', {
          url: response.config?.url,
          status: response.status,
          code: data.code,
          message: data.message,
          hasData: !!data.data
        })

        if (data.code === 200) {
          return data.data
        } else {
          console.log('[Request Interceptor] 业务错误:', {
            code: data.code,
            message: data.message
          })
          const error = new Error(data.message || '请求失败')
          ;(error as any).code = data.code
          return Promise.reject(error)
        }
      },
      (error) => {
        console.log('[Request Interceptor] 错误拦截:', {
          hasResponse: !!error.response,
          status: error.response?.status,
          url: error.config?.url,
          method: error.config?.method,
          data: error.response?.data
        })
        
        if (error.response) {
          const { status, data } = error.response

          switch (status) {
            case 401:
              // 未授权错误处理
              const currentPath = window.location.pathname
              const requestUrl = error.config?.url || error.config?.baseURL || ''
              const fullUrl = requestUrl.includes('http') ? requestUrl : (error.config?.baseURL || '') + requestUrl
              
              console.log('[Request Interceptor] 401 错误处理:', {
                currentPath,
                requestUrl,
                fullUrl,
                method: error.config?.method,
                responseData: data
              })
              
              // 检查是否是登录或注册接口
              const isAuthEndpoint = requestUrl.includes('/auth/login') || 
                                     requestUrl.includes('/auth/register') ||
                                     fullUrl.includes('/auth/login') ||
                                     fullUrl.includes('/auth/register')
              
              console.log('[Request Interceptor] 是否为认证端点:', isAuthEndpoint)
              
              // 如果是登录/注册接口的 401 错误，表示用户名或密码错误，应该返回原始错误消息
              if (isAuthEndpoint) {
                console.log('[Request Interceptor] 认证端点响应数据详情:', {
                  detail: data?.detail,
                  message: data?.message,
                  fullData: data
                })
                const errorMessage = data?.detail || data?.message || '用户名或密码错误'
                const authError = new Error(errorMessage)
                ;(authError as any).response = error.response
                ;(authError as any).config = error.config
                ;(authError as any).code = 401
                throw authError
              }
              
              // 对于其他API请求的401错误，表示token无效或过期
              // 清除token并跳转到登录页
              localStorage.removeItem('accessToken')
              localStorage.removeItem('refreshToken')
              
              // 如果当前不在登录页，跳转到登录页
              if (currentPath !== '/login' && currentPath !== '/register') {
                // 使用 window.location 跳转，确保token清除后立即跳转
                window.location.href = `/login?redirect=${encodeURIComponent(currentPath)}`
              }
              
              // 抛出错误，让调用方知道认证失败
              const authError = new Error('认证失败，请重新登录')
              ;(authError as any).response = error.response
              ;(authError as any).config = error.config
              ;(authError as any).code = 401
              throw authError
            case 403:
              throw new Error('权限不足')
            case 404:
              throw new Error('接口不存在')
            case 500:
              throw new Error('服务器内部错误')
            default:
              throw new Error(data?.message || `请求失败 (${status})`)
          }
        } else if (error.code === 'ECONNABORTED') {
          throw new Error('请求超时，请检查网络连接')
        } else {
          throw new Error('网络错误，请检查网络连接')
        }

        return Promise.reject(error)
      }
    )
  }

  public async get<T = any>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return this.instance.get(url, config)
  }

  public async post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return this.instance.post(url, data, config)
  }

  public async put<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return this.instance.put(url, data, config)
  }

  public async delete<T = any>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return this.instance.delete(url, config)
  }

  public async upload<T = any>(url: string, file: File, config?: AxiosRequestConfig): Promise<T> {
    const formData = new FormData()
    formData.append('file', file)

    return this.instance.post(url, formData, {
      ...config,
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  }
}

export const request = new Request()
export default request
