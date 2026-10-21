export interface HealthResponse {
  status: 'ok'
  service: 'trpg-kp-backend'
}

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await fetch('/api/health', { signal })
  if (!response.ok) {
    throw new Error(`Health check failed: HTTP ${response.status}`)
  }
  const data: unknown = await response.json()
  if (
    typeof data !== 'object' || data === null ||
    !('status' in data) || data.status !== 'ok' ||
    !('service' in data) || data.service !== 'trpg-kp-backend'
  ) {
    throw new Error('Unexpected health response')
  }
  return { status: data.status, service: data.service }
}
