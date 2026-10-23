/** Runtime checks for the public HTTP projection, shared by both catalogues. */
export function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}
export function text(value: unknown): value is string { return typeof value === 'string' }
export function numberOrNull(value: unknown): value is number | null {
  return value === null || (typeof value === 'number' && Number.isFinite(value) && value >= 0)
}
export function optionalText(value: unknown): value is string | null | undefined {
  return value == null || text(value)
}
export function arrayOf<T>(value: unknown, check: (item: unknown) => item is T): value is T[] {
  return Array.isArray(value) && value.every(check)
}
export function positiveInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 1
}
export function assetUrl(value: unknown): value is string {
  return text(value) && /^\/api\/modules\/[a-z0-9_-]+\/(?:cover|investigators\/[a-z0-9_-]+\/portrait)$/.test(value)
}

export class CatalogueHttpError extends Error {
  status: number
  constructor(status: number) {
    super(`Catalogue request failed: HTTP ${status}`)
    this.status = status
  }
}

export async function fetchCatalogue<T>(url: string, signal: AbortSignal, validate: (data: unknown) => data is T): Promise<T> {
  signal.throwIfAborted()
  const response = await fetch(url, { signal, headers: { Accept: 'application/json' } })
  if (!response.ok) throw new CatalogueHttpError(response.status)
  const data: unknown = await response.json()
  signal.throwIfAborted()
  if (!validate(data)) throw new Error('Unexpected catalogue response')
  return data
}
