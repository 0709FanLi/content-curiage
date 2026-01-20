<template>
  <el-dialog
    :model-value="modelValue"
    width="980px"
    :show-close="true"
    :close-on-click-modal="true"
    @close="$emit('update:modelValue', false)"
  >
    <div class="dlg">
      <div class="dlg-left">
        <video
          v-if="recipe?.highlightVideoUrl || recipe?.videoUrl"
          class="dlg-video"
          :src="recipe?.highlightVideoUrl || recipe?.videoUrl"
          autoplay
          muted
          loop
          playsinline
          controls
        />
        <div v-else class="dlg-empty">No preview</div>
      </div>
      <div class="dlg-right">
        <div class="dlg-head">
          <div v-if="recipe?.isNew" class="dlg-new">New</div>
          <div class="dlg-title">{{ recipe?.name || 'Recipe' }}</div>
          <div v-if="recipe?.label" class="dlg-tag">{{ recipe.label }}</div>
        </div>

        <div class="dlg-desc">
          {{ recipe?.description || '—' }}
        </div>

        <div class="dlg-divider" />

        <div class="dlg-section">
          <div class="dlg-section-title">Prompt</div>
          <div class="dlg-prompt">{{ recipe?.userPrompt || '—' }}</div>
        </div>

        <div class="dlg-actions">
          <el-button class="dlg-use" type="primary" @click="$emit('use')">
            Use this recipe
          </el-button>
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import type { MedeoRecipe } from './RecipeCard.vue'

defineProps<{
  modelValue: boolean
  recipe: MedeoRecipe | null
}>()

defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'use'): void
}>()
</script>

<style scoped>
.dlg {
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: 16px;
  min-height: 520px;
}
.dlg-left {
  border-radius: 16px;
  overflow: hidden;
  background: #0b0f1a;
  display: flex;
  align-items: center;
  justify-content: center;
}
.dlg-video {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.dlg-empty {
  color: rgba(255, 255, 255, 0.7);
}
.dlg-right {
  padding: 6px 2px;
  display: flex;
  flex-direction: column;
}
.dlg-head {
  display: flex;
  align-items: center;
  gap: 10px;
}
.dlg-new {
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(17, 24, 39, 0.06);
  font-size: 12px;
  font-weight: 700;
}
.dlg-title {
  font-size: 22px;
  font-weight: 900;
  color: #111827;
}
.dlg-tag {
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(17, 24, 39, 0.06);
  font-size: 12px;
  color: #374151;
}
.dlg-desc {
  margin-top: 10px;
  color: #4b5563;
  line-height: 1.5;
  font-size: 13px;
}
.dlg-divider {
  height: 1px;
  background: rgba(229, 231, 235, 0.9);
  margin: 14px 0;
}
.dlg-section-title {
  font-weight: 800;
  color: #111827;
  margin-bottom: 8px;
}
.dlg-prompt {
  color: #111827;
  background: rgba(17, 24, 39, 0.03);
  border: 1px solid rgba(229, 231, 235, 0.9);
  border-radius: 12px;
  padding: 10px 12px;
  font-size: 13px;
  line-height: 1.45;
  white-space: pre-wrap;
}
.dlg-actions {
  margin-top: auto;
  padding-top: 18px;
}
.dlg-use {
  width: 100%;
  height: 44px;
  border-radius: 12px;
  font-weight: 800;
}
@media (max-width: 1100px) {
  .dlg {
    grid-template-columns: 1fr;
    min-height: 0;
  }
  .dlg-left {
    height: 360px;
  }
}
</style>

