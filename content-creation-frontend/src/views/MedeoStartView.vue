<template>
  <div class="medeo-start">
    <section class="hero">
      <div class="hero-title">One Click to <span class="hero-em">Pro Videos</span></div>
      <div class="hero-sub">Make great videos by chatting with AI</div>

      <div class="prompt-card">
        <el-input
          v-model="prompt"
          class="prompt-input"
          type="textarea"
          :rows="3"
          placeholder="Ask Medeo to produce a documentary-style explainer..."
        />

        <div class="controls">
          <div class="left-controls">
            <el-select v-model="aspectRatio" size="small" class="ctl">
              <el-option label="16:9" value="16:9" />
              <el-option label="9:16" value="9:16" />
            </el-select>

            <el-select v-model="durationMs" size="small" class="ctl">
              <el-option label="Auto" :value="30000" />
              <el-option label="15s" :value="15000" />
              <el-option label="30s" :value="30000" />
              <el-option label="60s" :value="60000" />
            </el-select>

            <el-select v-model="selectedRecipeId" size="small" class="ctl" clearable placeholder="Recipe（可选）">
              <el-option v-for="r in recipes" :key="r.id" :label="r.name" :value="r.id" />
            </el-select>
          </div>

          <el-button
            type="primary"
            class="gen-btn"
            :loading="creating"
            :disabled="!prompt.trim()"
            @click="onGenerate"
          >
            Generate
          </el-button>
        </div>
      </div>
    </section>

    <section class="recipes">
      <div class="recipes-head">
        <div class="recipes-title">Recipe</div>
        <el-button text size="small" @click="reload">刷新</el-button>
      </div>

      <div class="recipes-rail">
        <button
          v-for="r in recipes"
          :key="r.id"
          type="button"
          class="recipe-card"
          :class="{ active: selectedRecipeId === r.id }"
          @click="selectedRecipeId = r.id"
        >
          <div class="recipe-thumb">
            <img v-if="r.thumbUrl" :src="r.thumbUrl" alt="" />
            <div v-else class="thumb-skel" />
            <div v-if="r.isNew" class="badge">New</div>
          </div>
          <div class="recipe-name">{{ r.name }}</div>
        </button>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { medeoApi } from '@/api'

type Recipe = { id: string; name: string; thumbUrl?: string; isNew?: boolean }

const router = useRouter()
const creating = ref(false)
const prompt = ref('')
const aspectRatio = ref<'16:9' | '9:16'>('16:9')
const durationMs = ref<number>(30000)
const selectedRecipeId = ref<string>('')
const recipes = ref<Recipe[]>([])

function normalize_recipe(raw: any): Recipe {
  const ossBase = 'https://oss.prd.medeo.app/'
  const key = String(raw?.thumb_storage_key || raw?.thumbStorageKey || '').trim()
  return {
    id: String(raw?.id || ''),
    name: String(raw?.name || 'Untitled'),
    // Medeo 文档说明：可直接用 oss base + storage_key（若后续需要签名，再放到后端）
    thumbUrl: key ? `${ossBase}${key}` : undefined,
    isNew: Boolean(raw?.is_new || raw?.isNew)
  }
}

async function reload() {
  try {
    const resp = await medeoApi.listRecipes({ limit: 20, order: 'desc' })
    const list = resp?.list || []
    recipes.value = list.map((x: any) => normalize_recipe(x)).filter((x: Recipe) => x.id)
  } catch (e) {
    console.error(e)
    ElMessage.error('加载 recipes 失败')
  }
}

async function onGenerate() {
  creating.value = true
  try {
    const resp = await medeoApi.initiateProject({
      prompt: prompt.value.trim(),
      settings: {
        duration_ms: durationMs.value,
        aspect_ratio: aspectRatio.value,
        recipe_id: selectedRecipeId.value || undefined
      }
    })
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
</script>

<style scoped>
.medeo-start {
  height: 100%;
  min-height: 0;
  padding: 20px 24px;
  background: #f3f4f6;
  overflow: auto;
}
.hero {
  max-width: 1080px;
  margin: 0 auto;
  padding: 32px 0 18px 0;
}
.hero-title {
  font-size: 52px;
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
  margin-top: 10px;
  text-align: center;
  color: #6b7280;
}
.prompt-card {
  margin: 24px auto 0 auto;
  padding: 16px;
  background: rgba(255, 255, 255, 0.85);
  border: 1px solid rgba(229, 231, 235, 0.9);
  border-radius: 22px;
  box-shadow: 0 18px 42px rgba(0, 0, 0, 0.08);
}
.controls {
  margin-top: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.left-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.ctl {
  width: 140px;
}
.gen-btn {
  border-radius: 999px;
  padding: 10px 18px;
}
.recipes {
  max-width: 1180px;
  margin: 0 auto;
  padding-top: 18px;
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
  outline: 3px solid rgba(124, 58, 237, 0.4);
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

