import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, post } from '../lib/api'
import type { User } from '../types'

interface AuthContextValue {
  user: User | null
  loading: boolean
  refresh: () => Promise<void>
  login: (email: string, password: string) => Promise<void>
  register: (name: string, email: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const data = await api<{ user: User | null }>('/api/auth/me')
      setUser(data.user)
    } catch {
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void refresh() }, [refresh])

  const value = useMemo<AuthContextValue>(() => ({
    user,
    loading,
    refresh,
    login: async (email, password) => {
      const data = await post<{ user: User }>('/api/auth/login', { email, password })
      setUser(data.user)
    },
    register: async (name, email, password) => {
      const data = await post<{ user: User }>('/api/auth/register', { name, email, password })
      setUser(data.user)
    },
    logout: async () => {
      await post('/api/auth/logout', {})
      setUser(null)
    },
  }), [loading, refresh, user])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth måste användas i AuthProvider')
  return context
}
