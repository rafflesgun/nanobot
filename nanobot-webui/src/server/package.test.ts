import { readFileSync } from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'

const packageJson = JSON.parse(readFileSync(path.join(process.cwd(), 'package.json'), 'utf8')) as {
  dependencies?: Record<string, string>
  devDependencies?: Record<string, string>
}

describe('runtime dependencies', () => {
  it('ships ws with production dependencies because chatBridge imports it at runtime', () => {
    expect(packageJson.dependencies).toHaveProperty('ws')
    expect(packageJson.devDependencies).not.toHaveProperty('ws')
  })
})
