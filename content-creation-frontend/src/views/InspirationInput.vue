<template>
  <div class="ai-hotspot-page">
    <CommonLoading :visible="strategy_loading" text="正在分析热点策略..." />
    <!-- Header / Sidebar 已统一迁移到全局 MainContent（共用） -->
    <div class="page-body">
      <main class="landing">
        <div class="landing-center">
          <div class="card">
            <div class="card-head">
              <div class="card-title">输入创作指令</div>
              <div class="card-subtitle">
                描述您的创作需求，AI将为您生成专业内容
      </div>
    </div>

            <textarea
              v-model="inspiration"
              class="card-textarea"
              :placeholder="textarea_placeholder"
              @keydown.meta.enter.prevent="submit_generate_script"
              @keydown.ctrl.enter.prevent="submit_generate_script"
             
            />

            <div class="card-meta">
              <span class="meta-muted"
                >已输入 {{ inspiration_length }} 字</span
              >
      </div>

            <div class="form">
              <!-- 脚本风格 -->
              <div class="row">
                <div class="label">脚本风格</div>
                <div class="style-select-wrapper">
                  <div class="segmented">
                    <el-tooltip
                      v-for="s in style_options"
                      :key="s.id"
                      :content="s.usage || ''"
                      placement="top"
                      effect="dark"
                      :show-after="300"
                      :disabled="!s.usage"
                    >
                      <button
                        type="button"
                        class="pill"
                        :class="{ active: selected_style_id === s.id }"
                        @click="selected_style_id = s.id"
                      >
                        {{ s.name }}
                      </button>
                    </el-tooltip>
                  </div>
                  <el-button
                    type="default"
                    class="style-edit-button"
                    :icon="Edit"
                    circle
                    size="small"
                    @click="showStyleDialog"
                    title="编辑脚本风格"
                  />
                </div>
              </div>

              <!-- 模型 -->
              <div class="row row-tall">
                <div class="label">模型</div>
                <div class="model-pills">
                  <button
                    v-for="m in model_options"
                    :key="m.id"
                    type="button"
                    class="model"
                    :class="{ active: selected_model_id === m.id }"
                    @click="select_model(m.id)"
                  >
                    <div class="model-name">{{ m.display_name }}</div>
                    <div class="model-desc">{{ m.display_desc }}</div>
                  </button>
                </div>
              </div>

              <!-- 视频设置 -->
              <div class="row">
                <div class="label">视频设置</div>
                <div class="video-settings">
                  <div class="mini-label">比例</div>
                  <div class="segmented small">
                    <button
                      type="button"
                      class="pill small"
                      :class="{ active: aspect_ratio === '9:16' }"
                      @click="aspect_ratio = '9:16'"
                     
                    >
                      9:16
                    </button>
                    <button
                      type="button"
                      class="pill small"
                      :class="{ active: aspect_ratio === '16:9' }"
                      @click="aspect_ratio = '16:9'"
                     
                    >
                      16:9
                    </button>
                  </div>

                  <div class="duration">
                    <div class="mini-label">时长</div>
                    <div class="duration-input">
                      <input
                        v-model.number="total_duration"
                        type="number"
                        min="4"
                        step="1"
                      />
                      <span class="unit">秒</span>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 其他设置 -->
              <div class="row">
                <div class="label">其他设置</div>
                <div class="others">
                  <button
                    class="ref-btn"
                    type="button"
                    @click="open_reference_dialog"
                   
                  >
                    <img
                      class="ref-icon"
                      :src="uploadParametersIcon"
                      alt=""
                     
                    />
                    <span>参考图</span>
                  </button>
                  <!-- 测试环境出现 prompt 按钮，生产环境不出现 -->
                  <button v-if="isDevelopment" class="ref-btn prompt-btn" type="button" @click="showPromptDialog">
                    提示词
                  </button>

                  <label class="switch">
                    <input v-model="enable_search" type="checkbox" />
                    <span class="switch-ui">
                      <span class="switch-knob" />
                    </span>
                    <span class="switch-text"
                      >联网搜索</span
                    >
                  </label>
                </div>
              </div>
            </div>

            <div class="card-footer">
              <button
                class="btn secondary"
                type="button"
                :disabled="!can_submit"
                @click="submit_generate_script"
               
              >
                生成脚本
              </button>
              <button
                class="btn primary"
                type="button"
                :disabled="!can_submit"
                @click="submit_one_click"
               
              >
                <img
                  class="btn-icon"
                  :src="sendIcon"
                  alt=""
                 
                />
                一键生成
              </button>
            </div>
          </div>
        </div>
      </main>

      <!-- StrategyDetailPanel（右侧策略详情） -->
      <aside v-if="strategy_panel_visible" class="strategy">
      <div class="strategy-head">
        <div class="strategy-title">
          <img
            class="strategy-title-icon"
            :src="hotIcon"
            alt=""
           
          />
          <div class="strategy-title-text">
            {{ selected_hotspot_title || '—' }}
          </div>
        </div>
        <button
          class="strategy-close"
          type="button"
          @click="close_strategy_panel"
         
        >
          ×
        </button>
      </div>

      <div class="strategy-body">
        <div v-if="strategy_loading" class="strategy-loading">
          正在分析热点策略...
        </div>
        <template v-else>
          <div class="strategy-section">
            <div class="strategy-section-title">
              科学定律 (TRUST)
            </div>
            <div class="strategy-items">
              <div
                v-for="(t, idx) in trust_items"
                :key="'t-' + idx"
                class="strategy-item"
              >
                <div class="strategy-item-head">▸ {{ t.title }}</div>
                <div class="strategy-item-body">{{ t.content }}</div>
              </div>
            </div>
          </div>

          <div class="strategy-section">
            <div class="strategy-section-title">
              转化策略 (CONVERSION)
            </div>
            <div class="strategy-items">
              <div
                v-for="(c, idx) in conversion_items"
                :key="'c-' + idx"
                class="strategy-item"
              >
                <div class="strategy-item-head">▸ {{ c.title }}</div>
                <div class="strategy-item-body">{{ c.content }}</div>
      </div>
    </div>
          </div>
        </template>
      </div>

      <div class="strategy-footer">
        <button
          class="strategy-apply"
          type="button"
          :disabled="!strategy_detail"
          @click="apply_strategy"
         
        >
          应用此策略
        </button>
      </div>
      </aside>
    </div>

    <input
      ref="file_input_ref"
      class="hidden-file-input"
      type="file"
      accept="image/*"
      multiple
      @change="handle_reference_files"
    />

    <!-- ReferenceImageDialog（参考图管理弹窗，Figma: 16:2578） -->
    <div
      v-if="ref_dialog_open"
      class="ref-dialog-mask"
     
      @click.self="close_reference_dialog"
    >
      <div class="ref-dialog">
        <div class="ref-dialog-head">
          <div class="ref-dialog-title">管理参考图</div>
          <button
            class="ref-dialog-close"
            type="button"
           
            @click="close_reference_dialog"
          >
            ×
          </button>
        </div>

        <div class="ref-dialog-body">
          <div class="ref-help">
            <div class="ref-help-title">参考图说明</div>
            <ul class="ref-help-list">
              <li class="ref-help-item">
                参考图仅用于主调色和视觉风格，帮助AI理解您想要的画面风格
              </li>
              <li class="ref-help-item">
                建议上传2张参考图，支持JPG、PNG、WEBP格式（最多5张）
              </li>
              <li class="ref-help-item">
                建议上传竖版照片时默认调整比例的图片
              </li>
            </ul>
          </div>

          <button
            class="ref-upload-box"
            type="button"
            :disabled="uploading_reference"
           
            @click="pick_reference_images"
          >
            <div class="ref-upload-icon">
              <img
                class="ref-upload-icon-img"
                :src="uploadParametersIcon"
                alt=""
               
              />
            </div>
            <div class="ref-upload-text">
              {{ uploading_reference ? '上传中...' : '点击上传参考图' }}
            </div>
            <div class="ref-upload-sub">
              支持 JPG、PNG、WEBP 格式
            </div>
            <div class="ref-upload-counter">
              已上传 {{ reference_images.length }}/5
            </div>
          </button>

          <!-- 缩略图列表（设计图未包含，补齐“删除/清空”能力） -->
          <div v-if="reference_images.length > 0" class="ref-thumbs">
            <div class="ref-thumbs-head">
              <div class="ref-thumbs-title">已选参考图</div>
              <button
                class="ref-clear"
                type="button"
                :disabled="uploading_reference"
                @click="clear_reference_images"
              >
                清空
              </button>
            </div>
            <div class="ref-thumbs-grid">
              <div
                v-for="(url, idx) in reference_images"
                :key="url + idx"
                class="ref-thumb"
              >
                <img class="ref-thumb-img" :src="url" alt="" />
                <button
                  class="ref-thumb-del"
                  type="button"
                  :disabled="uploading_reference"
                  @click="remove_reference_image(idx)"
                  title="删除"
                >
                  ×
                </button>
              </div>
            </div>
          </div>

          <div class="ref-dialog-actions">
            <button
              class="ref-dialog-btn"
              type="button"
             
              @click="close_reference_dialog"
            >
              关闭
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 生成脚本 Loading（弹框式，主题色适配） -->
    <el-dialog
      v-model="script_loading_visible"
      class="script-loading-dialog"
      width="520px"
      align-center
      :show-close="false"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      :append-to-body="true"
    >
      <div class="script-loading-body">
        <div class="script-loading-icon" />
        <div class="script-loading-title">正在生成脚本</div>
        <div class="script-loading-sub">{{ script_loading_tip }}</div>
        <div class="script-loading-progress">
          <el-progress
            :percentage="Math.min(100, Math.max(0, Math.round(script_loading_progress)))"
            :stroke-width="10"
            :show-text="false"
            color="#2b7fff"
          />
          <div class="script-loading-meta">
            <span class="script-loading-meta-left">生成进度</span>
            <span class="script-loading-meta-right"
              >{{ Math.min(100, Math.max(0, Math.round(script_loading_progress))) }}%</span
            >
          </div>
        </div>
        <div class="script-loading-hint">预计用时 1-3 分钟</div>
      </div>
    </el-dialog>

    <!-- 提示词编辑弹窗（复用旧版 ScriptOptimization，不做主题适配） -->
    <el-dialog
      v-model="promptDialogVisible"
      title="编辑脚本生成提示词"
      width="70%"
      :close-on-click-modal="false"
      class="prompt-dialog"
    >
      <div class="prompt-dialog-content">
        <el-input
          v-model="promptContent"
          type="textarea"
          :rows="20"
          placeholder="请输入提示词模板..."
          class="prompt-textarea"
        />
        <div class="prompt-tips">
          <el-alert
            title="提示词支持以下变量（使用 {变量名} 格式）："
            type="info"
            :closable="false"
          >
            <template #default>
              <ul class="variable-list">
                <li><code>{total_duration}</code> - 视频总时长（秒）</li>
                <li><code>{segment_duration}</code> - 单个片段时长（秒）</li>
                <li><code>{segment_count}</code> - 片段数量</li>
                <li><code>{style}</code> - 脚本风格（兼容字段，通常等于风格说明）</li>
                <li><code>{style_name}</code> - 风格名称（用于逻辑判断/展示）</li>
                <li><code>{style_description}</code> - 风格说明（用于指导生成）</li>
                <li><code>{strategy_context}</code> - 核心策略输入（市场策略中心内容）</li>
                <li><code>{is_web_search_enabled}</code> - 联网开关 True/False（由前端强制控制）</li>
                <li><code>{current_date}</code> - 当前日期（如 2025年12月）</li>
                <li><code>{current_date_month}</code> - 当前月份（如 2025年12月）</li>
                <li><code>{current_date_year}</code> - 当前年份（如 2025）</li>
                <li><code>{content_length_min}</code> - 最小内容长度</li>
                <li><code>{content_length_max}</code> - 最大内容长度</li>
              </ul>
            </template>
          </el-alert>
        </div>
      </div>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="promptDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="savingPrompt" @click="savePrompt">
            保存
          </el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 风格编辑弹窗 -->
    <el-dialog
      v-model="styleDialogVisible"
      title="编辑脚本风格"
      width="70%"
      :close-on-click-modal="false"
      class="style-dialog"
    >
      <div class="style-dialog-content">
        <div class="style-list-header">
          <el-button
            type="primary"
            size="small"
            @click="addNewStyle"
          >
            <el-icon><Plus /></el-icon>
            新增风格
          </el-button>
        </div>
        <div class="style-list">
          <div
            v-for="(style, index) in editableStyles"
            :key="style.id"
            class="style-item"
          >
            <div class="style-item-header">
              <el-input
                v-model="style.name"
                placeholder="风格名称"
                class="style-name-input"
              />
              <el-button
                type="danger"
                size="small"
                :icon="Delete"
                circle
                @click="deleteStyle(index)"
                :disabled="editableStyles.length <= 1"
              />
            </div>
            <el-input
              v-model="style.description"
              type="textarea"
              :rows="4"
              placeholder="风格描述"
              class="style-description-input"
            />
            <el-input
              v-model="style.usage"
              type="textarea"
              :rows="2"
              placeholder="用途说明（可选，例如：适用场景：症状自查、红黑榜、避坑指南、食谱）"
              class="style-usage-input"
            />
          </div>
        </div>
        <div class="style-tips">
          <el-alert
            title="提示："
            type="info"
            :closable="false"
          >
            <template #default>
              <ul>
                <li>编辑风格的描述将影响脚本生成的方式，请确保描述清晰明确</li>
                <li>用途说明会在鼠标悬停时显示，帮助用户了解风格的适用场景</li>
                <li>至少保留一个风格</li>
              </ul>
            </template>
          </el-alert>
        </div>
      </div>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="styleDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="savingStyle" @click="saveStyles">
            保存
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Edit, Plus, Delete } from '@element-plus/icons-vue'

