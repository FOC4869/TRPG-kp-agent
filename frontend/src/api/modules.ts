import { previewModules } from '../data/modules'

/** Player-public catalogue only. Never include Keeper notes or scenario state. */
export interface PublicModule {
  id: string
  caseNumber: string
  title: string
  englishTitle?: string
  status: 'preview' | 'coming-soon'
  cover?: string
  introduction: string[]
  era: string
  location: string
  playStyle: string
  originalPlayers: string
  contentNote?: string
}

export interface ModulePage {
  items: PublicModule[]
  page: number
  pageSize: number
  total: number
}

export async function getPublicModule({ id, signal }: { id: string; signal: AbortSignal }): Promise<PublicModule | null> {
  signal.throwIfAborted()
  await Promise.resolve()
  signal.throwIfAborted()
  return structuredClone(previewModules.find((module) => module.id === id) ?? null)
}

/** Local preview adapter. Replace its body when a real GET contract is agreed. */
export async function listPublicModules({ page, pageSize, signal }: {
  page: number
  pageSize: number
  signal: AbortSignal
}): Promise<ModulePage> {
  signal.throwIfAborted()
  const size = Math.min(30, Math.max(1, Math.floor(pageSize) || 3))
  const total = previewModules.length
  const current = Math.min(Math.max(1, Math.floor(page) || 1), Math.max(1, Math.ceil(total / size)))
  return {
    items: previewModules.slice((current - 1) * size, current * size),
    page: current,
    pageSize: size,
    total,
  }
}
