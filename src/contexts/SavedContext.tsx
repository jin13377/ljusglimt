import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, post, remove } from '../lib/api'
import type { NewsArticle, SavedArticle } from '../types'
import { useAuth } from './AuthContext'

interface SavedContextValue {
  saved: SavedArticle[]
  loading: boolean
  isSaved: (id: string) => boolean
  toggle: (article: NewsArticle) => Promise<'saved' | 'removed' | 'login'>
  refresh: () => Promise<void>
}

const SavedContext = createContext<SavedContextValue | null>(null)

export function SavedProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const [saved, setSaved] = useState<SavedArticle[]>([])
  const [loading, setLoading] = useState(false)
  const refresh = useCallback(async () => {
    if (!user) { setSaved([]); return }
    setLoading(true)
    try { setSaved((await api<{ articles: SavedArticle[] }>('/api/saved')).articles) }
    finally { setLoading(false) }
  }, [user])
  useEffect(() => { void refresh() }, [refresh])
  const value = useMemo<SavedContextValue>(() => ({
    saved, loading, refresh,
    isSaved: (id) => saved.some((item) => item.article_id === id),
    toggle: async (article) => {
      if (!user) return 'login'
      if (saved.some((item) => item.article_id === article.id)) {
        await remove(`/api/saved/${encodeURIComponent(article.id)}`)
        setSaved((items) => items.filter((item) => item.article_id !== article.id))
        return 'removed'
      }
      await post('/api/saved', { id: article.id, title: article.title, excerpt: article.excerpt, source: article.source, url: article.url, image: '' })
      await refresh()
      return 'saved'
    },
  }), [loading, refresh, saved, user])
  return <SavedContext.Provider value={value}>{children}</SavedContext.Provider>
}

export function useSaved() {
  const context = useContext(SavedContext)
  if (!context) throw new Error('useSaved måste användas i SavedProvider')
  return context
}
