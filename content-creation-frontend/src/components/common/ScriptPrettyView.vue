<template>
  <div class="script-pretty">
    <div v-if="!content?.trim()" class="empty">暂无内容</div>

    <template v-else>
      <el-alert
        v-if="parseError"
        type="warning"
        :closable="false"
        class="parse-alert"
        title="脚本格式未完全识别，已按原文展示。"
      />

      <!-- 结构化展示：按“卡片 + 标签 + 折叠”呈现（接近 Figma 9:611） -->
      <div v-if="cards.length" class="cards">
        <div v-for="(c, idx) in cards" :key="idx" class="card">
          <div class="card-header">
            <div class="card-header-left">
              <span class="card-title">{{ c.title }}</span>
              <span class="pill" :class="`pill-${c.kind}`">{{ c.pill }}</span>
            </div>
            <button
              class="collapse-btn"
              type="button"
              :title="isCollapsed(idx) ? '展开' : '收起'"
              @click="toggle(idx)"
            >
              <span class="collapse-icon">{{ isCollapsed(idx) ? '▾' : '▴' }}</span>
            </button>
          </div>

          <div v-if="!isCollapsed(idx)" class="card-body" :class="`card-body-${c.kind}`">
            <pre class="card-pre">{{ c.value }}</pre>
          </div>
        </div>
      </div>

      <!-- 回退：原文展示 -->
      <div v-else class="raw">
        <pre class="raw-pre">{{ content }}</pre>
        <div class="footer-actions">
          <el-button size="small" @click="copyText(content)">复制全文</el-button>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'

type CardKind = 'keyframe' | 'video' | 'narration'

interface Field {
  key: CardKind
  value: string
}

interface Block {
  title: string
  raw: string
  fields?: Field[]
}

interface Card {
  title: string
  kind: CardKind
  pill: string
  value: string
}

const props = defineProps<{
  content: string
}>()

const parseError = ref(false)
const collapsed = ref<Record<number, boolean>>({})

function copyText(text: string) {
  navigator.clipboard
    .writeText(text)
    .then(() => ElMessage.success('已复制'))
    .catch(() => ElMessage.error('复制失败（请检查浏览器权限）'))
}

function normalize(s: string) {
  return s.replace(/\r\n/g, '\n').trim()
}

function splitBlocks(text: string): string[] {
  // 全局移除第0帧后：脚本以时间段 blocks 为主；
  // 若仍含“第0帧”，作为历史文本保留并单独成块展示（不参与生成流程）。
  const t = normalize(text)
  const re = /(\(\d+\s*-\s*\d+\s*s\))/g
  const parts = t.split(re)

  // 如果没时间段标记，整段作为 1 block
  if (parts.length <= 1) return [t]

  const out: string[] = []
  // parts[0] 可能包含历史“第0帧” + 前导内容
  if (parts[0].trim()) out.push(parts[0].trim())

  // 后续是 [time, content, time, content...]
  for (let i = 1; i < parts.length; i += 2) {
    const time = parts[i]
    const body = parts[i + 1] ?? ''
    const block = `${time}\n${body}`.trim()
    if (block) out.push(block)
  }
  return out
}

function parseFields(blockText: string): Field[] | null {
  const t = normalize(blockText)
  const fields: Field[] = []

  // 历史第0帧只做原文（不再参与结构化字段解析）
  if (t.startsWith('第0帧：') || t.startsWith('第0帧:')) return null

  const map: Array<{ key: CardKind; patterns: RegExp[] }> = [
    { key: 'keyframe', patterns: [/^关键帧：/m, /^关键帧:/m] },
    { key: 'video', patterns: [/^视频：/m, /^视频:/m] },
    { key: 'narration', patterns: [/^口播文案：/m, /^口播文案:/m] }
  ]

  // 用行级扫描切分字段
  const lines = t.split('\n')
  let cur: { key: CardKind; buf: string[] } | null = null

  const matchField = (line: string) => {
    for (const item of map) {
      for (const p of item.patterns) {
        if (p.test(line)) return item
      }
    }
    return null
  }

  for (const line of lines) {
    // 跳过时间行
    if (/^\(\d+\s*-\s*\d+\s*s\)\s*$/.test(line.trim())) continue

    const hit = matchField(line)
    if (hit) {
      if (cur) {
        fields.push({ key: cur.key, value: cur.buf.join('\n').trim() })
      }
      // 去掉 “字段名：” 前缀
      const cleaned = line.replace(/^(关键帧|视频|口播文案)\s*[:：]\s*/, '')
      cur = { key: hit.key, buf: [cleaned] }
    } else {
      if (!cur) {
        // 还没遇到字段，先忽略杂项（很多脚本里会在字段前有空行/说明）
        continue
      }
      cur.buf.push(line)
    }
  }

  if (cur) {
    fields.push({ key: cur.key, value: cur.buf.join('\n').trim() })
  }

  // 如果一个字段都没解析出来，返回 null 让父层按 raw 展示
  if (!fields.length) return null
  return fields
}

