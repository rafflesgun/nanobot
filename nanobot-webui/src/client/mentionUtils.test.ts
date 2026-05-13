import { describe, expect, it } from 'vitest'
import { parseMentions, extractMentionQuery, isMentionTrigger } from './mentionUtils'
import type { PublicInstance } from './api'

const members: PublicInstance[] = [
  { id: 'a1', name: 'Alpha', baseUrl: '', enabled: true },
  { id: 'b2', name: 'Beta', baseUrl: '', enabled: true },
  { id: 'g3', name: 'Gamma', baseUrl: '', enabled: true },
]

describe('parseMentions', () => {
  it('returns empty mentionedIds when no @mentions in text', () => {
    const result = parseMentions('hello world', members)
    expect(result.mentionedIds).toEqual([])
  })

  it('matches single @mention by name (case-insensitive)', () => {
    const result = parseMentions('@alpha how are you?', members)
    expect(result.mentionedIds).toEqual(['a1'])
  })

  it('matches multiple @mentions', () => {
    const result = parseMentions('@Alpha @Beta please collaborate', members)
    expect(result.mentionedIds).toEqual(['a1', 'b2'])
  })

  it('resolves @all to all member IDs', () => {
    const result = parseMentions('@all team update', members)
    expect(result.mentionedIds).toEqual(['a1', 'b2', 'g3'])
  })

  it('@all wins over individual mentions', () => {
    const result = parseMentions('@Alpha @all hi', members)
    expect(result.mentionedIds).toEqual(['a1', 'b2', 'g3'])
  })

  it('ignores @mention of non-member', () => {
    const result = parseMentions('@Unknown hello', members)
    expect(result.mentionedIds).toEqual([])
  })

  it('does not match mid-word @', () => {
    const result = parseMentions('email@domain.com', members)
    expect(result.mentionedIds).toEqual([])
  })

  it('deduplicates mentioned IDs', () => {
    const result = parseMentions('@Alpha @Alpha again', members)
    expect(result.mentionedIds).toEqual(['a1'])
  })

  it('returns text unchanged', () => {
    const text = '@Alpha check this out'
    const result = parseMentions(text, members)
    expect(result.text).toBe(text)
  })
})

describe('isMentionTrigger', () => {
  it('returns true for @ at position 0', () => {
    expect(isMentionTrigger('@', 0, '')).toBe(false)
  })

  it('returns true for @ at position 1 (start of text)', () => {
    expect(isMentionTrigger('@', 1, '')).toBe(true)
  })

  it('returns true for @ after space', () => {
    expect(isMentionTrigger('hello @', 7, 'hello ')).toBe(true)
  })

  it('returns true for @ after newline', () => {
    expect(isMentionTrigger('hello\n@', 7, 'hello\n')).toBe(true)
  })

  it('returns false for mid-word @', () => {
    expect(isMentionTrigger('email@', 5, 'email')).toBe(false)
  })
})

describe('extractMentionQuery', () => {
  it('extracts query after @ at end of text', () => {
    expect(extractMentionQuery('hello @al', 9)).toEqual({ query: 'al', startIndex: 6 })
  })

  it('extracts empty query right after @', () => {
    expect(extractMentionQuery('hello @', 7)).toEqual({ query: '', startIndex: 6 })
  })

  it('returns null when cursor is not after @mention', () => {
    expect(extractMentionQuery('hello world', 5)).toBeNull()
  })

  it('returns null for mid-word @', () => {
    expect(extractMentionQuery('email@domain', 6)).toBeNull()
  })
})
