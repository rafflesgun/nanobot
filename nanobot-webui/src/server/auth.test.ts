import { describe, expect, it } from 'vitest'
import { isDashboardAuthorized } from './auth'

describe('isDashboardAuthorized', () => {
  it('accepts bearer token only', () => {
    expect(isDashboardAuthorized({ authorization: 'Bearer dashboard' }, 'dashboard')).toBe(true)
    expect(isDashboardAuthorized({ authorization: 'Bearer wrong' }, 'dashboard')).toBe(false)
    expect(isDashboardAuthorized({}, 'dashboard')).toBe(false)
  })

  it('rejects tokens with unequal UTF-8 byte lengths without throwing', () => {
    expect(() => isDashboardAuthorized({ authorization: 'Bearer a' }, 'é')).not.toThrow()
    expect(isDashboardAuthorized({ authorization: 'Bearer a' }, 'é')).toBe(false)
  })
})
