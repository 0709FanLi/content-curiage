<template>
  <div class="medeo-start">
    <section class="hero">
      <div class="hero-sub">Make great videos by chatting with AI</div>
      <div class="hero-title">One Click to <span class="hero-em">Pro Videos</span></div>

      <div class="composer">
        <div class="composer-inner">
          <textarea
            v-model="prompt"
            class="composer-input"
            rows="2"
            placeholder="Ask Medeo to create a high-energy commercial..."
          />

          <div v-if="assetItems.length > 0" class="asset-rail">
            <div class="asset-rail-title">Assets</div>
            <div class="asset-rail-list">
              <button v-for="a in assetItems" :key="a.id" class="asset-card" type="button" @click="openAssetPreview(a)">
                <img v-if="a.kind === 'image'" class="asset-thumb" :src="a.previewUrl" alt="asset" />
                <video
                  v-else
                  class="asset-thumb"
                  :src="a.previewUrl"
                  muted
                  playsinline
                  preload="metadata"
                  @loadedmetadata="onVideoMeta(a.id, $event)"
                />
                <div v-if="a.kind === 'video' && formatDuration(a.durationSec)" class="asset-duration">
                  {{ formatDuration(a.durationSec) }}
                </div>
                <div v-if="a.status !== 'done'" class="asset-mask">
                  <div class="asset-mask-text">
                    {{ a.status === 'uploading' ? 'Uploading…' : a.status === 'processing' ? 'Processing…' : 'Failed' }}
                  </div>
                </div>
                <button class="asset-del" type="button" title="Remove" @click.stop="removeAsset(a.id)">×</button>
              </button>
            </div>
            <div v-if="uploadingAssets" class="asset-rail-hint">正在上传并创建 Medeo media…</div>
          </div>

          <div class="composer-bar">
            <div class="bar-left">
              <button
                class="pill pill-icon"
                type="button"
                title="Add files & URL"
                :disabled="uploadingAssets"
                @click="pick_asset_files"
              >
                <span class="pill-plus">＋</span>
              </button>
              <input
                ref="assetFileInputRef"
                class="asset-file-input"
                type="file"
                accept="image/*,video/*"
                multiple
                @change="handle_asset_files"
              />

              <button class="pill" type="button" @click="toggleAspect">
                <span class="pill-label">{{ aspectRatio }}</span>
              </button>

              <el-popover
                v-model:visible="moreOpen"
                placement="bottom-start"
                :width="560"
                trigger="click"
                popper-class="medeo-more-popper"
              >
                <template #reference>
                  <button class="pill pill-ghost" type="button">
                    <span class="pill-label">More</span>
                  </button>
                </template>

                <div class="more">
                  <div class="more-left">
                    <button
                      v-for="s in moreSections"
                      :key="s.key"
                      class="more-item"
                      :class="{ active: activeSection === s.key }"
                      type="button"
                      @click="activeSection = s.key"
                    >
                      <span class="more-item-icon">{{ s.icon }}</span>
                      <span class="more-item-text">{{ s.label }}</span>
                      <span class="more-item-arrow">›</span>
                    </button>
                  </div>
                  <div class="more-right">
                    <div v-if="activeSection === 'duration'" class="more-panel">
                      <div class="more-panel-title">Duration</div>
                      <div class="more-options">
                        <button
                          v-for="d in durationOptions"
                          :key="d.value"
                          type="button"
                          class="more-option"
                          :class="{ selected: durationMs === d.value }"
                          @click="durationMs = d.value"
                        >
                          <span class="opt-label">{{ d.label }}</span>
                          <span v-if="durationMs === d.value" class="opt-check">✓</span>
                        </button>
                      </div>
                    </div>

                    <div v-else-if="activeSection === 'assets'" class="more-panel">
                      <div class="more-panel-title">Assets source</div>
                      <div class="more-options">
                        <button
                          v-for="a in assetSourceOptions"
                          :key="a.value"
                          type="button"
                          class="more-option"
                          :class="{ selected: assetSource === a.value }"
                          @click="assetSource = a.value"
                        >
                          <div class="opt-col">
                            <div class="opt-label">{{ a.label }}</div>
                            <div class="opt-desc">{{ a.desc }}</div>
                          </div>
                          <span v-if="assetSource === a.value" class="opt-check">✓</span>
                        </button>
                      </div>
                    </div>

                    <div v-else-if="activeSection === 'style'" class="more-panel">
                      <div class="more-panel-title">AI style</div>
                      <div class="more-options">
                        <button
                          v-for="s in styleOptions"
                          :key="s.value"
                          type="button"
                          class="more-option"
                          :class="{ selected: videoStyleId === s.value }"
                          @click="videoStyleId = s.value"
                        >
                          <span class="opt-label">{{ s.label }}</span>
                          <span v-if="videoStyleId === s.value" class="opt-check">✓</span>
                        </button>
                      </div>
                    </div>

                    <div v-else class="more-panel">
                      <div class="more-panel-title">Voice</div>
                      <div class="more-options">
                        <button
                          v-for="v in voiceOptions"
                          :key="v.value"
                          type="button"
                          class="more-option"
                          :class="{ selected: voiceId === v.value }"
                          @click="voiceId = v.value"
                        >
                          <span class="opt-label">{{ v.label }}</span>
                          <span v-if="voiceId === v.value" class="opt-check">✓</span>
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </el-popover>

              <button class="pill pill-ghost" type="button" @click="openRecipeRail">
                <span class="pill-label">{{ durationLabel }}</span>
              </button>
            </div>

            <button
              class="gen"
              type="button"
              :disabled="creating || uploadingAssets || !prompt.trim()"
              @click="onGenerate"
            >
              <span class="gen-icon">▶</span>
              <span class="gen-text">{{ creating ? 'Generating' : 'Generate' }}</span>
            </button>
          </div>
        </div>
      </div>
    </section>

    <section class="recipes">
      <div class="recipes-head">
        <div class="recipes-title">Recipe</div>
        <div class="recipes-actions">
          <el-button text size="small" @click="reload">刷新</el-button>
        </div>
      </div>

      <div class="recipes-rail">
        <RecipeCard
          v-for="r in recipes"
          :key="r.id"
          :recipe="r"
          :selected="selectedRecipeId === r.id"
          @open="openRecipe(r)"
          @use="useRecipe(r)"
        />
      </div>
    </section>

    <RecipePreviewDialog v-model="previewOpen" :recipe="previewRecipe" @use="previewUse" />

    <el-dialog v-model="assetPreviewOpen" width="860" :show-close="true" align-center>
      <template #header>
        <div style="font-weight: 700">预览</div>
      </template>
      <div v-if="previewAsset" class="asset-preview">
        <img v-if="previewAsset.kind === 'image'" class="asset-preview-media" :src="previewAsset.url" alt="asset" />
        <video
          v-else
          class="asset-preview-media"
          :src="previewAsset.url"
          controls
          autoplay
          muted
          playsinline
        />
        <div class="asset-preview-url">{{ previewAsset.url }}</div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { medeoApi } from '@/api'

