import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, post, remove as deleteApi } from '../lib/api'
import type { NewsArticle, SavedArticle } from '../types'
import { useAuth } from './AuthContext'

interface SavedContextValue {
  saved: SavedArticle[]
  loading: boolean
  error: string
  isSaved: (id: string) => boolean
  toggle: (article: NewsArticle) => Promise<'saved' | 'removed' | 'login'>
  removeSaved: (id: string) => Promise<void>
  refresh: () => Promise<void>
}

const SavedContext = createContext<SavedContextValue | null>(null)

export function SavedProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const [saved, setSaved] = useState<SavedArticle[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const refresh = useCallback(async () => {
    if (!user) { setSaved([]); return }
    setLoading(true)
    setError('')
    try { setSaved((await api<{ articles: SavedArticle[] }>('/api/saved')).articles) }
    catch (reason) { setSaved([]); setError(reason instanceof Error ? reason.message : 'Läslistan kunde inte laddas.') }
    finally { setLoading(false) }
  }, [user])
  useEffect(() => { void refresh() }, [refresh])
  const value = useMemo<SavedContextValue>(() => ({
    saved, loading, error, refresh,
    isSaved: (id) => saved.some((item) => item.article_id === id),
    toggle: async (article) => {
      if (!user) return 'login'
      if (saved.some((item) => item.article_id === article.id)) {
        await deleteApi(`/api/saved/${encodeURIComponent(article.id)}`)
        setSaved((items) => items.filter((item) => item.article_id !== article.id))
        return 'removed'
      }
      const image = article.image.url.startsWith('/news-images/ai/') ? article.image.url : ''
      await post('/api/saved', { id: article.id, title: article.title, excerpt: article.excerpt, source: article.source, url: article.url, image })
      await refresh()
      return 'saved'
    },
    removeSaved: async (id) => {
      await deleteApi(`/api/saved/${encodeURIComponent(id)}`)
      setSaved((items) => items.filter((item) => item.article_id !== id))
    },
  }), [error, loading, refresh, saved, user])
  return <SavedContext.Provider value={value}>{children}</SavedContext.Provider>
}

export function useSaved() {
  const context = useContext(SavedContext)
  if (!context) throw new Error('useSaved måste användas i SavedProvider')
  return context
}
