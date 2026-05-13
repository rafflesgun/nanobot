<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, shallowRef, watch } from 'vue'
import { EditorState } from '@codemirror/state'
import { EditorView, keymap, lineNumbers, highlightActiveLine, highlightActiveLineGutter } from '@codemirror/view'
import { json, jsonParseLinter } from '@codemirror/lang-json'
import { markdown } from '@codemirror/lang-markdown'
import { linter } from '@codemirror/lint'
import { oneDark } from '@codemirror/theme-one-dark'
import { defaultKeymap, indentWithTab } from '@codemirror/commands'
import { syntaxHighlighting, defaultHighlightStyle, bracketMatching } from '@codemirror/language'

const props = withDefaults(defineProps<{
  modelValue: string
  language: 'json' | 'markdown'
  readOnly?: boolean
  placeholder?: string
}>(), {
  readOnly: false,
  placeholder: ''
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const editorRef = ref<HTMLDivElement>()
const view = shallowRef<EditorView>()
const isValid = ref(true)

const extensions = computed(() => {
  const exts: any[] = [
    lineNumbers(),
    highlightActiveLine(),
    highlightActiveLineGutter(),
    bracketMatching(),
    syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
    oneDark,
    keymap.of([...defaultKeymap, indentWithTab]),
    EditorView.updateListener.of((update) => {
      if (update.docChanged) {
        const doc = update.state.doc.toString()
        emit('update:modelValue', doc)
        if (props.language === 'json') {
          try { JSON.parse(doc); isValid.value = true } catch { isValid.value = false }
        }
      }
    }),
    EditorState.readOnly.of(props.readOnly),
    EditorView.editable.of(!props.readOnly)
  ]
  if (props.language === 'json') {
    exts.push(json())
    exts.push(linter(jsonParseLinter()))
  } else {
    exts.push(markdown())
    isValid.value = true
  }
  return exts
})

onMounted(() => {
  if (!editorRef.value) return
  view.value = new EditorView({
    state: EditorState.create({ doc: props.modelValue, extensions: extensions.value }),
    parent: editorRef.value
  })
  if (props.language === 'json') {
    try { JSON.parse(props.modelValue); isValid.value = true } catch { isValid.value = false }
  }
})

watch(() => props.modelValue, (newValue) => {
  if (!view.value) return
  const current = view.value.state.doc.toString()
  if (current !== newValue) {
    view.value.dispatch({
      changes: { from: 0, to: current.length, insert: newValue }
    })
  }
})

onUnmounted(() => {
  view.value?.destroy()
})

defineExpose({ isValid })
</script>

<template>
  <div
    ref="editorRef"
    class="code-editor"
    :class="[`lang-${language}`, { 'is-readonly': readOnly }]"
  />
</template>

<style scoped>
.code-editor {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: oklch(12% 0.012 255);
  font-size: 0.88rem;
  line-height: 1.6;
  min-height: 14rem;
  overflow: hidden;
}
.code-editor :deep(.cm-editor) {
  height: 100%;
  min-height: 14rem;
}
.code-editor :deep(.cm-scroller) {
  font-family: var(--font-mono);
}
.code-editor.is-readonly :deep(.cm-content) {
  opacity: 0.7;
}
.code-editor :deep(.cm-gutters) {
  border-right: 1px solid var(--border);
}
.code-editor :deep(.cm-lint-marker-error) {
  background: var(--danger);
}
.code-editor :deep(.cm-tooltip-lint) {
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--fg);
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 12px;
}
</style>