const blocks = computed<Block[]>(() => {
  parseError.value = false
  try {
    const rawBlocks = splitBlocks(props.content)
    return rawBlocks.map((raw, idx) => {
      const t = normalize(raw)
      let title = `第${idx}段`
      const timeMatch = t.match(/^\(\d+\s*-\s*\d+\s*s\)/)
      if (t.startsWith('第0帧')) title = '第0帧（历史文本，已废弃）'
      else if (timeMatch) title = `片段 ${timeMatch[0]}`

      const fields = parseFields(t) ?? undefined
      return { title, raw: t, fields }
    })
  } catch (e) {
    parseError.value = true
    return []
  }
})

const cards = computed<Card[]>(() => {
  const out: Card[] = []
  let segIndex = 1
  for (const b of blocks.value) {
    if (b.title.startsWith('第0帧')) {
      out.push({
        title: '第0帧（历史文本，已废弃）',
        kind: 'narration',
        pill: '口播文案',
        value: b.raw
      })
      continue
    }

    if (!b.fields?.length) {
      out.push({
        title: b.title,
        kind: 'narration',
        pill: '口播文案',
        value: b.raw
      })
      segIndex += 1
      continue
    }

    for (const f of b.fields) {
      if (f.key === 'narration') {
        out.push({
          title: `第${segIndex}帧`,
          kind: 'narration',
          pill: '口播文案',
          value: f.value
        })
      } else if (f.key === 'keyframe') {
        out.push({
          title: b.title,
          kind: 'keyframe',
          pill: '关键帧',
          value: f.value
        })
      } else if (f.key === 'video') {
        out.push({
          title: `视频片段 ${segIndex}`,
          kind: 'video',
          pill: '视频',
          value: f.value
        })
      }
    }
    segIndex += 1
  }
  return out
})

const isCollapsed = (idx: number) => Boolean(collapsed.value[idx])
const toggle = (idx: number) => {
  collapsed.value[idx] = !collapsed.value[idx]
}
</script>

<style scoped>
.script-pretty {
  width: 100%;
}

.parse-alert {
  margin-bottom: 10px;
}

.empty {
  color: #999;
  padding: 8px 0;
}

.cards {
  display: flex;
  width: 75%;
  flex-direction: column;
  gap: 16px;
}

.card {
  width: 100%;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 28px;
  margin-bottom: 8px;
}

.card-header-left {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.card-title {
  font-size: 14px;
  font-weight: 600;
  color: #1e2939;
  letter-spacing: -0.1504px;
}

.pill {
  height: 22px;
  display: inline-flex;
  align-items: center;
  padding: 0 9px;
  border-radius: 999px;
  font-size: 12px;
  line-height: 16px;
  border: 1px solid transparent;
}

.pill-narration {
  background: #ffedd4;
  border-color: #ffd6a7;
  color: #ca3500;
}

.pill-keyframe {
  background: #dbeafe;
  border-color: #bedbff;
  color: #1447e6;
}

.pill-video {
  background: #dcfce7;
  border-color: #b9f8cf;
  color: #008236;
}

.collapse-btn {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  border: none;
  background: transparent;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #4a5565;
}

.collapse-icon {
  font-size: 14px;
  line-height: 1;
}

.card-body {
  border-radius: 10px;
  padding: 16px;
}

.card-body-narration {
  background: #fff7ed;
}

.card-body-keyframe {
  background: #eff6ff;
}

.card-body-video {
  background: #f0fdf4;
}

.card-pre,
.raw-pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  font-size: 14px;
  line-height: 22.75px;
  color: #364153;
  letter-spacing: -0.1504px;
}

.footer-actions {
  margin-top: 10px;
  display: flex;
  justify-content: flex-end;
}
</style>



