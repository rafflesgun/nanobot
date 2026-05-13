import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const dashboardFiles = [
  'src/client/components/chat/ChatView.vue',
  'src/client/components/chat/ConversationSidebar.vue',
  'src/client/components/chat/ChatArea.vue',
  'src/client/components/chat/ChatHeader.vue',
  'src/client/components/chat/MessageBubble.vue',
  'src/client/components/chat/CodeBlock.vue',
  'src/client/components/chat/ChatComposer.vue',
  'src/client/components/chat/NewChatDialog.vue',
  'src/client/components/chat/AddMemberDialog.vue',
  'src/client/components/OverviewPanel.vue',
  'src/client/components/LogsPanel.vue',
  'src/client/components/AgentConfigPanel.vue',
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
