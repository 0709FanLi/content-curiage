<template>
  <div class="reference-image-manager">
    <!-- 图片列表 -->
    <div v-if="images.length > 0" class="image-list">
      <div 
        v-for="(image, index) in images" 
        :key="index"
        class="image-item"
      >
        <img :src="image.url" :alt="`参考图 ${index + 1}`" />
        <div class="image-overlay">
          <el-button 
            circle 
            size="small"
            @click="handlePreview(image)"
          >
            <el-icon><ZoomIn /></el-icon>
          </el-button>
          <el-button 
            circle 
            size="small"
            type="danger"
            @click="handleRemove(index)"
          >
            <el-icon><Delete /></el-icon>
          </el-button>
        </div>
        <div class="image-index">{{ index + 1 }}</div>
      </div>
    </div>

    <!-- 上传按钮 -->
    <el-upload
      ref="uploadRef"
      :action="uploadUrl"
      :headers="uploadHeaders"
      :on-success="handleUploadSuccess"
      :on-error="handleUploadError"
      :before-upload="beforeUpload"
      :show-file-list="false"
      :multiple="true"
      :limit="maxImages"
      name="files"
      accept="image/jpeg,image/jpg,image/png,image/webp"
      :disabled="images.length >= maxImages"
      class="upload-section"
    >
      <el-button 
        type="primary" 
        :icon="Picture"
        :disabled="images.length >= maxImages"
        style="width: 100%;"
      >
        {{ buttonText }}
      </el-button>
    </el-upload>

    <!-- 图片预览对话框 -->
    <el-dialog
      v-model="previewVisible"
      :show-close="true"
      class="reference-preview-dialog"
      width="860px"
      align-center
      :append-to-body="true"
      :close-on-click-modal="true"
      :close-on-press-escape="true"
    >
      <div v-if="previewImage" class="preview-body">
        <div class="preview-meta">
          <div class="preview-title">
            {{ previewImage.filename || '参考图预览' }}
          </div>
          <div class="preview-subtitle">
            <span v-if="previewIndex !== null">第 {{ previewIndex + 1 }} 张</span>
            <span v-if="previewImage.size">&nbsp;·&nbsp;{{ formatBytes(previewImage.size) }}</span>
          </div>
        </div>

        <div class="preview-frame">
          <el-image
            :src="previewImage.url"
            fit="contain"
            class="preview-image"
          >
            <template #error>
              <div class="preview-error">图片加载失败</div>
            </template>
          </el-image>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage, ElLoading } from 'element-plus'
import { Picture, ZoomIn, Delete } from '@element-plus/icons-vue'
import type { UploadInstance, UploadRawFile } from 'element-plus'
import { useProjectStore } from '@/stores'

interface ReferenceImage {
  url: string
  filename: string
  size: number
}

interface Props {
  modelValue?: ReferenceImage[]
  maxImages?: number
  buttonText?: string
}

interface Emits {
  (e: 'update:modelValue', value: ReferenceImage[]): void
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: () => [],
  maxImages: 5,
  buttonText: '添加参考图'
})

const emit = defineEmits<Emits>()
const projectStore = useProjectStore()

// 数据
const uploadRef = ref<UploadInstance>()
// 从store中获取参考图，如果store中有数据则使用store的，否则使用props
const images = ref<ReferenceImage[]>(
  projectStore.referenceImageUrls.length > 0 
    ? projectStore.referenceImageUrls.map(url => ({ url, filename: '', size: 0 }))
    : [...props.modelValue]
)
const previewVisible = ref(false)
const previewImage = ref<ReferenceImage | null>(null)
const previewIndex = ref<number | null>(null)

const formatBytes = (bytes: number): string => {
  if (!bytes || bytes <= 0) return ''

  const units = ['B', 'KB', 'MB', 'GB']
  let size = bytes
  let unitIndex = 0

  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex += 1
  }

  const fixed = unitIndex === 0 ? 0 : 1
  return `${size.toFixed(fixed)} ${units[unitIndex]}`
}

// 计算属性
const uploadUrl = computed(() => {
  // 使用相对路径，让Vite的proxy处理
  const url = '/api/files/upload-reference-images'
  console.log('Upload URL:', url)
  return url
})

const uploadHeaders = computed(() => {
  const token = localStorage.getItem('accessToken')
  console.log('Token for upload:', token ? 'exists' : 'missing')
  if (!token) {
    ElMessage.error('未登录，请先登录')
    return {}
  }
  return {
    'Authorization': `Bearer ${token}`
  }
})

// Loading实例
let loadingInstance: any = null