import RecipeCard, { type MedeoRecipe } from '@/components/medeo/RecipeCard.vue'
import RecipePreviewDialog from '@/components/medeo/RecipePreviewDialog.vue'

type AssetSource = 'auto' | 'ai_video' | 'ai_image' | 'uploaded' | 'stock'

const router = useRouter()
const creating = ref(false)
const prompt = ref('')
const aspectRatio = ref<'16:9' | '9:16'>('16:9')
type DurationValue = 'auto' | 15000 | 30000 | 60000
const durationMs = ref<DurationValue>('auto')
const selectedRecipeId = ref<string>('')
const recipes = ref<MedeoRecipe[]>([])

type AssetKind = 'image' | 'video'
type AssetStatus = 'uploading' | 'processing' | 'done' | 'error'
type MedeoAssetItem = {
  id: string
  url?: string
  localUrl: string
  previewUrl: string
  filename?: string
  contentType: string
  kind: AssetKind
  status: AssetStatus
  mediaIds: string[]
  durationSec?: number
}

const assetItems = ref<MedeoAssetItem[]>([])
const mediaIds = ref<string[]>([])
const uploadingAssets = ref(false)
const assetFileInputRef = ref<HTMLInputElement | null>(null)
const assetPreviewOpen = ref(false)
const previewAsset = ref<MedeoAssetItem | null>(null)

