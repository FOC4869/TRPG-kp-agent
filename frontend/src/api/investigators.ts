import { previewInvestigators } from '../data/investigators'
import { getPublicModule } from './modules'
import type { InvestigatorCatalogue, InvestigatorDetail, InvestigatorSummary } from '../types/investigators'

export class InvestigatorRequestError extends Error {
  code: 'module-unavailable' | 'investigator-unavailable'

  constructor(code: InvestigatorRequestError['code']) {
    super(code)
    this.name = 'InvestigatorRequestError'
    this.code = code
  }
}

async function requireModule(moduleId: string, signal: AbortSignal) {
  signal.throwIfAborted()
  const module = await getPublicModule({ id: moduleId, signal })
  signal.throwIfAborted()
  if (!module || module.status !== 'preview') throw new InvestigatorRequestError('module-unavailable')
  return { id: module.id, title: module.title }
}

/** Async client adapter. Replace mock reads after the HTTP contract is agreed. */
export async function listInvestigators({ moduleId, signal }: {
  moduleId: string
  signal: AbortSignal
}): Promise<InvestigatorCatalogue> {
  const module = await requireModule(moduleId, signal)
  signal.throwIfAborted()
  const items: InvestigatorSummary[] = previewInvestigators.map(({ id, name, displayName, occupation, age, portrait }) => ({ id, name, displayName, occupation, age, portrait }))
  return structuredClone({ module, items, source: 'mock' })
}

export async function getInvestigator({ moduleId, id, signal }: {
  moduleId: string
  id: string
  signal: AbortSignal
}): Promise<InvestigatorDetail> {
  await requireModule(moduleId, signal)
  signal.throwIfAborted()
  const investigator = previewInvestigators.find((candidate) => candidate.id === id)
  if (!investigator) throw new InvestigatorRequestError('investigator-unavailable')
  return structuredClone(investigator)
}
