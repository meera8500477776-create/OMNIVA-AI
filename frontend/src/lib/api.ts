export type ApiErrorKind =
  | 'network'
  | 'timeout'
  | 'unauthorized'
  | 'forbidden'
  | 'not-found'
  | 'validation'
  | 'rate-limited'
  | 'server'
  | 'unknown'

export class ApiError extends Error {
  constructor(
    public kind: ApiErrorKind,
    message: string,
    public status?: number,
    public requestId?: string,
    public fieldErrors?: Record<string, string>,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

const baseUrl = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1').replace(/\/$/, '')
export const appMode: 'demo' | 'live' = import.meta.env.VITE_APP_MODE === 'live' ? 'live' : 'demo'
let accessToken: string | null = null
let refreshPromise: Promise<AuthTokens> | null = null

export type ApiUser = { id: string; email: string; display_name: string; roles?: string[] }
export type AuthTokens = { access_token: string; expires_in: number; user: ApiUser }

export function setAccessToken(token: string | null) {
  accessToken = token
}

function skipsRefresh(path: string) {
  return ['/auth/login', '/auth/register', '/auth/refresh', '/auth/password/forgot', '/auth/password/reset']
    .some((endpoint) => path === endpoint || path.startsWith(`${endpoint}?`))
}

function validationErrors(err: Record<string, unknown>): Record<string, string> | undefined {
  const fields = err.fields
  if (Array.isArray(fields)) {
    return Object.fromEntries(fields.map((field) => {
      const item = field as { field?: string; message?: string }
      return [item.field ?? 'request', item.message ?? 'Invalid value']
    }))
  }
  return typeof err.field_errors === 'object' && err.field_errors !== null
    ? err.field_errors as Record<string, string>
    : undefined
}

async function request<T>(path: string, init: RequestInit, allowRefresh: boolean, omitAuthorization = false): Promise<T> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), path.includes('/features/voice/') ? 150_000 : 15_000)
  const requestId = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`
  const headers = new Headers(init.headers)
  if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  headers.set('X-Request-ID', requestId)
  if (!omitAuthorization && accessToken && !skipsRefresh(path)) {
    headers.set('Authorization', `Bearer ${accessToken}`)
  }
  try {
    const response = await fetch(`${baseUrl}${path}`, {
      ...init,
      credentials: 'include',
      signal: init.signal ?? controller.signal,
      headers,
    })
    if (response.status === 401 && allowRefresh && accessToken && !skipsRefresh(path)) {
      try {
        await refreshSession()
        return request<T>(path, init, false)
      } catch {
        setAccessToken(null)
        window.dispatchEvent(new Event('omniva:session-expired'))
        throw new ApiError('unauthorized', 'Your session expired. Please sign in again.', 401, requestId)
      }
    }
    const body = response.status === 204 ? undefined : await response.json().catch(() => undefined)
    if (!response.ok) {
      const envelope = body?.error ?? body?.detail ?? {}
      const err = typeof envelope === 'object' && envelope !== null
        ? envelope as Record<string, unknown>
        : { message: String(envelope) }
      const status = response.status
      const kind: ApiErrorKind = status === 401 ? 'unauthorized'
        : status === 403 ? 'forbidden'
          : status === 404 ? 'not-found'
            : status === 422 ? 'validation'
              : status === 429 ? 'rate-limited'
                : status >= 500 ? 'server' : 'unknown'
      throw new ApiError(
        kind,
        typeof err.message === 'string' ? err.message : `Request failed (${status})`,
        status,
        typeof err.request_id === 'string' ? err.request_id : requestId,
        validationErrors(err),
      )
    }
    return body as T
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError('timeout', 'The request took too long. Please try again.', undefined, requestId)
    }
    if (error instanceof TypeError) {
      throw new ApiError('network', 'We could not reach the Omniva service. Check your connection and try again.', undefined, requestId)
    }
    throw new ApiError('unknown', 'Something went wrong. Please try again.', undefined, requestId)
  } finally {
    window.clearTimeout(timeout)
  }
}

export function api<T>(path: string, init: RequestInit = {}) {
  return request<T>(path, init, true)
}

export async function refreshSession(): Promise<AuthTokens> {
  if (!refreshPromise) {
    refreshPromise = request<AuthTokens>('/auth/refresh', { method: 'POST' }, false, true)
      .then((tokens) => {
        setAccessToken(tokens.access_token)
        return tokens
      })
      .finally(() => { refreshPromise = null })
  }
  return refreshPromise
}
