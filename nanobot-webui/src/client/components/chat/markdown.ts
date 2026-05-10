import MarkdownIt from 'markdown-it'
import taskLists from 'markdown-it-task-lists'
import hljs from 'highlight.js'

const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  highlight(str: string, lang: string): string {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return (
          '<pre class="hljs"><code class="language-' +
          lang +
          '">' +
          hljs.highlight(str, { language: lang }).value +
          '</code></pre>'
        )
      } catch {
        // fall through
      }
    }
    return (
      '<pre class="hljs"><code>' +
      md.utils.escapeHtml(str) +
      '</code></pre>'
    )
  },
})

md.use(taskLists)

export function renderMarkdown(text: string): string {
  return md.render(text)
}
