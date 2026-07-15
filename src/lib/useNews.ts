import { useCallback, useEffect, useState } from 'react'
import { fetchNews, type NewsCollection } from './news'

const empty: NewsCollection = { articles: [], fetchedCount: 0, demoCount: 0, sourceCount: 0, latestFetchedAt: '', fetchedAvailable: false, seedAvailable: false, warning: '' }
let cache: NewsCollection | null = null
let cacheTime = 0
let pending: Promise<NewsCollection> | null = null
const CACHE_TTL = 5 * 60 * 1000

function loadNews(force = false): Promise<NewsCollection> {
  if (!force && cache && Date.now() - cacheTime < CACHE_TTL) return Promise.resolve(cache)
  if (pending) return pending
  pending = fetchNews().then((result) => {
    cache = result
    cacheTime = Date.now()
    return result
  }).finally(() => { pending = null })
  return pending
}

export function useNews() {
  const [data, setData] = useState<NewsCollection>(cache || empty)
  const [loading, setLoading] = useState(!cache)
  const [error, setError] = useState('')
  const refresh = useCallback(async (force = true) => {
    setLoading(!cache)
    setError('')
    try {
      const result = await loadNews(force)
      setData(result)
      return result
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Nyheterna kunde inte laddas.')
      throw reason
    } finally {
      setLoading(false)
    }
  }, [])
  useEffect(() => {
    let active = true
    loadNews().then((result) => {
      if (active) setData(result)
    }).catch((reason: unknown) => {
      if (active) setError(reason instanceof Error ? reason.message : 'Nyheterna kunde inte laddas.')
    }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])
  return { data, loading, error, refresh }
}
