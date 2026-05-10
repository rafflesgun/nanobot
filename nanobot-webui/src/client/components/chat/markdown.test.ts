import { describe, expect, it } from 'vitest'
import { renderMarkdown } from './markdown'

describe('renderMarkdown', () => {
  it('renders a paragraph', () => {
    const result = renderMarkdown('Hello world')
    expect(result).toContain('<p>Hello world</p>')
  })

  it('renders a heading', () => {
    const result = renderMarkdown('# Title')
    expect(result).toContain('<h1>Title</h1>')
  })

  it('renders a code block with language class', () => {
    const result = renderMarkdown('```ts\nconst x = 1\n```')
    expect(result).toContain('class="language-ts"')
  })

  it('renders inline code', () => {
    const result = renderMarkdown('Use `npm install`')
    expect(result).toContain('<code>npm install</code>')
  })

  it('renders a bullet list', () => {
    const result = renderMarkdown('- one\n- two')
    expect(result).toContain('<ul>')
    expect(result).toContain('<li>one</li>')
    expect(result).toContain('<li>two</li>')
  })

  it('renders GFM task list', () => {
    const result = renderMarkdown('- [x] done\n- [ ] todo')
    expect(result).toContain('task-list')
  })

  it('renders a table', () => {
    const result = renderMarkdown('| A | B |\n|---|---|\n| 1 | 2 |')
    expect(result).toContain('<table>')
  })

  it('escapes script tags in content', () => {
    const result = renderMarkdown('<script>alert(1)</script>')
    expect(result).not.toContain('<script>')
  })

  it('highlights code blocks', () => {
    const result = renderMarkdown('```js\nconst x = 1\n```')
    expect(result).toContain('hljs')
  })
})
