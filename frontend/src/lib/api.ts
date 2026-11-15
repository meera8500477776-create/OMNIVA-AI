export type ApiErrorKind = 'network' | 'timeout' | 'unauthorized' | 'forbidden' | 'not-found' | 'validation' | 'rate-limited' | 'server' | 'unknown'
export class ApiError extends Error {
  constructor(public kind: ApiErrorKind, message: string, public status?: number, public requestId?: string, public fieldErrors?: Record<string, string>) {
    super(message); this.name = 'ApiError'
  }
}

const baseUrl = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1').replace(/\/$/, '')
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), 15_000)
  const requestId = crypto.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`
  try {
    const response = await fetch(`${baseUrl}${path}`, {
      ...init, credentials: 'include', signal: init.signal ?? controller.signal,
      headers: { 'Content-Type': 'application/json', 'X-Request-ID': requestId, ...init.headers },
    })
    const body = response.status === 204 ? undefined : await response.json().catch(() => undefined)
    if (!response.ok) {
      const err = body?.error ?? body?.detail ?? {}
      const status = response.status
      const kind: ApiErrorKind = status === 401 ? 'unauthorized' : status === 403 ? 'forbidden' : status === 404 ? 'not-found' : status === 422 ? 'validation' : status === 429 ? 'rate-limited' : status >= 500 ? 'server' : 'unknown'
      throw new ApiError(kind, typeof err === 'string' ? err : err.message || `Request failed (${status})`, status, err.request_id ?? requestId, err.field_errors)
    }
    return body as T
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (error instanceof DOMException && error.name === 'AbortError') throw new ApiError('timeout', 'The request took too long. Please try again.', undefined, requestId)
    if (error instanceof TypeError) throw new ApiError('network', 'We could not reach the Omniva service. Check your connection and try again.', undefined, requestId)
    throw new ApiError('unknown', 'Something went wrong. Please try again.', undefined, requestId)
  } finally { window.clearTimeout(timeout) }
}
export const appMode: 'demo' | 'live' = import.meta.env.VITE_APP_MODE === 'live' || import.meta.env.PROD ? 'live' : 'demo'
