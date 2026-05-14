import { ref, computed, type Ref } from 'vue'
import type { Conversation } from '../../api'
import { normalizeTranscriptState } from '../../chatTranscript'

export type DateGroup = {
  label: string
  conversations: Conversation[]
}

export type UseConversationsOptions = {
  loadConversationsApi: (token: string) => Promise<Conversation[]>
  saveConversationsApi: (token: string, conversations: Conversation[]) => Promise<Conversation[]>
}

function generateId(): string {
  try {
    return crypto.randomUUID()
  } catch {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = Math.random() * 16 | 0
      return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16)
    })
  }
}

function getLastEntryDate(conv: Conversation): Date {
  const updatedAt = (conv as Record<string, unknown>).updatedAt
  if (typeof updatedAt === 'string') {
    return new Date(updatedAt)
  }
  if (conv.transcript?.entries?.length) {
    const last = conv.transcript.entries[conv.transcript.entries.length - 1]
    if (last?.timestamp) return new Date(last.timestamp)
  }
  return new Date(0)
}

function groupByDate(conversations: Conversation[]): DateGroup[] {
  const now = new Date()
  const todayStart = new Date(now)
  todayStart.setHours(0, 0, 0, 0)

  const yesterdayStart = new Date(todayStart)
  yesterdayStart.setDate(yesterdayStart.getDate() - 1)

  const weekAgoStart = new Date(todayStart)
  weekAgoStart.setDate(weekAgoStart.getDate() - 7)

  const groups: { label: string; cutoff: Date; items: Conversation[] }[] = [
    { label: 'Today', cutoff: todayStart, items: [] },
    { label: 'Yesterday', cutoff: yesterdayStart, items: [] },
    { label: 'Previous 7 Days', cutoff: weekAgoStart, items: [] },
  ]
  const older: Conversation[] = []

  for (const conv of conversations) {
    const date = getLastEntryDate(conv)
    if (date >= todayStart) {
      groups[0].items.push(conv)
    } else if (date >= yesterdayStart) {
      groups[1].items.push(conv)
    } else if (date >= weekAgoStart) {
      groups[2].items.push(conv)
    } else {
      older.push(conv)
    }
  }

  const result: DateGroup[] = []
  for (const g of groups) {
    if (g.items.length > 0) {
      result.push({ label: g.label, conversations: g.items })
    }
  }
  if (older.length > 0) {
    result.push({ label: 'Older', conversations: older })
  }

  return result
}

export function useConversations(options: UseConversationsOptions) {
  const conversations: Ref<Conversation[]> = ref<Conversation[]>([])
  const activeConversationId = ref<string | null>(null)

  const activeConversation = computed(() => {
    return conversations.value.find((c: Conversation) => c.id === activeConversationId.value) ?? null
  })

  const dateGroups = computed(() => groupByDate(conversations.value))

  async function loadConversations(token: string) {
    const loaded = await options.loadConversationsApi(token)
    for (const conv of loaded) {
      if (conv.transcript) normalizeTranscriptState(conv.transcript as any)
    }
    conversations.value = loaded
    if (conversations.value.length > 0) {
      activeConversationId.value = conversations.value[0].id
    } else {
      activeConversationId.value = null
    }
  }

  function createConversation(name: string, memberIds: string[]): Conversation {
    const conv = {
      id: generateId(),
      name,
      selectedIds: memberIds,
      transcript: { entries: [], debugEvents: [], nextEntryId: 1 },
      updatedAt: new Date().toISOString(),
    } as Conversation
    conversations.value = [conv, ...conversations.value]
    activeConversationId.value = conv.id
    return conv
  }

  function deleteConversation(id: string) {
    conversations.value = conversations.value.filter((c: Conversation) => c.id !== id)
    if (activeConversationId.value === id) {
      activeConversationId.value = conversations.value.length > 0 ? conversations.value[0].id : null
    }
  }

  function renameConversation(id: string, newName: string) {
    const conv = conversations.value.find((c: Conversation) => c.id === id)
    if (conv) {
      conv.name = newName
    }
  }

  function selectConversation(id: string) {
    activeConversationId.value = id
  }

  function touchConversation(id: string) {
    const conv = conversations.value.find((c: Conversation) => c.id === id)
    if (conv) {
      ;(conv as Record<string, unknown>).updatedAt = new Date().toISOString()
    }
  }

  async function persistConversations(token: string) {
    await options.saveConversationsApi(token, conversations.value)
  }

  return {
    conversations,
    activeConversationId,
    activeConversation,
    dateGroups,
    loadConversations,
    createConversation,
    deleteConversation,
    renameConversation,
    selectConversation,
    touchConversation,
    persistConversations,
  }
}