import { configApi, hotspotApi, modelApi, projectApi, scriptApi } from '@/api'
import { useProjectStore } from '@/stores'
import CommonLoading from '@/components/common/CommonLoading.vue'

import chevronIcon from '@/assets/icons/arrow-bottom.png'
import folderIcon from '@/assets/icons/folder.png'
import hotIcon from '@/assets/icons/light.png'
import logoIcon from '@/assets/icons/logo.png'
import sendIcon from '@/assets/icons/submit.png'
import startIcon from '@/assets/icons/submit.png'
import uploadParametersIcon from '@/assets/icons/upload_paramers.png'
import userIcon from '@/assets/icons/user.png'

type HotspotItem = {
  title: string
  track: string
  source: string
  angle: string
}

type HotspotDetailResponse = {
  title: string
  trust: { title: string; content: string }
  conversion: { title: string; content: string }
  structure: { title: string; content: string }
  raw_content?: string
}

const route = useRoute()
const router = useRouter()
const project_store = useProjectStore()

// 进入创意页时，清空上一次的参考图，避免状态串联
project_store.clearReferenceImages()

const textarea_placeholder =
  '请输入创作主题（如：赛道+痛点+策略），或直接描述您的大健康内容需求...'

// 页面状态
const inspiration = ref<string>('')
const total_duration = ref<number>(20)
const segment_duration = ref<number>(4)
const aspect_ratio = ref<'9:16' | '16:9'>('9:16')
const enable_search = ref<boolean>(false)