const previewOpen = ref(false)
const previewRecipe = ref<MedeoRecipe | null>(null)

const moreOpen = ref(false)
const activeSection = ref<'duration' | 'assets' | 'style' | 'voice'>('duration')
const assetSource = ref<AssetSource>('auto')
const videoStyleId = ref<string>('style_modern')
const voiceId = ref<string>('voice_default')

const moreSections = [
  { key: 'duration', label: 'Duration', icon: '⏱' },
  { key: 'assets', label: 'Assets source', icon: '🧩' },
  { key: 'style', label: 'AI style', icon: '✨' },
  { key: 'voice', label: 'Voice', icon: '🎙' }
] as const

const durationOptions: Array<{ label: string; value: DurationValue }> = [
  { label: 'Auto', value: 'auto' },
  { label: '15s', value: 15000 },
  { label: '30s', value: 30000 },
  { label: '60s', value: 60000 }
]

const assetSourceOptions: Array<{ label: string; value: AssetSource; desc: string }> = [
  { label: 'Auto', value: 'auto', desc: 'Automatically match the most suitable assets.' },
  { label: 'AI video', value: 'ai_video', desc: 'Use AI-generated videos as the source of your video.' },
  { label: 'AI image', value: 'ai_image', desc: 'Use AI-generated images as the source of your video.' },
  { label: 'My uploaded assets', value: 'uploaded', desc: 'Use your uploaded assets as the source of your video.' },
  { label: 'Stock videos', value: 'stock', desc: 'Use official stock videos as the source of your video.' }
]

const styleOptions = [
  { label: 'Modern', value: 'style_modern' },
  { label: 'Cinematic', value: 'style_cinematic' },
  { label: 'Anime', value: 'style_anime' }
]

const voiceOptions = [
  { label: 'Default', value: 'voice_default' },
  { label: 'Sarah (EN)', value: 'voice_sarah_en' },
  { label: 'XiaoYu (ZH)', value: 'voice_xiaoyu_zh' }
]

const durationLabel = computed(() => {
  const hit = durationOptions.find(x => x.value === durationMs.value)
  return hit?.label || 'Auto'
})

const durationMsToSend = computed<number>(() => {
  return durationMs.value === 'auto' ? 30000 : durationMs.value
})


function toggleAspect() {
  aspectRatio.value = aspectRatio.value === '16:9' ? '9:16' : '16:9'
}

