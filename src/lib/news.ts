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
  const agentSummary = item.agent_summary?.trim() || ''
  const excerpt = agentSummary || item.source_excerpt?.trim() || 'Kort källnotis utan sammanfattning.'
  const language = item.language || 'en'
  return {
    id: item.id,
    slug: `${slugify(item.title)}-${item.id.slice(0, 6)}`,
    title: item.title,
    excerpt,
    category: inferCategory(item),
    location: '',
    publishedAt: item.published_at || '',
    readTime: Math.max(1, Math.ceil(excerpt.split(/\s+/).length / 180)),
    featured: false,
    source: item.source || 'Extern källa',
    url: item.url,
    origin: 'fetched',
    language,
    excerptLanguage: agentSummary ? 'sv' : language,
    hasAgentSummary: Boolean(agentSummary),
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
    excerptLanguage: 'sv',
    hasAgentSummary: false,
    score: 0,
    signals: [],
  }
}

const sensitiveCandidate = /\b(?:abandon(?:ed|ment)?|abuse|anxiety|assault|backlash|blood|bloody|bomb|chronic loneliness|closing|conflict|criticiz(?:e|ed|es|ing)|crush(?:ed|ing)?|death|earthquake|extinct(?:ion)?|extremism|fraud|harass(?:ment|ed|ing)?|harrowing|hooks? in|injur(?:ed|y|ies)|killed|loathe|mangled|missing flipper|murder|onlyfans|revok(?:e|ed|es|ing)|shooting|shocked|strangl(?:e|ed|es|ing)|stroke|terror|threaten(?:ed|ing)?|traffick(?:ing|ed)?|trapped|treatment center|violence|war)\b/i
const feedNoise = /\b(?:appeared first on|share the stories)\b/i
const positiveCandidate = /\b(?:achiev(?:e|ed|ement)|award(?:ed|s)?|birth|breakthrough|celebrat(?:e|ed|es|ing|ion)|conservation(?:ist|ists)?|discov(?:er|ered|ery)|free(?:d|ing)?|help(?:s|ed|ing)?|hope(?:ful)?|improv(?:e|ed|ement)|milestone|protect(?:s|ed|ing|ion)?|recover(?:ed|y)|rescu(?:e|ed|es|ing)|restor(?:e|ed|es|ing|ation)|save(?:d|s|ing)?|second chance|smooth(?:er|est)|solv(?:e|ed|es|ing)|success(?:ful)?|volunteer(?:s|ed|ing)?|win(?:s|ning)?)\b/i

export function isSuitableForPublicFeed(article: NewsArticle): boolean {
  if (article.origin === 'demo') return true
  return !article.title.trim().endsWith('?')
    && !sensitiveCandidate.test(`${article.title} ${article.excerpt}`)
    && !feedNoise.test(article.excerpt)
    && positiveCandidate.test(`${article.title} ${article.excerpt}`)
}

export interface NewsCollection {
  articles: NewsArticle[]
  fetchedCount: number
  demoCount: number
  sourceCount: number
  latestFetchedAt: string
  fetchedAvailable: boolean
  seedAvailable: boolean
  warning: string
}

export async function fetchNews(): Promise<NewsCollection> {
  const [fetchedResult, seedResult] = await Promise.allSettled([
    fetch('/api/news', { credentials: 'same-origin' }),
    fetch('/data/seed-news.json'),
  ])
  const fetchedResponse = fetchedResult.status === 'fulfilled' ? fetchedResult.value : null
  const seedResponse = seedResult.status === 'fulfilled' ? seedResult.value : null
  if (!fetchedResponse?.ok && !seedResponse?.ok) throw new Error('Nyhetsflödet kunde inte laddas.')
  const fetchedData = fetchedResponse?.ok
    ? (await fetchedResponse.json()) as { items?: RawFetchedNews[]; generated_at?: string }
    : { items: [] }
  const seedData = seedResponse?.ok
    ? (await seedResponse.json()) as { articles?: RawSeedNews[] }
    : { articles: [] }
  const fetched = (fetchedData.items ?? []).map(normalizeFetched).filter(isSuitableForPublicFeed)
  const demo = (seedData.articles ?? []).map(normalizeSeed)
  const articles = [...demo, ...fetched].sort((a, b) => Date.parse(b.publishedAt) - Date.parse(a.publishedAt))
  return {
    articles,
    fetchedCount: fetched.length,
    demoCount: demo.length,
    sourceCount: new Set(fetched.map((item) => item.source)).size,
    latestFetchedAt: fetchedData.generated_at || '',
    fetchedAvailable: Boolean(fetchedResponse?.ok),
    seedAvailable: Boolean(seedResponse?.ok),
    warning: !fetchedResponse?.ok
      ? 'Det automatiska nattflödet kunde inte hämtas. Demosammanfattningarna visas fortfarande.'
      : !seedResponse?.ok
        ? 'Demosammanfattningarna kunde inte hämtas. De aktuella källnotiserna visas fortfarande.'
        : '',
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
