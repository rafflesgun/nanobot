<script setup lang="ts">
import { ref } from 'vue'
import { Icon } from '@iconify/vue'

const props = defineProps<{
  language: string
  code: string
}>()

const copied = ref(false)

const ext: Record<string, string> = {
  ts: 'ts', js: 'js', python: 'py', html: 'html', css: 'css', json: 'json',
  bash: 'sh', shell: 'sh', sql: 'sql', rust: 'rs', go: 'go', java: 'java',
  cpp: 'cpp', c: 'c', ruby: 'rb', yaml: 'yml', yml: 'yml', xml: 'xml',
  markdown: 'md', typescript: 'ts', javascript: 'js',
}

async function copyCode() {
  try {
    await navigator.clipboard.writeText(props.code)
  } catch {
    const ta = document.createElement('textarea')
    ta.value = props.code
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
  }
  copied.value = true
  setTimeout(() => { copied.value = false }, 2000)
}

function downloadCode() {
  const extension = ext[props.language] || 'txt'
  const name = `code-${Math.random().toString(36).slice(2, 8)}.${extension}`
  const blob = new Blob([props.code], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <div class="code-block">
    <div class="code-header">
      <span class="lang-label">{{ language.toLowerCase() }}</span>
      <div class="actions">
        <button class="action-btn" :data-testid="'copy-code'" @click="copyCode">
          <Icon :icon="copied ? 'mdi:check' : 'mdi:content-copy'" />
        </button>
        <button class="action-btn" :data-testid="'download-code'" @click="downloadCode">
          <Icon icon="mdi:download" />
        </button>
      </div>
    </div>
    <div class="code-body">
      <pre><code>{{ code }}</code></pre>
    </div>
  </div>
</template>

<style scoped>
.code-block {
  border: 1px solid var(--border);
  border-radius: 0.7rem;
  background: oklch(12% 0.012 255);
  overflow: hidden;
}

.code-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 10px;
  background: oklch(22% 0.014 255);
}

.lang-label {
  font-size: 0.7rem;
  color: var(--muted);
  text-transform: lowercase;
}

.actions {
  display: flex;
  gap: 2px;
}

.action-btn {
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  color: var(--muted);
  cursor: pointer;
  border-radius: 4px;
}

.action-btn:hover {
  color: var(--fg);
}

.code-body {
  padding: 0.75rem;
  overflow: auto;
  font-family: var(--font-mono);
  font-size: 0.85rem;
}

.code-body pre {
  margin: 0;
}

.code-body code {
  font-family: inherit;
  font-size: inherit;
}
</style>