function openRecipeRail() {
  // 预留：后续可做滚动到 recipes 或打开 recipe selector
  const el = document.querySelector('.recipes') as HTMLElement | null
  el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function normalize_recipe(raw: any): MedeoRecipe {
  const ossBase = 'https://oss.prd.medeo.app/'
  const key = String(raw?.thumb_storage_key || raw?.thumbStorageKey || '').trim()
  const highlightKey = String(raw?.highlight_video_storage_key || raw?.highlightVideoStorageKey || '').trim()
  const videoKey = String(raw?.video_storage_key || raw?.videoStorageKey || '').trim()
  return {
    id: String(raw?.id || ''),
    name: String(raw?.name || 'Untitled'),
    thumbUrl: key ? `${ossBase}${key}` : undefined,
    highlightVideoUrl: highlightKey ? `${ossBase}${highlightKey}` : undefined,
    videoUrl: videoKey ? `${ossBase}${videoKey}` : undefined,
    description: String(raw?.description || ''),
    userPrompt: String(raw?.user_prompt || raw?.userPrompt || ''),
    label: String(raw?.label || ''),
    isNew: Boolean(raw?.is_new || raw?.isNew)
  }
}

function openRecipe(r: MedeoRecipe) {
  previewRecipe.value = r
  previewOpen.value = true
}

function useRecipe(r: MedeoRecipe) {
  selectedRecipeId.value = r.id
  // 将 recipe 推荐 prompt 带入输入框，用户可继续编辑
  if (r.userPrompt && r.userPrompt.trim()) {
    prompt.value = r.userPrompt.trim()
  }
  previewOpen.value = false
}

function previewUse() {
  if (previewRecipe.value) useRecipe(previewRecipe.value)
}

async function reload() {
  try {
    const resp = await medeoApi.listRecipes({ limit: 20, order: 'desc' })
    const list = resp?.list || []
    recipes.value = list.map((x: any) => normalize_recipe(x)).filter((x: MedeoRecipe) => x.id)
  } catch (e) {
    console.error(e)
    ElMessage.error('加载 recipes 失败')
  }
}

async function onGenerate() {
  creating.value = true
  try {
    const sourcesMap: Record<string, string[]> = {
      auto: [],
      ai_video: ['ai_videos'],
      ai_image: ['ai_images'],
      uploaded: ['my_uploaded_assets'],
      stock: ['stock_videos']
    }
    const params = {
      prompt: prompt.value.trim(),
      settings: {
        duration_ms: durationMsToSend.value,
        aspect_ratio: aspectRatio.value,
        recipe_id: selectedRecipeId.value || undefined,
        video_style_id: videoStyleId.value || undefined,
        voice_id: voiceId.value || undefined,
        asset_sources: sourcesMap[assetSource.value] || undefined
      },
      media_ids: mediaIds.value.length > 0 ? mediaIds.value : undefined
    }
    console.log('params', params)
    const resp = await medeoApi.initiateProject(params)
    const pid = Number(resp?.project_id || 0)
    if (!pid) throw new Error('project_id 缺失')
    await router.push({ name: 'MedeoPreviewProject', params: { projectId: String(pid) } })
  } catch (e: any) {
    ElMessage.error(e?.message || '创建失败')
  } finally {
    creating.value = false
  }
}

onMounted(() => reload())

function pick_asset_files() {
  assetFileInputRef.value?.click()
}

async function upload_assets(files: File[]): Promise<MedeoAssetItem[]> {
  const token = localStorage.getItem('accessToken')
  if (!token) throw new Error('未登录，请先登录')

  const form = new FormData()
  for (const f of files) {
    form.append('files', f)
  }

  const resp = await fetch('/api/files/upload-assets', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
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

  const filesResp = json?.data?.files || []
  const items: MedeoAssetItem[] = []
  for (const x of filesResp) {
    const url = String(x?.url || '').trim()
    const ct = String(x?.content_type || x?.contentType || '').trim()
    if (!url) continue
    const kind: AssetKind = ct.startsWith('video/') ? 'video' : 'image'
    items.push({
      id: `remote_${Math.random().toString(16).slice(2)}`,
      url,
      localUrl: url,
      previewUrl: url,
      filename: String(x?.filename || ''),
      contentType: ct || (kind === 'video' ? 'video/mp4' : 'image/jpeg'),
      kind,
      status: 'processing',
      mediaIds: []
    })
  }
  return items
}

async function sleep(ms: number): Promise<void> {
  await new Promise((r) => setTimeout(r, ms))
}

async function create_media_id_from_url(url: string): Promise<string[]> {
  const job = await medeoApi.createMediaFromUrl({ url })
  const jobId = String(job?.id || '')
  if (!jobId) throw new Error('Medeo media job_id 缺失')

  const deadline = Date.now() + 120_000
  while (Date.now() < deadline) {
    const st = await medeoApi.getMediaCreationJob(jobId)
    const state = String(st?.state || '')
    if (state === 'completed') {
      const ids = (st?.media_ids || []).map((x: any) => String(x)).filter(Boolean)
      if (ids.length === 0) throw new Error('media_ids 为空')
      return ids
    }
    if (state === 'failed') {
      throw new Error('Medeo media 创建失败')
    }
    await sleep(1000)
  }
  throw new Error('Medeo media 创建超时')
}

async function handle_asset_files(evt: Event) {
  const input = evt.target as HTMLInputElement
  const files = input.files
  if (!files || files.length === 0) return

  try {
    const selected = Array.from(files)
    const currentCount = assetItems.value.length
    if (currentCount + selected.length > 5) {
      ElMessage.warning('最多上传 5 个素材（图片/视频），请先删除再上传')
      return
    }

    // 1) 先插入本地预览卡片（立刻显示）
    const tempIds: string[] = []
    const tempItems: MedeoAssetItem[] = selected.map((f) => {
      const local = URL.createObjectURL(f)
      const kind: AssetKind = (f.type || '').startsWith('video/') ? 'video' : 'image'
      const id = `asset_${Date.now()}_${Math.random().toString(16).slice(2)}`
      tempIds.push(id)
      return {
        id,
        url: undefined,
        localUrl: local,
        previewUrl: local,
        filename: f.name,
        contentType: f.type || (kind === 'video' ? 'video/mp4' : 'image/jpeg'),
        kind,
        status: 'uploading',
        mediaIds: []
      }
    })
    assetItems.value = [...assetItems.value, ...tempItems]

    // 2) 上传到 OSS -> 拿到远端 url
    uploadingAssets.value = true
    const uploaded = await upload_assets(selected)

    // 3) 用返回结果按顺序回填到临时卡片，然后 create_from_url -> media_ids
    for (let i = 0; i < uploaded.length; i++) {
      const tempId = tempIds[i]
      const temp = assetItems.value.find((x) => x.id === tempId)
      if (!temp) continue // 被用户删掉了

      const remote = uploaded[i]
      temp.url = remote.url
      temp.contentType = remote.contentType
      temp.kind = remote.kind
      temp.status = 'processing'
      temp.previewUrl = temp.localUrl || remote.url || temp.previewUrl

      try {
        const ids = await create_media_id_from_url(String(remote.url || ''))
        // 若用户删掉了则不写回
        const stillThere = assetItems.value.find((x) => x.id === tempId)
        if (!stillThere) continue
        stillThere.mediaIds = ids
        stillThere.status = 'done'
      } catch (e) {
        const stillThere = assetItems.value.find((x) => x.id === tempId)
        if (!stillThere) continue
        stillThere.status = 'error'
      }
    }

    mediaIds.value = assetItems.value.flatMap((x) => x.mediaIds || []).filter(Boolean)
    ElMessage.success('已上传并创建 Medeo media')
  } catch (e: any) {
    ElMessage.error(e?.message || '上传失败')
  } finally {
    uploadingAssets.value = false
    input.value = ''
  }
}

function openAssetPreview(a: MedeoAssetItem) {
  // 优先用远端 url 预览（若尚未回填则用本地预览）
  previewAsset.value = {
    ...a,
    previewUrl: a.url || a.previewUrl
  }
  assetPreviewOpen.value = true
}

function removeAsset(id: string) {
  const target = assetItems.value.find((x) => x.id === id)
  if (target?.localUrl) {
    try { URL.revokeObjectURL(target.localUrl) } catch {}
  }
  assetItems.value = assetItems.value.filter((x) => x.id !== id)
  mediaIds.value = assetItems.value.flatMap((x) => x.mediaIds || []).filter(Boolean)
  if (previewAsset.value?.id === id) {
    assetPreviewOpen.value = false
    previewAsset.value = null
  }
}

function onVideoMeta(id: string, evt: Event) {
  const el = evt.target as HTMLVideoElement | null
  const dur = el?.duration
  if (!dur || !Number.isFinite(dur) || dur <= 0) return
  const it = assetItems.value.find((x) => x.id === id)
  if (it) it.durationSec = dur
}

function formatDuration(sec?: number) {
  if (!sec || !Number.isFinite(sec) || sec <= 0) return ''
  const s = Math.round(sec)
  const mm = Math.floor(s / 60)
  const ss = s % 60
  return `${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}`
}
</script>

<style scoped>
.medeo-start {
  height: 100%;
  min-height: 0;
  padding: 0;
  background: radial-gradient(1200px 600px at 50% 10%, rgba(124, 58, 237, 0.18), rgba(255, 255, 255, 0) 55%),
    radial-gradient(900px 500px at 20% 30%, rgba(59, 130, 246, 0.14), rgba(255, 255, 255, 0) 60%),
    #f5f6f8;
  overflow: auto;
}
.medeo-start::before {
  content: '';
  position: fixed;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.82) 0%, rgba(255, 255, 255, 0.92) 55%, rgba(245, 246, 248, 1) 100%);
}
.hero {
  position: relative;
  max-width: 1180px;
  margin: 0 auto;
  padding: 56px 24px 14px 24px;
}
.hero-title {
  font-size: 56px;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: #111827;
  text-align: center;
}
.hero-em {
  font-family: ui-serif, Georgia, Cambria, 'Times New Roman', Times, serif;
  font-style: italic;
  font-weight: 700;
}
.hero-sub {
  margin-top: 6px;
  text-align: center;
  color: #6b7280;
}
.composer {
  margin: 22px auto 0 auto;
  padding: 0 8px;
}
.composer-inner {
  position: relative;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(229, 231, 235, 0.9);
  border-radius: 26px;
  box-shadow: 0 22px 60px rgba(17, 24, 39, 0.12);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  overflow: hidden;
}
.asset-file-input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}
.asset-rail {
  padding: 0 18px 10px 18px;
}
.asset-rail-title {
  font-size: 12px;
  color: rgba(107, 114, 128, 0.9);
  margin-bottom: 6px;
}
.asset-rail-list {
  display: flex;
  gap: 10px;
  overflow-x: auto;
  padding-bottom: 2px;
}
.asset-card {
  width: 140px;
  height: auto;
  border-radius: 14px;
  border: 1px solid rgba(229, 231, 235, 0.9);
  background: rgba(255, 255, 255, 0.6);
  overflow: hidden;
  position: relative;
  cursor: pointer;
  flex: 0 0 auto;
}
.asset-del {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 22px;
  height: 22px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: rgba(0, 0, 0, 0.72);
  color: rgba(255, 255, 255, 0.92);
  font-size: 16px;
  line-height: 18px;
  display: grid;
  place-items: center;
  opacity: 0;
  pointer-events: none;
  transition: opacity 140ms ease;
}
.asset-card:hover .asset-del {
  opacity: 1;
  pointer-events: auto;
}
.asset-mask {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  background: rgba(0, 0, 0, 0.38);
  backdrop-filter: blur(2px);
  -webkit-backdrop-filter: blur(2px);
}
.asset-mask-text {
  font-weight: 700;
  font-size: 12px;
  letter-spacing: 0.02em;
  color: rgba(255, 255, 255, 0.95);
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.55);
}
.asset-thumb {
  width: 100%;
  height: auto;
  object-fit: contain;
  display: block;
  background: rgba(17, 24, 39, 0.06);
}
.asset-duration {
  position: absolute;
  bottom: 6px;
  right: 8px;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  color: rgba(255, 255, 255, 0.92);
  background: rgba(17, 24, 39, 0.52);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
}
.asset-rail-hint {
  margin-top: 6px;
  font-size: 12px;
  color: rgba(124, 58, 237, 0.9);
}
.asset-preview {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.asset-preview-media {
  width: 100%;
  max-height: 460px;
  object-fit: contain;
  background: #0b0f19;
  border-radius: 12px;
}
.asset-preview-url {
  font-size: 12px;
  color: rgba(107, 114, 128, 0.95);
  word-break: break-all;
}
.composer-input {
  width: 100%;
  border: none;
  outline: none;
  resize: none;
  padding: 18px 18px 10px 18px;
  background: transparent;
  font-size: 15px;
  line-height: 1.5;
  color: #111827;
}
.composer-input::placeholder {
  color: rgba(107, 114, 128, 0.9);
}
.composer-bar {
  padding: 12px 14px 14px 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.bar-left {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.pill {
  height: 34px;
  padding: 0 12px;
  border-radius: 999px;
  border: 1px solid rgba(229, 231, 235, 0.9);
  background: rgba(255, 255, 255, 0.72);
  color: #111827;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
.pill-ghost {
  background: rgba(255, 255, 255, 0.5);
}
.pill-icon {
  width: 34px;
  justify-content: center;
  padding: 0;
}
.pill-plus {
  font-size: 18px;
  line-height: 1;
  color: #6b7280;
}
.pill-label {
  font-weight: 600;
}
.gen {
  height: 40px;
  padding: 0 18px;
  border-radius: 999px;
  border: none;
  cursor: pointer;
  background: linear-gradient(180deg, #8b5cf6 0%, #6d28d9 100%);
  box-shadow: 0 14px 30px rgba(109, 40, 217, 0.28);
  color: #fff;
  display: inline-flex;
  align-items: center;
  gap: 10px;
}
.gen:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.gen-icon {
  width: 22px;
  height: 22px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.18);
  font-size: 12px;
}
.gen-text {
  font-weight: 700;
}

.more {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 0;
  border-radius: 16px;
  overflow: hidden;
}
.more-left {
  background: #fff;
  border-right: 1px solid rgba(229, 231, 235, 0.8);
  padding: 10px;
}
.more-item {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 10px;
  border-radius: 12px;
  border: none;
  background: transparent;
  cursor: pointer;
  color: #111827;
}
.more-item.active {
  background: rgba(17, 24, 39, 0.04);
}
.more-item-icon {
  width: 18px;
  text-align: center;
}
.more-item-text {
  flex: 1;
  text-align: left;
  font-weight: 600;
}
.more-item-arrow {
  color: #9ca3af;
}
.more-right {
  background: #fff;
  padding: 12px;
}
.more-panel-title {
  font-weight: 800;
  color: #111827;
  margin-bottom: 10px;
}
.more-options {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.more-option {
  width: 100%;
  border: 1px solid rgba(229, 231, 235, 0.9);
  background: rgba(255, 255, 255, 0.9);
  border-radius: 14px;
  padding: 10px 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.more-option.selected {
  border-color: rgba(124, 58, 237, 0.35);
  box-shadow: 0 0 0 3px rgba(124, 58, 237, 0.12);
}
.opt-col {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.opt-label {
  font-weight: 700;
  color: #111827;
}
.opt-desc {
  font-size: 12px;
  color: #6b7280;
}
.opt-check {
  color: #111827;
  font-weight: 900;
}

.recipes {
  position: relative;
  max-width: 1180px;
  margin: 0 auto;
  padding: 18px 24px 28px 24px;
}
.recipes-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.recipes-title {
  font-weight: 700;
  color: #111827;
  font-size: 18px;
}
.recipes-rail {
  margin-top: 12px;
  display: flex;
  gap: 14px;
  overflow-x: auto;
  padding-bottom: 10px;
}
.recipe-card {
  width: 168px;
  flex: 0 0 auto;
  text-align: left;
  border: 2px solid transparent;
  background: transparent;
  cursor: pointer;
}
.recipe-card.active .recipe-thumb {
  outline: 3px solid rgba(124, 58, 237, 0.38);
}
.selected-mark {
  position: absolute;
  top: 10px;
  right: 10px;
  width: 22px;
  height: 22px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 900;
  font-size: 12px;
  color: #ffffff;
  background: #22c55e;
  box-shadow: 0 10px 22px rgba(34, 197, 94, 0.35);
}
.recipe-thumb {
  width: 168px;
  height: 168px;
  border-radius: 18px;
  overflow: hidden;
  background: #111827;
  position: relative;
}
.recipe-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.thumb-skel {
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, #111827, #1f2937, #111827);
  background-size: 200% 100%;
  animation: shimmer 1.2s infinite;
}
.badge {
  position: absolute;
  top: 10px;
  left: 10px;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 12px;
  background: rgba(255, 255, 255, 0.9);
  color: #111827;
}
.recipe-name {
  margin-top: 10px;
  font-weight: 700;
  color: #111827;
}

@keyframes shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}
</style>