// 方法
const beforeUpload = (rawFile: UploadRawFile) => {
  // 检查数量限制
  if (images.value.length >= props.maxImages) {
    ElMessage.warning(`最多只能上传${props.maxImages}张参考图`)
    return false
  }

  // 检查文件类型
  const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
  if (!allowedTypes.includes(rawFile.type)) {
    ElMessage.error('只支持 JPG、PNG、WEBP 格式的图片')
    return false
  }

  // 检查文件大小（限制10MB）
  const maxSize = 10 * 1024 * 1024
  if (rawFile.size > maxSize) {
    ElMessage.error('图片大小不能超过 10MB')
    return false
  }

  // 显示全局loading
  loadingInstance = ElLoading.service({
    lock: true,
    text: '正在上传参考图...',
    background: 'rgba(0, 0, 0, 0.7)'
  })

  return true
}

const handleUploadSuccess = (response: any) => {
  // 关闭loading
  if (loadingInstance) {
    loadingInstance.close()
    loadingInstance = null
  }

  if (response.code === 200 && response.data?.images) {
    const uploadedImages = response.data.images as ReferenceImage[]
    images.value.push(...uploadedImages)
    
    // 限制最大数量
    if (images.value.length > props.maxImages) {
      images.value = images.value.slice(0, props.maxImages)
    }
    
    // 同步到store
    projectStore.setReferenceImages(images.value.map(img => img.url))
    
    emit('update:modelValue', images.value)
    ElMessage.success(`成功上传 ${uploadedImages.length} 张图片`)
  } else {
    ElMessage.error('上传失败，请重试')
  }
}

const handleUploadError = (error: any) => {
  // 关闭loading
  if (loadingInstance) {
    loadingInstance.close()
    loadingInstance = null
  }

  console.error('上传失败:', error)
  ElMessage.error('上传失败，请重试')
}

const handlePreview = (image: ReferenceImage) => {
  previewImage.value = image
  const idx = images.value.findIndex(i => i.url === image.url)
  previewIndex.value = idx >= 0 ? idx : null
  previewVisible.value = true
}

const handleRemove = (index: number) => {
  images.value.splice(index, 1)
  
  // 同步到store
  projectStore.setReferenceImages(images.value.map(img => img.url))
  
  emit('update:modelValue', images.value)
  ElMessage.success('已删除')
}

// 暴露方法给父组件
defineExpose({
  clearImages: () => {
    images.value = []
    emit('update:modelValue', [])
  }
})
</script>

<style scoped>
.reference-image-manager {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 200px;
}

.upload-section {
  margin-top: auto;
}

.image-list {
  margin-top: 20px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 12px;
}

.image-item {
  position: relative;
  aspect-ratio: 16/9;
  border-radius: 8px;
  overflow: hidden;
  background: #f5f7fa;
  border: 2px solid #e4e7ed;
  cursor: pointer;
  transition: all 0.3s;
}

.image-item:hover {
  border-color: #00aaaa;
  box-shadow: 0 2px 8px rgba(0, 170, 170, 0.2);
}

.image-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.image-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  opacity: 0;
  transition: opacity 0.3s;
}

.image-item:hover .image-overlay {
  opacity: 1;
}

.image-index {
  position: absolute;
  top: 8px;
  left: 8px;
  background: rgba(0, 0, 0, 0.7);
  color: #fff;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
}

/* 预览弹框美化（在 scoped 下用 deep 影响 Element Plus 内部结构） */
:deep(.reference-preview-dialog) {
  --el-dialog-border-radius: 16px;
}

:deep(.reference-preview-dialog .el-dialog) {
  border-radius: 16px;
  overflow: hidden;
  background: linear-gradient(180deg, #0b1220 0%, #0f172a 100%);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.45);
}

:deep(.reference-preview-dialog .el-dialog__header) {
  margin-right: 0;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

:deep(.reference-preview-dialog .el-dialog__title) {
  color: rgba(255, 255, 255, 0.92);
  font-weight: 600;
}

:deep(.reference-preview-dialog .el-dialog__body) {
  padding: 16px;
}

.preview-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.preview-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.preview-title {
  font-size: 14px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.92);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.preview-subtitle {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.62);
}

.preview-frame {
  border-radius: 14px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  height: min(70vh, 640px);
  display: flex;
  align-items: center;
  justify-content: center;
}

.preview-image {
  width: 100%;
  height: 100%;
}

.preview-error {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(255, 255, 255, 0.7);
  font-size: 14px;
}

::deep(.el-upload) {
  width: 100%;
}
</style>
