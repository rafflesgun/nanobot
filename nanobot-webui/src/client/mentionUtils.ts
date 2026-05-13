import type { PublicInstance } from './api'

export type MentionResult = {
  mentionedIds: string[]
  text: string
}

export function parseMentions(text: string, members: PublicInstance[]): MentionResult {
  const tokens = text.match(/(?<=^|[\s])@(\w+)/g)
  if (!tokens) return { mentionedIds: [], text }
  const seen = new Set<string>()
  const ids: string[] = []
  let hasAll = false
  for (const token of tokens) {
    const name = token.slice(1)
    if (name.toLowerCase() === 'all') {
      hasAll = true
    }
  }
  if (hasAll) {
    for (const m of members) {
      if (!seen.has(m.id)) { seen.add(m.id); ids.push(m.id) }
    }
    return { mentionedIds: ids, text }
  }
  for (const token of tokens) {
    const name = token.slice(1)
    const match = members.find(m => m.name.toLowerCase() === name.toLowerCase())
    if (match && !seen.has(match.id)) { seen.add(match.id); ids.push(match.id) }
  }
  return { mentionedIds: ids, text }
}

export function isMentionTrigger(text: string, cursorPos: number, _before: string): boolean {
  if (cursorPos <= 0) return false
  if (text[cursorPos - 1] !== '@') return false
  if (cursorPos === 1) return true
  const before = text[cursorPos - 2]
  return before === ' ' || before === '\n' || before === '\t'
}

export function extractMentionQuery(text: string, cursorPos: number): { query: string; startIndex: number } | null {
  let i = cursorPos - 1
  while (i >= 0 && text[i] !== '@') i--
  if (i < 0) return null
  if (i > 0 && text[i - 1] !== ' ' && text[i - 1] !== '\n' && text[i - 1] !== '\t') return null
  const query = text.slice(i + 1, cursorPos)
  return { query, startIndex: i }
}
