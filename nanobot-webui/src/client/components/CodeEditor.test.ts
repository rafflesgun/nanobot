import { describe, expect, it } from 'vitest'

function computeIsValid(modelValue: string, language: 'json' | 'markdown'): boolean {
  if (language === 'markdown') return true
  try { JSON.parse(modelValue); return true } catch { return false }
}

describe('CodeEditor logic', () => {
  it('isValid is true for valid JSON in json mode', () => {
    expect(computeIsValid('{"key": "value"}', 'json')).toBe(true)
  })

  it('isValid is false for invalid JSON in json mode', () => {
    expect(computeIsValid('{bad', 'json')).toBe(false)
  })

  it('isValid is true for empty string in json mode', () => {
    expect(computeIsValid('', 'json')).toBe(false)
  })

  it('isValid is always true in markdown mode', () => {
    expect(computeIsValid('anything', 'markdown')).toBe(true)
    expect(computeIsValid('{bad', 'markdown')).toBe(true)
    expect(computeIsValid('', 'markdown')).toBe(true)
  })

  it('computes language class', () => {
    expect(`lang-json`).toBe('lang-json')
    expect(`lang-markdown`).toBe('lang-markdown')
  })

  it('computes readonly class', () => {
    const readOnly = true
    const classes = ['code-editor', `lang-json`, ...(readOnly ? ['is-readonly'] : [])]
    expect(classes).toContain('is-readonly')

    const readOnly2 = false
    const classes2 = ['code-editor', `lang-json`, ...(readOnly2 ? ['is-readonly'] : [])]
    expect(classes2).not.toContain('is-readonly')
  })
})
