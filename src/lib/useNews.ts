import { useEffect, useState } from 'react'
import { fetchNews, type NewsCollection } from './news'

const empty: NewsCollection = { articles: [], fetchedCount: 0, demoCount: 0, sourceCount: 0, latestFetchedAt: '' }
let cache: NewsCollection | null = null

export function useNews() {
  const [data, setData] = useState<NewsCollection>(cache || empty)
  const [loading, setLoading] = useState(!cache)
  const [error, setError] = useState('')
  useEffect(() => {
    if (cache) return
    let active = true
    fetchNews().then((result) => {
      cache = result
      if (active) setData(result)
    }).catch((reason: unknown) => {
      if (active) setError(reason instanceof Error ? reason.message : 'Nyheterna kunde inte laddas.')
    }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])
  return { data, loading, error }
}
