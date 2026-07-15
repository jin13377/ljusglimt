import type { NewsArticle, RawFetchedNews, RawSeedNews } from '../types'

const categoryWords: Record<string, string[]> = {
  Hälsa: ['health', 'medical', 'vaccine', 'malaria', 'care', 'brain', 'stroke', 'hospital', 'dementia'],
  Miljö: ['climate', 'energy', 'solar', 'carbon', 'air', 'water', 'plastic', 'environment'],
  Natur: ['nature', 'wildlife', 'forest', 'ocean', 'bird', 'species', 'restoration', 'biodiversity'],
  Vetenskap: ['science', 'research', 'nasa', 'space', 'study', 'technology', 'data'],
  Kultur: ['culture', 'music', 'dance', 'art', 'book', 'creative', 'heritage'],
  Människor: ['community', 'people', 'youth', 'school', 'refugee', 'social', 'local', 'together'],
}

export function inferCategory(item: RawFetchedNews): string {
  const text = `${item.title} ${item.source} ${(item.positive_signals ?? []).join(' ')}`.toLocaleLowerCase('en')
  let best = 'Framsteg'
  let bestScore = 0
  for (const [category, words] of Object.entries(categoryWords)) {
    const score = words.reduce((sum, word) => sum + (text.includes(word) ? 1 : 0), 0)
    if (score > bestScore) {
      best = category
      bestScore = score
    }
  }
  return best
}

export function slugify(value: string): string {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLocaleLowerCase('sv')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 90)
}

export function normalizeFetched(item: RawFetchedNews): NewsArticle {
  const excerpt = item.agent_summary?.trim() || item.source_excerpt?.trim() || 'Kort källnotis utan sammanfattning.'
  return {
    id: item.id,
    slug: `${slugify(item.title)}-${item.id.slice(0, 6)}`,
    title: item.title,
    excerpt,
    category: inferCategory(item),
    location: item.language === 'sv' ? 'Sverige' : 'Världen',
    publishedAt: item.published_at || '',
    readTime: Math.max(1, Math.ceil(excerpt.split(/\s+/).length / 180)),
    featured: false,
    source: item.source || 'Extern källa',
    url: item.url,
    origin: 'fetched',
    language: item.language || 'en',
    score: item.positivity_score || 0,
    signals: item.positive_signals || [],
  }
}

export function normalizeSeed(item: RawSeedNews): NewsArticle {
  return {
    id: item.id,
    slug: item.slug || slugify(item.title),
    title: item.title,
    excerpt: item.summary,
    category: item.category || 'Framsteg',
    location: item.location || 'Världen',
    publishedAt: item.publishedAt || '',
    readTime: item.readTimeMinutes || Math.max(1, Math.ceil(item.summary.split(/\s+/).length / 180)),
    featured: Boolean(item.featured),
    source: item.source.name,
    url: item.source.url,
    origin: 'demo',
    language: 'sv',
    score: 0,
    signals: [],
  }
}

export interface NewsCollection {
  articles: NewsArticle[]
  fetchedCount: number
  demoCount: number
  sourceCount: number
  latestFetchedAt: string
}

export async function fetchNews(): Promise<NewsCollection> {
  const [fetchedResponse, seedResponse] = await Promise.all([
    fetch('/api/news', { credentials: 'same-origin' }),
    fetch('/data/seed-news.json'),
  ])
  if (!fetchedResponse.ok) throw new Error('Nyhetsflödet kunde inte laddas.')
  const fetchedData = (await fetchedResponse.json()) as { items?: RawFetchedNews[]; generated_at?: string }
  const seedData = seedResponse.ok
    ? ((await seedResponse.json()) as { articles?: RawSeedNews[] })
    : { articles: [] }
  const fetched = (fetchedData.items ?? []).map(normalizeFetched)
  const demo = (seedData.articles ?? []).map(normalizeSeed)
  const articles = [...demo, ...fetched].sort((a, b) => Date.parse(b.publishedAt) - Date.parse(a.publishedAt))
  return {
    articles,
    fetchedCount: fetched.length,
    demoCount: demo.length,
    sourceCount: new Set(fetched.map((item) => item.source)).size,
    latestFetchedAt: fetchedData.generated_at || '',
  }
}

export const formatDate = (value: string, withTime = false) => {
  const date = new Date(value)
  if (Number.isNaN(date.valueOf())) return 'Datum saknas'
  return new Intl.DateTimeFormat('sv-SE', withTime
    ? { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }
    : { day: 'numeric', month: 'long', year: 'numeric' }).format(date)
}

export const excerpt = (value: string, length = 190) => value.length > length ? `${value.slice(0, length).trim()}…` : value
