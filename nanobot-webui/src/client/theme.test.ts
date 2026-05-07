import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const dashboardFiles = [
  'src/client/components/ChatPanel.vue',
  'src/client/components/OverviewPanel.vue',
  'src/client/components/LogsPanel.vue',
  'src/client/components/SettingsPanel.vue',
  'src/client/components/InstancesPanel.vue',
  'src/client/components/ManagePanel.vue'
]

describe('dashboard dark theme', () => {
  it('does not use bright card backgrounds in authenticated dashboard components', () => {
    const forbidden = ['background: #fbfdff', 'background: #fff;', 'border: 1px solid #dce4ef']
    for (const file of dashboardFiles) {
      const source = readFileSync(file, 'utf-8')
      for (const token of forbidden) expect(source, `${file} contains ${token}`).not.toContain(token)
    }
  })
})