const isDevelopment = ref(false)
if (import.meta.env.MODE === 'development') {
  isDevelopment.value = true
}
// reference image dialog
const ref_dialog_open = ref<boolean>(false)
const uploading_reference = ref<boolean>(false)

// strategy panel（由共享 Sidebar 通过 route.query.hotspot 驱动）
const selected_hotspot_title = computed(() => {
  const title = String(route.query.hotspot || '').trim()
  return title || ''
})
const strategy_panel_visible = computed(() => Boolean(selected_hotspot_title.value))
const strategy_loading = ref<boolean>(false)
const strategy_detail = ref<HotspotDetailResponse | null>(null)

const trust_items = computed(() => {
  if (!strategy_detail.value) return []
  return [{ title: `"${strategy_detail.value.trust.title}"`, content: strategy_detail.value.trust.content }]
})

// prompt dialog (复用旧版)
const promptDialogVisible = ref(false)
const promptContent = ref('')
const savingPrompt = ref(false)

// style dialog
const styleDialogVisible = ref(false)
const savingStyle = ref(false)
const editableStyles = ref<{ id: string; name: string; description: string; usage?: string }[]>([])

const showPromptDialog = async () => {
  try {
    // 响应拦截器已返回 data.data，所以这里直接是 { prompt: "..." }
    const response = await configApi.getScriptPrompt()
    if (response && response.prompt) {
      promptContent.value = response.prompt
      promptDialogVisible.value = true
    } else {
      ElMessage.error('获取提示词失败')
    }
  } catch (error: any) {
    console.error('获取提示词失败:', error)
    ElMessage.error('获取提示词失败，请重试')
  }
}

const savePrompt = async () => {
  if (!promptContent.value.trim()) {
    ElMessage.warning('提示词不能为空')
    return
  }
  savingPrompt.value = true
  try {
    const response = await configApi.updateScriptPrompt(promptContent.value)
    if (response) {
      ElMessage.success('提示词保存成功')
      promptDialogVisible.value = false
    } else {
      ElMessage.error('保存失败')
    }
  } catch (error: any) {
    console.error('保存提示词失败:', error)
    ElMessage.error('保存提示词失败，请重试')
  } finally {
    savingPrompt.value = false
  }
}

