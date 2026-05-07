import { describe, expect, it } from 'vitest'
import { escapeHtml, parseMarkdownTranscript } from './markdownTranscript'

describe('markdownTranscript', () => {
  it('parses headings, paragraphs, bullets, and inline code into structured blocks', () => {
    expect(parseMarkdownTranscript('# Summary\n\nReady with `code`.\n\n- first\n- second')).toEqual([
      { type: 'heading', level: 1, content: [{ type: 'text', text: 'Summary' }] },
      {
        type: 'paragraph',
        content: [
          { type: 'text', text: 'Ready with ' },
          { type: 'inlineCode', text: 'code' },
          { type: 'text', text: '.' }
        ]
      },
      {
        type: 'list',
        items: [
          [{ type: 'text', text: 'first' }],
          [{ type: 'text', text: 'second' }]
        ]
      }
    ])
  })

  it('parses fenced code blocks with their language and literal code', () => {
    expect(parseMarkdownTranscript('```ts\nconst value = `<x>`\n```')).toEqual([
      { type: 'code', language: 'ts', code: 'const value = `<x>`' }
    ])
  })

  it('escapes html without treating markdown punctuation as markup', () => {
    expect(escapeHtml('<img src=x onerror=alert(1)> & `safe`')).toBe(
      '&lt;img src=x onerror=alert(1)&gt; &amp; `safe`'
    )
  })
})
