import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, appMode, refreshSession, setAccessToken, type ApiUser, type AuthTokens } from './api'

export type User = { id: string; name: string; email: string; avatarUrl?: string }
type AuthValue = {
  user: User | null
  loading: boolean
  mode: 'demo' | 'live'
  login: (email: string, password: string) => Promise<void>
  register: (name: string, email: string, password: string) => Promise<void>
  forgot: (email: string) => Promise<void>
  logout: () => Promise<void>
  updateProfile: (name: string) => Promise<void>
}

const Context = createContext<AuthValue | null>(null)
const key = 'omniva.session.v1'
const demo: User = { id: 'demo-learner', name: 'Avery Morgan', email: 'demo@omniva.ai' }
const demoPassword = 'learn123'

function fromApiUser(user: ApiUser): User {
  return { id: user.id, name: user.display_name, email: user.email }
}

function setDemoUser(user: User) {
  sessionStorage.setItem(key, JSON.stringify(user))
  return user
}

function readDemoUser(): User | null {
  if (appMode !== 'demo') return null
  try { return JSON.parse(sessionStorage.getItem(key) || 'null') as User | null } catch { return null }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(readDemoUser)
  const [loading, setLoading] = useState(appMode === 'live')

  useEffect(() => {
    if (appMode !== 'live') return
    let alive = true
    const expired = () => { if (alive) setUser(null) }
    window.addEventListener('omniva:session-expired', expired)
    refreshSession()
      .then((tokens) => { if (alive) setUser(fromApiUser(tokens.user)) })
      .catch(() => { if (alive) { setAccessToken(null); setUser(null) } })
      .finally(() => { if (alive) setLoading(false) })
    return () => {
      alive = false
      window.removeEventListener('omniva:session-expired', expired)
    }
  }, [])

  const value = useMemo<AuthValue>(() => ({
    user,
    loading,
    mode: appMode,
    async login(email, password) {
      if (appMode === 'demo') {
        if (email.toLowerCase() !== demo.email || password !== demoPassword) {
          throw new Error(`Use the clearly labeled demo account ${demo.email} and ${demoPassword}.`)
        }
        setUser(setDemoUser(demo))
        return
      }
      const tokens = await api<AuthTokens>('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      })
      setAccessToken(tokens.access_token)
      setUser(fromApiUser(tokens.user))
    },
    async register(name, email, password) {
      if (appMode === 'demo') {
        const next = { id: `demo-${Date.now()}`, name: name.trim(), email }
        setUser(setDemoUser(next))
        return
      }
      const tokens = await api<AuthTokens>('/auth/register', {
        method: 'POST',
        body: JSON.stringify({ email, password, display_name: name.trim() }),
      })
      setAccessToken(tokens.access_token)
      setUser(fromApiUser(tokens.user))
    },
    async forgot(email) {
      if (appMode === 'demo') return
      await api('/auth/password/forgot', { method: 'POST', body: JSON.stringify({ email }) })
    },
    async logout() {
      try {
        if (appMode === 'live') await api('/auth/logout', { method: 'POST', body: '{}' })
      } finally {
        sessionStorage.removeItem(key)
        setAccessToken(null)
        setUser(null)
      }
    },
    async updateProfile(name) {
      if (!user) throw new Error('Sign in before updating your profile.')
      if (appMode === 'demo') {
        setUser(setDemoUser({ ...user, name: name.trim() }))
        return
      }
      const updated = await api<ApiUser>('/auth/me', {
        method: 'PATCH',
        body: JSON.stringify({ display_name: name.trim() }),
      })
      setUser(fromApiUser(updated))
    },
  }), [user, loading])

  return <Context.Provider value={value}>{children}</Context.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const value = useContext(Context)
  if (!value) throw new Error('useAuth must be used inside AuthProvider')
  return value
}
