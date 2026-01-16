<template>
  <el-select
    v-model="modelValue"
    :placeholder="placeholder"
    :class="selectClass"
    :disabled="disabled"
    :clearable="clearable"
    @change="handleChange"
  >
    <el-option
      v-for="model in filteredModels"
      :key="model.id"
      :label="model.name"
      :value="model.id"
    />
  </el-select>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, computed } from 'vue'
import { modelApi } from '@/api'

interface Props {
  /** 模型类型：script（脚本模型）或 image（图片模型） */
  type?: 'script' | 'image'
  /** 占位符文本 */
  placeholder?: string
  /** 自定义样式类名 */
  selectClass?: string
  /** 是否禁用 */
  disabled?: boolean
  /** 是否可清空 */
  clearable?: boolean
  /** 默认选中的模型ID */
  defaultValue?: string
  /** 限制可选模型ID（空数组/不传表示不限制） */
  allowedModelIds?: string[]
}

const props = withDefaults(defineProps<Props>(), {
  type: 'script',
  placeholder: '选择模型',
  selectClass: 'control-select',
  disabled: false,
  clearable: false,
  defaultValue: '',
  allowedModelIds: () => []
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
  'change': [value: string]
}>()

const modelValue = ref<string>(props.defaultValue)
const models = ref<{ id: string; name: string }[]>([])

const filteredModels = computed(() => {
  const allow = props.allowedModelIds || []
  if (!allow.length) return models.value
  const allowSet = new Set(allow)
  return models.value.filter(m => allowSet.has(m.id))
})

// 加载模型列表
const loadModels = async () => {
  try {
    let response
    if (props.type === 'script') {
      response = await modelApi.getScriptModels()
    } else {
      response = await modelApi.getImageModels()
    }
    
    const modelList = Array.isArray(response) 
      ? response 
      : (response?.data || [])
    
    models.value = modelList
    
    // 如果有模型且没有默认值，设置第一个为默认值
    const listForDefault = filteredModels.value
    if (listForDefault.length > 0 && !modelValue.value) {
      modelValue.value = listForDefault[0].id
      emit('update:modelValue', modelValue.value)
      emit('change', modelValue.value)
    }
  } catch (error) {
    console.error(`加载${props.type === 'script' ? '脚本' : '图片'}模型列表失败:`, error)
  }
}

const handleChange = (value: string) => {
  emit('update:modelValue', value)
  emit('change', value)
}

// 监听defaultValue变化
watch(() => props.defaultValue, (newValue) => {
  if (newValue && newValue !== modelValue.value) {
    modelValue.value = newValue
  }
})

// 监听 allowedModelIds：如果当前值不在白名单里，自动切到第一个允许模型
watch(
  () => props.allowedModelIds,
  () => {
    const allow = props.allowedModelIds || []
    if (!allow.length) return
    if (modelValue.value && allow.includes(modelValue.value)) return
    const listForDefault = filteredModels.value
    if (listForDefault.length > 0) {
      modelValue.value = listForDefault[0].id
      emit('update:modelValue', modelValue.value)
      emit('change', modelValue.value)
    }
  },
  { deep: true }
)

onMounted(() => {
  loadModels()
})

// 暴露方法供父组件调用
defineExpose({
  loadModels
})
</script>

<style scoped>
/* 样式由父组件通过selectClass控制 */
</style>

