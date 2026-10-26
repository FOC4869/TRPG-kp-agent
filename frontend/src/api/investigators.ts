import { arrayOf, assetUrl, CatalogueHttpError, fetchCatalogue, numberOrNull, record, text } from './catalogue'
import type { InvestigatorCatalogue, InvestigatorDetail, InvestigatorSummary } from '../types/investigators'

export class InvestigatorRequestError extends Error {
  code: 'module-unavailable' | 'investigator-unavailable'

  constructor(code: InvestigatorRequestError['code']) {
    super(code)
    this.name = 'InvestigatorRequestError'
    this.code = code
  }
}

function isSummary(value: unknown): value is InvestigatorSummary {
  return record(value) && text(value.id) && text(value.name) && text(value.displayName) && text(value.occupation)
    && (value.playable === undefined || typeof value.playable === 'boolean')
    && numberOrNull(value.age) && record(value.portrait) && assetUrl(value.portrait.url)
}

export function isDetail(value: unknown): value is InvestigatorDetail {
  if (!isSummary(value) || !record(value)) return false
  const { resources, attributes, cash } = value
  return text(value.overview) && record(resources) && record(attributes)
    && ['hp', 'hpMax', 'san', 'mp', 'mpMax', 'luck'].every((key) => numberOrNull(resources[key]))
    && ['STR', 'CON', 'SIZ', 'DEX', 'APP', 'INT', 'POW', 'EDU'].every((key) => numberOrNull(attributes[key]))
    && arrayOf(value.skills, (item): item is InvestigatorDetail['skills'][number] => record(item) && text(item.name) && numberOrNull(item.value) && typeof item.highlighted === 'boolean')
    && arrayOf(value.background, (item): item is InvestigatorDetail['background'][number] => record(item) && text(item.title) && (item.text === null || text(item.text)))
    && arrayOf(value.equipment, (item): item is InvestigatorDetail['equipment'][number] => record(item) && text(item.name) && numberOrNull(item.quantity) && (item.kind === 'carried' || item.kind === 'owned') && text(item.note))
    && (cash === null || (record(cash) && typeof cash.amount === 'number' && Number.isFinite(cash.amount) && cash.amount >= 0 && text(cash.currency)))
}

type ServerCatalogue = Omit<InvestigatorCatalogue, 'source'>
function isCatalogue(value: unknown): value is ServerCatalogue {
  return record(value) && record(value.module) && text(value.module.id) && text(value.module.title) && arrayOf(value.items, isSummary)
}

export async function listInvestigators({ moduleId, signal }: {
  moduleId: string
  signal: AbortSignal
}): Promise<InvestigatorCatalogue> {
  try {
    const result = await fetchCatalogue(`/api/modules/${encodeURIComponent(moduleId)}/investigators`, signal, isCatalogue)
    if (result.module.id !== moduleId) throw new Error('Unexpected module identity')
    return { ...result, source: 'api' }
  } catch (error) {
    if (error instanceof CatalogueHttpError && error.status === 404) throw new InvestigatorRequestError('module-unavailable')
    throw error
  }
}

export async function getInvestigator({ moduleId, id, signal }: {
  moduleId: string
  id: string
  signal: AbortSignal
}): Promise<InvestigatorDetail> {
  try {
    const result = await fetchCatalogue(`/api/modules/${encodeURIComponent(moduleId)}/investigators/${encodeURIComponent(id)}`, signal, isDetail)
    if (result.id !== id) throw new Error('Unexpected investigator identity')
    return result
  } catch (error) {
    if (error instanceof CatalogueHttpError && error.status === 404) throw new InvestigatorRequestError('investigator-unavailable')
    throw error
  }
}