// 显示风格编辑弹窗
const showStyleDialog = () => {
  // 加载所有风格（不仅仅是显示的4个）
  loadAllStylesForEdit()
}

// 加载所有风格用于编辑
const loadAllStylesForEdit = async () => {
  try {
    const resp: any = await modelApi.getScriptStyles()
    const styles = Array.isArray(resp) ? resp : resp?.data || []
    editableStyles.value = JSON.parse(JSON.stringify(styles))
    styleDialogVisible.value = true
  } catch (e) {
    console.error('加载脚本风格失败:', e)
    ElMessage.error('加载脚本风格失败')
  }
}

// 新增风格
const addNewStyle = () => {
  const timestamp = Date.now()
  const newStyle = {
    id: `custom_style_${timestamp}`,
    name: '',
    description: '',
    usage: ''
  }
  editableStyles.value.push(newStyle)
  ElMessage.success('已添加新风格，请编辑后保存')
}

// 删除风格
const deleteStyle = async (index: number) => {
  if (editableStyles.value.length <= 1) {
    ElMessage.warning('至少需要保留一个风格')
    return
  }

  try {
    await ElMessageBox.confirm(
      '确定要删除这个风格吗？删除后无法恢复。',
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    editableStyles.value.splice(index, 1)
    ElMessage.success('风格已删除，请点击保存按钮确认')
  } catch {
    // 用户取消删除
  }
}

// 保存风格
const saveStyles = async () => {
  // 验证风格数据
  for (const style of editableStyles.value) {
    if (!style.name || !style.name.trim()) {
      ElMessage.warning('风格名称不能为空')
      return
    }
    if (!style.description || !style.description.trim()) {
      ElMessage.warning('风格描述不能为空')
      return
    }
  }

  savingStyle.value = true
  try {
    // 调用API保存风格
    await modelApi.updateScriptStyles(editableStyles.value)
    
    // 重新加载风格列表
    await load_styles()
    
    ElMessage.success('风格保存成功')
    styleDialogVisible.value = false
  } catch (error: any) {
    console.error('保存风格失败:', error)
    ElMessage.error('保存风格失败，请重试')
  } finally {
    savingStyle.value = false
  }
}

const conversion_items = computed(() => {
  if (!strategy_detail.value) return []
  return [
    {
      title: `"${strategy_detail.value.conversion.title}"`,
      content: strategy_detail.value.conversion.content
    }
  ]
})

// form options
const style_options = ref<Array<{ id: string; name: string; usage?: string }>>([])
const selected_style_id = ref<string>('')
const model_options = ref<
  Array<{ id: string; display_name: string; display_desc: string }>
>([])
const selected_model_id = ref<string>('')

const inspiration_length = computed(() => inspiration.value.trim().length)
const can_submit = computed(() => inspiration.value.trim().length > 0)

// script loading dialog
const script_loading_visible = ref<boolean>(false)
const script_loading_progress = ref<number>(0)
const script_loading_tip = ref<string>('AI 正在分析您的创意…')
let script_loading_timer: ReturnType<typeof setInterval> | null = null

const start_script_loading = () => {
  script_loading_visible.value = true
  script_loading_progress.value = 0
  const tips = [
    'AI 正在分析您的创意…',
    '正在匹配风格与结构…',
    '正在生成分段与关键帧描述…',
    '正在校验格式与时长…'
  ]
  let tip_idx = 0
  if (script_loading_timer) clearInterval(script_loading_timer)
  script_loading_timer = setInterval(() => {
    // 进度条到 90% 停住，等接口返回再结束
    if (script_loading_progress.value < 90) {
      script_loading_progress.value = Math.min(
        90,
        script_loading_progress.value + 4 + Math.random() * 8
      )
    }
    tip_idx = (tip_idx + 1) % tips.length
    script_loading_tip.value = tips[tip_idx]
  }, 800)
}

const stop_script_loading = () => {
  if (script_loading_timer) {
    clearInterval(script_loading_timer)
    script_loading_timer = null
  }
  script_loading_progress.value = 100
  script_loading_tip.value = '生成完成！'
  // 轻微延迟，避免闪烁
  setTimeout(() => {
    script_loading_visible.value = false
  }, 250)
}

const reference_images = computed(() => {
  return project_store.referenceImageUrls || []
})

const open_reference_dialog = () => {
  ref_dialog_open.value = true
}

const close_reference_dialog = () => {
  ref_dialog_open.value = false
}

const close_strategy_panel = async () => {
  strategy_detail.value = null
  await router.replace({
    name: 'InspirationInput',
    query: {
      ...route.query,
      hotspot: undefined
    }
  })
}

const apply_strategy = () => {
  if (!strategy_detail.value) return
  const content = `
# ${strategy_detail.value.title}

## ${strategy_detail.value.trust.title}
${strategy_detail.value.trust.content}

## ${strategy_detail.value.conversion.title}
${strategy_detail.value.conversion.content}

## ${strategy_detail.value.structure.title}
${strategy_detail.value.structure.content}
  `.trim()
  inspiration.value = content
  ElMessage.success('策略已应用到输入框')
  // 关闭详情弹框
  close_strategy_panel()
}

const load_styles = async () => {
  try {
    const resp: any = await modelApi.getScriptStyles()
    const styles = Array.isArray(resp) ? resp : resp?.data || []

    const prefer_names = ['产品种草文案', '科普知识', '故事叙述', '教程讲解']
    const picked: Array<{ id: string; name: string; usage?: string }> = []
    for (const n of prefer_names) {
      const found = styles.find((s: any) => s?.name === n)
      if (found) picked.push({ id: found.id, name: found.name, usage: found.usage })
    }
    if (picked.length < 4) {
      for (const s of styles) {
        if (picked.length >= 4) break
        if (!picked.some(x => x.id === s.id)) {
          picked.push({ id: s.id, name: s.name, usage: s.usage })
        }
      }
    }
    style_options.value = picked
    if (!selected_style_id.value && picked.length > 0) {
      selected_style_id.value = picked[0].id
    }
  } catch (e) {
    console.error('加载脚本风格失败:', e)
  }
}

const load_models = async () => {
  try {
    const resp: any = await modelApi.getScriptModels()
    const models = Array.isArray(resp) ? resp : resp?.data || []

    // 需求：只展示 deepseek-reasoner / kimi-k2-thinking
    const display_map: Record<
      string,
      { short: string; feature: string }
    > = {
      'deepseek-reasoner': { short: 'DeepSeek', feature: '专家硬核科普' },
      'kimi-k2-thinking': { short: 'Kimi', feature: '爆款网感模式' }
    }

    const picked: Array<{ id: string; display_name: string; display_desc: string }> =
      []

    for (const m of models) {
      const id = String(m?.id || '')
      const mapped = display_map[id]
      if (!mapped) continue
      picked.push({
        id,
        display_name: mapped.short,
        display_desc: mapped.feature
      })
    }

    model_options.value = picked
    if (!selected_model_id.value && model_options.value.length > 0) {
      selected_model_id.value = model_options.value[0].id
    }
  } catch (e) {
    console.error('加载脚本模型失败:', e)
  }
}

const select_model = (id: string) => {
  selected_model_id.value = id
}

// reference images
const file_input_ref = ref<HTMLInputElement | null>(null)

const pick_reference_images = () => {
  file_input_ref.value?.click()
}

const upload_reference_images = async (files: File[]): Promise<string[]> => {
  const token = localStorage.getItem('accessToken')
  if (!token) {
    throw new Error('未登录，请先登录')
}

  const form = new FormData()
  for (const f of files) {
    form.append('files', f)
  }

  const resp = await fetch('/api/files/upload-reference-images', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`
    },
    body: form
  })

  if (!resp.ok) {
    const text = await resp.text()
    throw new Error(text || `上传失败 (${resp.status})`)
  }

  const json: any = await resp.json()
  if (json?.code !== 200) {
    throw new Error(json?.message || '上传失败')
  }

  const images = json?.data?.images || []
  const urls = images.map((x: any) => x?.url).filter(Boolean)
  return urls
}

const handle_reference_files = async (evt: Event) => {
  const input = evt.target as HTMLInputElement
  const files = input.files
  if (!files || files.length === 0) return

  try {
    const current_count = reference_images.value.length
    if (current_count >= 5) {
      ElMessage.warning('最多上传 5 张参考图')
    return
  }

    const selected = Array.from(files)
    const available_slots = Math.max(0, 5 - current_count)
    const files_to_upload = selected.slice(0, available_slots)
    if (selected.length > files_to_upload.length) {
      ElMessage.warning('最多上传 5 张参考图，已自动截取前 5 张')
    }

    uploading_reference.value = true
    const urls = await upload_reference_images(files_to_upload)
    if (urls.length > 0) {
      project_store.setReferenceImages([...reference_images.value, ...urls])
      ElMessage.success(`已添加 ${urls.length} 张参考图`)
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '上传参考图失败')
  } finally {
    uploading_reference.value = false
    input.value = ''
  }
}

const remove_reference_image = (index: number) => {
  const next = [...reference_images.value]
  next.splice(index, 1)
  project_store.setReferenceImages(next)
}

const clear_reference_images = () => {
  project_store.clearReferenceImages()
}

const build_generate_request = (generation_mode: 'step_by_step' | 'one_click') => {
  return {
    inspiration: inspiration.value.trim(),
    style: selected_style_id.value,
    totalDuration: total_duration.value,
    segmentDuration: segment_duration.value,
    generationMode: generation_mode,
    referenceImageUrls: project_store.referenceImageUrls,
    enableSearch: enable_search.value
  }
}

const submit_generate_script = async () => {
  if (!can_submit.value) return
  start_script_loading()
  try {
    const data: any = await scriptApi.generateScript(
      build_generate_request('step_by_step'),
      selected_model_id.value
    )
    const project_id = data?.projectId
    if (project_id) {
      // 开发/调试可观测：把本次生成脚本的返回（含 visionAnalysis）写入 store，
      // 这样跳转到脚本页后也能看到“参考图解析是否用到”的状态。
      try {
        const project = await projectApi.getProject(project_id)
        const project_with_script = project as any
        if (project_with_script.scripts && Array.isArray(project_with_script.scripts) && project_with_script.scripts.length > 0) {
          project_with_script.script = project_with_script.scripts[0]
        }
        // 兜底：后端 project 详情未必包含本次生成返回的 meta，优先用 data 覆盖
        project_with_script.script = { ...(project_with_script.script || {}), ...(data || {}) }
        project_store.setCurrentProject(project_with_script)
        project_store.addProject(project_with_script)
      } catch (e) {
        console.warn('同步项目到 store 失败（不影响跳转）:', e)
      }
      stop_script_loading()
      await router.push({ path: `/project/${project_id}/script` })
    }
  } catch (e: any) {
    script_loading_visible.value = false
    ElMessage.error(e?.message || '脚本生成失败')
  }
}

const submit_one_click = async () => {
  if (!can_submit.value) return
  try {
    // 立即跳转到“一键生成”页面，在该页面展示 loading 并等待脚本生成
    // 由 OneClickGenerateView 内部的 autoStart 流程创建项目并开始生成，避免创意页“无反应”的体验
    const request = build_generate_request('one_click')
    await router.push({
      name: 'OneClickGenerate',
      params: { projectId: 'new' },
      query: {
        autoStart: 'true',
        inspiration: request.inspiration,
        style: request.style,
        totalDuration: String(request.totalDuration),
        segmentDuration: String(request.segmentDuration),
        aspectRatio: aspect_ratio.value,
        enableSearch: String(!!request.enableSearch),
        model: selected_model_id.value,
      },
    })
  } catch (e: any) {
    ElMessage.error(e?.message || '一键生成失败')
  }
}

onMounted(async () => {
  await Promise.all([load_styles(), load_models()])
})

onUnmounted(() => {
  if (script_loading_timer) {
    clearInterval(script_loading_timer)
    script_loading_timer = null
  }
})

watch(
  selected_hotspot_title,
  async (title: string) => {
    if (!title) {
      strategy_detail.value = null
      return
    }
    strategy_loading.value = true
    strategy_detail.value = null
    try {
      strategy_detail.value = await hotspotApi.getHotspotDetail(title)
    } catch (e: any) {
      ElMessage.error(e?.message || '加载热点详情失败')
    } finally {
      strategy_loading.value = false
    }
  },
  { immediate: true }
)
</script>

<style scoped>
/* layout */
.ai-hotspot-page {
  width: 100%;
  height: 100%;
  background: #f3f4f6;
  overflow: hidden;
}

/* 生成脚本 loading dialog */
.script-loading-dialog :deep(.el-dialog) {
  border-radius: 14px;
  overflow: hidden;
}

.script-loading-dialog :deep(.el-dialog__header) {
  display: none;
}

.script-loading-dialog :deep(.el-dialog__body) {
  padding: 0;
}

.script-loading-body {
  padding: 28px 28px 22px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  background: #ffffff;
}

.script-loading-icon {
  width: 64px;
  height: 64px;
  border-radius: 999px;
  background: linear-gradient(180deg, #2b7fff 0%, #00b8db 100%);
  position: relative;
  margin-bottom: 6px;
}

.script-loading-icon::after {
  content: '';
  position: absolute;
  inset: 12px;
  border-radius: 999px;
  border: 4px solid #ffffff;
  border-left-color: transparent;
  border-bottom-color: transparent;
  animation: script-spin 1.2s linear infinite;
}

@keyframes script-spin {
  to {
    transform: rotate(360deg);
  }
}

.script-loading-title {
  font-size: 18px;
  font-weight: 600;
  color: #1e2939;
  line-height: 26px;
}

.script-loading-sub {
  font-size: 14px;
  color: #6a7282;
  line-height: 20px;
}

.script-loading-progress {
  width: 100%;
  margin-top: 8px;
}

.script-loading-meta {
  margin-top: 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.script-loading-meta-left {
  font-size: 13px;
  color: #6a7282;
}

.script-loading-meta-right {
  font-size: 13px;
  font-weight: 600;
  color: #2b7fff;
}

.script-loading-hint {
  margin-top: 4px;
  font-size: 12px;
  color: #99a1af;
}

.page-body {
  height: 100%;
  display: flex;
  align-items: stretch;
  overflow: hidden;
}

.sidebar-start-text {
  font-size: 14px;
  font-weight: 500;
}

.sidebar-body {
  flex: 1;
  padding: 16px;
  overflow: hidden;
}

.sidebar-scroll {
  height: 100%;
  overflow: auto;
}

.panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.panel + .panel {
  margin-top: 16px;
}

.panel-header {
  width: 100%;
  height: 45px;
  background: #ffffff;
  border: 1px solid #f3f4f6;
  border-radius: 10px;
  padding: 0 13px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
}

.panel-title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.panel-title-icon {
  width: 16px;
  height: 16px;
}

.panel-title-text {
  font-size: 12px;
  font-weight: 500;
  color: #1e2939;
}

.panel-hot-tag {
  height: 19px;
  padding: 0 6px;
  border-radius: 4px;
  background: #fb2c36;
  color: #ffffff;
  font-size: 10px;
  line-height: 19px;
  font-weight: 500;
}

.panel-count {
  height: 19px;
  padding: 0 6px;
  border-radius: 4px;
  background: #e5e7eb;
  color: #364153;
  font-size: 10px;
  line-height: 19px;
  font-weight: 500;
}

.panel-chevron {
  width: 14px;
  height: 14px;
  transition: transform 0.15s ease;
}

.panel-chevron.open {
  transform: rotate(180deg);
}

.panel-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.hotspot-card {
  background: #ffffff;
  border: 1px solid #f3f4f6;
  border-radius: 10px;
  padding: 13px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  cursor: pointer;
  text-align: left;
}

.hotspot-card.active {
  outline: 2px solid rgba(43, 127, 255, 0.35);
}

.hotspot-card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 500;
  color: #1e2939;
}

.hotspot-emoji {
  color: #2b7fff;
}

.hotspot-tags {
  display: flex;
  gap: 6px;
}

.tag {
  font-size: 10px;
  color: #2b7fff;
  background: #dbeafe;
  border-radius: 4px;
  padding: 2px 8px;
}

.hotspot-desc {
  font-size: 11px;
  line-height: 1.6;
  color: #6a7282;
}

.hotspot-footnote {
  font-size: 10px;
  color: #99a1af;
}

.recent-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.recent-card {
  background: #ffffff;
  border: 1px solid #f3f4f6;
  border-radius: 10px;
  padding: 13px;
  display: flex;
  gap: 12px;
  cursor: pointer;
  text-align: left;
}

.recent-card-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f3f4f6;
}

.recent-card-icon img {
  width: 16px;
  height: 16px;
  opacity: 0.9;
}

.recent-card-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.recent-card-title {
  font-size: 12px;
  font-weight: 600;
  color: #1e2939;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.recent-card-desc {
  font-size: 12px;
  color: #6a7282;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.recent-card-time {
  font-size: 12px;
  color: #6a7282;
}

.landing {
  flex: 1;
  background: #f3f4f6;
  overflow: auto;
  position: relative;
}

.landing-center {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  box-sizing: border-box;
}

.card {
  width: 896px;
  height: 727px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px -1px rgba(0, 0, 0, 0.1);
  padding: 24px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
}

.card-head {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.card-title {
  font-size: 18px;
  font-weight: 600;
  color: #1e2939;
  line-height: 28px;
}

.card-subtitle {
  font-size: 14px;
  color: #6a7282;
  line-height: 20px;
}

.card-textarea {
  margin-top: 24px;
  height: 160px;
  width: 100%;
  border: none;
  border-radius: 8px;
  background: #f3f3f5;
  padding: 24px;
  box-sizing: border-box;
  font-size: 14px;
  line-height: 20px;
  color: #364153;
  resize: none;
  outline: none;
}

.card-meta {
  margin-top: 20px;
  display: flex;
  align-items: center;
  gap: 8px;
  height: 16px;
}

.meta-muted {
  font-size: 12px;
  color: #99a1af;
}

.meta-sep {
  font-size: 12px;
  color: #d1d5dc;
}

.form {
  margin-top: 48px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.row {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.row-tall {
  align-items: center;
}

.label {
  width: 96px;
  font-size: 14px;
  color: #6a7282;
  padding-top: 8px;
  box-sizing: border-box;
  flex: 0 0 96px;
}

.style-select-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;
}

.segmented {
  display: inline-flex;
  gap: 8px;
  flex-wrap: nowrap;
}

.style-edit-button {
  width: 32px;
  height: 32px;
  padding: 0;
  background-color: #f3f4f6;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  color: #6a7282;
  flex-shrink: 0;
  transition: all 0.3s;
}

.style-edit-button:hover {
  border-color: #2b7fff;
  color: #2b7fff;
  background-color: #ffffff;
}

.pill {
  height: 36px;
  padding: 0 16px;
  border-radius: 10px;
  border: none;
  background: #f3f4f6;
  color: #364153;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
}

.pill.active {
  background: linear-gradient(180deg, #2b7fff 0%, #00b8db 100%);
  color: #ffffff;
}

.pill.small {
  height: 32px;
  border-radius: 8px;
}

.model-pills {
  display: flex;
  gap: 8px;
}

.model {
  width: 92px;
  height: 54px;
  border-radius: 10px;
  border: none;
  background: #f3f4f6;
  cursor: pointer;
  padding: 8px 16px;
  box-sizing: border-box;
  display: flex;
    flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
}

.model.active {
  background: linear-gradient(180deg, #2b7fff 0%, #00b8db 100%);
  color: #ffffff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px -1px rgba(0, 0, 0, 0.1);
}

.model-name {
  font-size: 14px;
  font-weight: 500;
  color: inherit;
  line-height: 20px;
}

.model-desc {
  font-size: 12px;
  font-weight: 500;
  opacity: 0.9;
  color: inherit;
  line-height: 16px;
  white-space: nowrap;
}

.video-settings {
  display: flex;
  align-items: center;
  gap: 16px;
  height: 34px;
}

.mini-label {
  font-size: 12px;
  color: #6a7282;
}

.duration {
  display: flex;
  align-items: center;
  gap: 8px;
}

.duration-input {
  width: 80px;
  height: 34px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  background: #f3f4f6;
  display: flex;
  align-items: center;
  padding: 0 12px;
  box-sizing: border-box;
  gap: 6px;
}

.duration-input input {
    width: 100%;
  border: none;
  outline: none;
  background: transparent;
  font-size: 14px;
  color: rgba(54, 65, 83, 0.8);
}

.unit {
  font-size: 12px;
  color: #6a7282;
}

.others {
  display: flex;
  align-items: center;
  gap: 16px;
  height: 36px;
}

.ref-btn {
  height: 36px;
  padding: 0 16px;
  border-radius: 10px;
  border: none;
  background: #f3f4f6;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: #364153;
  font-size: 14px;
  font-weight: 500;
}

.ref-icon {
  width: 16px;
  height: 16px;
}

.switch {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
}

.switch input {
  display: none;
}

.switch-ui {
  width: 32px;
  height: 18.39px;
  border-radius: 9999px;
  background: #cbced4;
  display: inline-flex;
  align-items: center;
  padding: 1px;
  box-sizing: border-box;
  transition: background 0.15s ease;
}

.switch-knob {
  width: 16px;
  height: 16px;
  border-radius: 9999px;
  background: #ffffff;
  transform: translateX(0);
  transition: transform 0.15s ease;
}

.switch input:checked + .switch-ui {
  background: linear-gradient(180deg, #2b7fff 0%, #00b8db 100%);
}

.switch input:checked + .switch-ui .switch-knob {
  transform: translateX(14px);
}

.switch-text {
  font-size: 14px;
  color: #364153;
}

.card-footer {
  margin-top: auto;
  height: 57px;
  border-top: 1px solid #f3f4f6;
  padding-top: 17px;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.btn {
  height: 40px;
  border-radius: 8px;
  border: 1px solid #d1d5dc;
  background: #ffffff;
  padding: 0 25px;
  font-size: 14px;
  font-weight: 500;
  color: #364153;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.btn.primary {
  border: none;
  color: #ffffff;
  background: linear-gradient(180deg, #2b7fff 0%, #00b8db 100%);
  width: 112px;
  padding: 0 12px;
  justify-content: flex-start;
}


.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-icon {
  width: 16px;
  height: 16px;
}

/* right strategy panel */
.strategy {
  position: relative;
  margin: 24px 16px 16px 0;
  width: 420px;
  height: 645px;
  border-radius: 10px;
  overflow: hidden;
  background: linear-gradient(180deg, #8b5cf6 0%, #6366f1 100%);
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
  display: flex;
  flex-direction: column;
}

.strategy-head {
  height: 72px;
  padding: 0 16px;
  background: rgba(43, 127, 255, 0.7);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.strategy-title {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
    flex: 1;
  }

.strategy-title-icon {
  width: 16px;
  height: 16px;
}

.strategy-title-text {
  font-size: 14px;
  font-weight: 700;
  color: #ffffff;
  line-height: 20px;
  max-height: 40px;
  overflow: hidden;
}

.strategy-close {
  width: 20px;
  height: 20px;
  border: none;
  background: transparent;
  color: #ffffff;
  font-size: 18px;
  cursor: pointer;
}

.strategy-body {
  background: #ffffff;
  padding: 20px 35px 0 20px;
  height: 500px;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.strategy-loading {
  font-size: 14px;
  color: #6a7282;
}

.strategy-section-title {
  font-size: 14px;
  font-weight: 600;
  color: #1e2939;
  display: flex;
  align-items: center;
  gap: 8px;
}

.strategy-items {
  margin-top: 12px;
  margin-left: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.strategy-item-head {
  font-size: 12px;
  font-weight: 500;
  color: #364153;
}

.strategy-item-body {
  margin-top: 6px;
  font-size: 12px;
  line-height: 19.5px;
  color: #6a7282;
  white-space: pre-wrap;
}

.strategy-footer {
  height: 73px;
  background: #ffffff;
  border-top: 1px solid #f3f4f6;
  padding: 17px 16px 0 16px;
  box-sizing: border-box;
}

.strategy-apply {
  width: 100%;
  height: 40px;
  border-radius: 8px;
  border: none;
  cursor: pointer;
  color: #ffffff;
  font-size: 14px;
  font-weight: 500;
  background: linear-gradient(180deg, #2b7fff 0%, #00b8db 100%);
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1);
}

.strategy-apply:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.hidden-file-input {
  display: none;
}

/* reference image dialog */
.ref-dialog-mask {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
}

.ref-dialog {
  width: 672px;
  background: #ffffff;
  border-radius: 10px;
  box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.ref-dialog-head {
  height: 57px;
  border-bottom: 1px solid #e5e7eb;
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.ref-dialog-title {
  font-size: 16px;
  font-weight: 600;
  color: #1e2939;
}

.ref-dialog-close {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  font-size: 22px;
  line-height: 28px;
  cursor: pointer;
  color: #6a7282;
}

.ref-dialog-body {
  padding: 20px 24px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.ref-help-title {
  font-size: 14px;
  font-weight: 500;
  color: #1e2939;
  margin-bottom: 8px;
}

.ref-help-list {
  margin: 0;
  padding-left: 18px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ref-help-item {
  font-size: 12px;
  color: #6a7282;
  line-height: 16px;
  }

.ref-help-item::marker {
  color: #2b7fff;
}

.ref-upload-box {
  width: 624px;
  height: 188px;
  border-radius: 10px;
  border: 2px solid #d1d5dc;
  background: #f9fafb;
  display: flex;
    flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  cursor: pointer;
  align-self: flex-start;
  }

.ref-upload-box:disabled {
  cursor: not-allowed;
  opacity: 0.75;
}

.ref-upload-icon {
  width: 64px;
  height: 64px;
  border-radius: 9999px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(180deg, #2b7fff 0%, #00b8db 100%);
  margin-bottom: 10px;
}

.ref-upload-icon-img {
  width: 32px;
  height: 32px;
}

.ref-upload-text {
  font-size: 14px;
  font-weight: 500;
  color: #1e2939;
  line-height: 20px;
}

.ref-upload-sub {
  font-size: 12px;
  font-weight: 500;
  color: #6a7282;
  line-height: 16px;
}

.ref-upload-counter {
  margin-top: 6px;
  font-size: 12px;
  color: #99a1af;
}

.ref-thumbs {
  width: 624px;
  align-self: flex-start;
}

.ref-thumbs-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.ref-thumbs-title {
  font-size: 13px;
  font-weight: 600;
  color: #1e2939;
}

.ref-clear {
  border: none;
  background: transparent;
  color: #2b7fff;
  font-size: 12px;
  cursor: pointer;
}

.ref-clear:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.ref-thumbs-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 10px;
}

.ref-thumb {
  position: relative;
    width: 100%;
  padding-top: 100%;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid #e5e7eb;
  background: #f3f4f6;
}

.ref-thumb-img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.ref-thumb-del {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 22px;
  height: 22px;
  border-radius: 9999px;
  border: none;
  color: #ffffff;
  background: rgba(0, 0, 0, 0.55);
  cursor: pointer;
  line-height: 22px;
}

.ref-thumb-del:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.ref-dialog-actions {
  margin-top: auto;
  display: flex;
  justify-content: flex-end;
}

.ref-dialog-btn {
  width: 76px;
  height: 36px;
  border-radius: 8px;
  border: none;
  cursor: pointer;
  color: #ffffff;
  font-size: 14px;
  font-weight: 500;
  background: linear-gradient(180deg, #2b7fff 0%, #00b8db 100%);
}

/* 风格编辑弹窗样式 */
.style-dialog :deep(.el-dialog__body) {
  padding: 20px;
}

.style-dialog-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.style-list-header {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 12px;
}

.style-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
  max-height: 500px;
  overflow-y: auto;
  padding: 10px;
}

.style-item {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 16px;
  background-color: #f9f9f9;
  transition: all 0.3s;
}

.style-item:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.style-item-header {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 12px;
}

.style-name-input {
  flex: 1;
}

.style-name-input :deep(.el-input__wrapper) {
  font-weight: 600;
  font-size: 14px;
}

.style-description-input {
  margin-top: 12px;
}

.style-usage-input {
  margin-top: 12px;
}

.style-tips {
  margin-top: 8px;
}

.style-tips ul {
  margin: 8px 0 0 0;
  padding-left: 20px;
  list-style: disc;
}

.style-tips li {
  margin: 4px 0;
  font-size: 13px;
  line-height: 1.6;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
