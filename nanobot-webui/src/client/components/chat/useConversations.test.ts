import { describe, expect, it, vi } from 'vitest'
import { useConversations } from './useConversations'
import type { Conversation } from '../../api'

function makeConversation(overrides: Partial<Conversation> & { id: string }): Conversation {
  return {
    name: overrides.name ?? `Conv ${overrides.id}`,
    selectedIds: overrides.selectedIds ?? [],
    chatMappings: overrides.chatMappings,
    transcript: overrides.transcript ?? { entries: [], debugEvents: [] },
    ...overrides,
  }
}

function makeDateGroupsSetup() {
  const now = new Date()
  const today = makeConversation({ id: '1', name: 'Today Conv' } as any)
  ;(today as any).updatedAt = now.toISOString()

  const yesterdayDate = new Date(now)
  yesterdayDate.setDate(yesterdayDate.getDate() - 1)
  const yesterday = makeConversation({ id: '2', name: 'Yesterday Conv' } as any)
  ;(yesterday as any).updatedAt = yesterdayDate.toISOString()

  const weekAgoDate = new Date(now)
  weekAgoDate.setDate(weekAgoDate.getDate() - 5)
  const weekAgo = makeConversation({ id: '3', name: 'Week Conv' } as any)
  ;(weekAgo as any).updatedAt = weekAgoDate.toISOString()

  const olderDate = new Date(now)
  olderDate.setDate(olderDate.getDate() - 30)
  const older = makeConversation({ id: '4', name: 'Older Conv' } as any)
  ;(older as any).updatedAt = olderDate.toISOString()

  return [today, yesterday, weekAgo, older]
}

describe('useConversations', () => {
  it('loads conversations from API', async () => {
    const mockConvs = [makeConversation({ id: 'a' }), makeConversation({ id: 'b' })]
    const loadApi = vi.fn().mockResolvedValue(mockConvs)
    const { conversations, loadConversations } = useConversations({ loadConversationsApi: loadApi, saveConversationsApi: vi.fn() })
    await loadConversations('token123')
    expect(loadApi).toHaveBeenCalledWith('token123')
    expect(conversations.value).toEqual(mockConvs)
  })

  it('sets first conversation as active after loading', async () => {
    const mockConvs = [makeConversation({ id: 'a' }), makeConversation({ id: 'b' })]
    const loadApi = vi.fn().mockResolvedValue(mockConvs)
    const { activeConversationId, loadConversations } = useConversations({ loadConversationsApi: loadApi, saveConversationsApi: vi.fn() })
    await loadConversations('tok')
    expect(activeConversationId.value).toBe('a')
  })

  it('creates a new conversation and selects it', () => {
    const { conversations, activeConversationId, createConversation } = useConversations({
      loadConversationsApi: vi.fn(),
      saveConversationsApi: vi.fn(),
    })
    const conv = createConversation('New Chat', ['inst1'])
    expect(conv.name).toBe('New Chat')
    expect(conv.selectedIds).toEqual(['inst1'])
    expect(conv.transcript.entries).toEqual([])
    expect(conversations.value[0]).toStrictEqual(conv)
    expect(activeConversationId.value).toBe(conv.id)
  })

  it('deletes a conversation', () => {
    const { conversations, activeConversationId, createConversation, deleteConversation } = useConversations({
      loadConversationsApi: vi.fn(),
      saveConversationsApi: vi.fn(),
    })
    const c1 = createConversation('One', [])
    const c2 = createConversation('Two', [])
    expect(conversations.value).toHaveLength(2)
    deleteConversation(c1.id)
    expect(conversations.value).toHaveLength(1)
    expect(conversations.value[0].id).toBe(c2.id)
  })

  it('re-selects first conversation if active one is deleted', () => {
    const { createConversation, activeConversationId, deleteConversation } = useConversations({
      loadConversationsApi: vi.fn(),
      saveConversationsApi: vi.fn(),
    })
    const c1 = createConversation('One', [])
    const c2 = createConversation('Two', [])
    expect(activeConversationId.value).toBe(c2.id)
    deleteConversation(c2.id)
    expect(activeConversationId.value).toBe(c1.id)
  })

  it('renames a conversation', () => {
    const { createConversation, renameConversation, conversations } = useConversations({
      loadConversationsApi: vi.fn(),
      saveConversationsApi: vi.fn(),
    })
    const c = createConversation('Original', [])
    renameConversation(c.id, 'Renamed')
    expect(conversations.value.find((x: Conversation) => x.id === c.id)!.name).toBe('Renamed')
  })

  it('selects a conversation', () => {
    const { createConversation, selectConversation, activeConversationId } = useConversations({
      loadConversationsApi: vi.fn(),
      saveConversationsApi: vi.fn(),
    })
    const c1 = createConversation('One', [])
    const c2 = createConversation('Two', [])
    selectConversation(c1.id)
    expect(activeConversationId.value).toBe(c1.id)
  })

  it('activeConversation returns the full conversation object', () => {
    const { createConversation, activeConversation, selectConversation } = useConversations({
      loadConversationsApi: vi.fn(),
      saveConversationsApi: vi.fn(),
    })
    const c1 = createConversation('One', [])
    createConversation('Two', [])
    selectConversation(c1.id)
    expect(activeConversation.value).toBeDefined()
    expect(activeConversation.value!.id).toBe(c1.id)
    expect(activeConversation.value!.name).toBe('One')
  })

  it('groups conversations by date', async () => {
    const convs = makeDateGroupsSetup()
    const loadApi = vi.fn().mockResolvedValue(convs)
    const { loadConversations, dateGroups } = useConversations({ loadConversationsApi: loadApi, saveConversationsApi: vi.fn() })
    await loadConversations('tok')
    const groupNames = dateGroups.value.map(g => g.label)
    expect(groupNames).toContain('Today')
    expect(groupNames).toContain('Yesterday')
    expect(groupNames).toContain('Previous 7 Days')
    expect(groupNames).toContain('Older')
  })

  it('persists conversations via save API', async () => {
    const saveApi = vi.fn().mockResolvedValue([])
    const { createConversation, persistConversations } = useConversations({
      loadConversationsApi: vi.fn(),
      saveConversationsApi: saveApi,
    })
    createConversation('Chat', [])
    await persistConversations('tok')
    expect(saveApi).toHaveBeenCalledWith('tok', expect.any(Array))
    expect(saveApi.mock.calls[0][1]).toHaveLength(1)
  })
})
