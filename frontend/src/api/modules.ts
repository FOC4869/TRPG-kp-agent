import { arrayOf, assetUrl, CatalogueHttpError, fetchCatalogue, optionalText, positiveInteger, record, text } from './catalogue'

/** Player-public catalogue only. Never include Keeper notes or scenario state. */
export interface PublicModule {
  id: string
  caseNumber: string
  title: string
  englishTitle?: string | null
  status: 'preview' | 'coming-soon'
  cover?: string | null
  introduction: string[]
  era: string
  location: string
  playStyle: string
  originalPlayers: string
  contentNote?: string | null
}

export interface ModulePage {
  items: PublicModule[]
  page: number
  pageSize: number
  total: number
}

function isPublicModule(value: unknown): value is PublicModule {
  return record(value) && text(value.id) && text(value.caseNumber) && text(value.title) && optionalText(value.englishTitle)
    && (value.status === 'preview' || value.status === 'coming-soon') && (value.cover == null || assetUrl(value.cover))
    && arrayOf(value.introduction, text) && text(value.era) && text(value.location) && text(value.playStyle)
    && text(value.originalPlayers) && optionalText(value.contentNote)
}

function isModulePage(value: unknown): value is ModulePage {
  return record(value) && arrayOf(value.items, isPublicModule) && positiveInteger(value.page)
    && positiveInteger(value.pageSize) && value.pageSize <= 30 && typeof value.total === 'number'
    && Number.isSafeInteger(value.total) && value.total >= 0 && value.items.length <= value.pageSize
    && value.items.length <= value.total && value.page <= Math.max(1, Math.ceil(value.total / value.pageSize))
}

export async function getPublicModule({ id, signal }: { id: string; signal: AbortSignal }): Promise<PublicModule | null> {
  try {
    const result = await fetchCatalogue(`/api/modules/${encodeURIComponent(id)}`, signal, isPublicModule)
    if (result.id !== id) throw new Error('Unexpected module identity')
    return result
  } catch (error) {
    if (error instanceof CatalogueHttpError && error.status === 404) return null
    throw error
  }
}

export async function listPublicModules({ page, pageSize, signal }: {
  page: number
  pageSize: number
  signal: AbortSignal
}): Promise<ModulePage> {
  const query = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  return fetchCatalogue(`/api/modules?${query}`, signal, isModulePage)
}
