export type InlineToken =
  | { type: 'text'; text: string }
  | { type: 'inlineCode'; text: string }

export type MarkdownBlock =
  | { type: 'heading'; level: 1 | 2 | 3; content: InlineToken[] }
  | { type: 'paragraph'; content: InlineToken[] }
  | { type: 'list'; items: InlineToken[][] }
  | { type: 'code'; language: string; code: string }

export function escapeHtml(text: string) {
  return text
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

export function parseMarkdownTranscript(text: string): MarkdownBlock[] {
  const lines = text.replaceAll('\r\n', '\n').split('\n')
  const blocks: MarkdownBlock[] = []
  let index = 0

  while (index < lines.length) {
    const line = lines[index]
    if (line.trim() === '') {
      index++
      continue
    }

    const fence = line.match(/^```(\S*)\s*$/)
    if (fence) {
      const codeLines: string[] = []
      index++
      while (index < lines.length && !lines[index].startsWith('```')) {
        codeLines.push(lines[index])
        index++
      }
      if (index < lines.length) index++
      blocks.push({ type: 'code', language: fence[1] ?? '', code: codeLines.join('\n') })
      continue
    }

    const heading = line.match(/^(#{1,3})\s+(.+)$/)
    if (heading) {
      blocks.push({ type: 'heading', level: heading[1].length as 1 | 2 | 3, content: parseInline(heading[2]) })
      index++
      continue
    }

    if (isBullet(line)) {
      const items: InlineToken[][] = []
      while (index < lines.length && isBullet(lines[index])) {
        items.push(parseInline(lines[index].replace(/^\s*[-*]\s+/, '')))
        index++
      }
      blocks.push({ type: 'list', items })
      continue
    }

    const paragraphLines: string[] = []
    while (
      index < lines.length &&
      lines[index].trim() !== '' &&
      !lines[index].startsWith('```') &&
      !/^(#{1,3})\s+/.test(lines[index]) &&
      !isBullet(lines[index])
    ) {
      paragraphLines.push(lines[index])
      index++
    }
    blocks.push({ type: 'paragraph', content: parseInline(paragraphLines.join('\n')) })
  }

  return blocks
}

function isBullet(line: string) {
  return /^\s*[-*]\s+/.test(line)
}

function parseInline(text: string): InlineToken[] {
  const tokens: InlineToken[] = []
  const parts = text.split('`')
  for (let index = 0; index < parts.length; index++) {
    if (parts[index] === '') continue
    tokens.push({ type: index % 2 === 0 ? 'text' : 'inlineCode', text: parts[index] })
  }
  return tokens.length > 0 ? tokens : [{ type: 'text', text: '' }]
}
