import type { NewsArticle, NewsImage, NewsVideo, RawAiNewsImage, RawFetchedNews, RawGeneratedNewsImage, RawSeedNews, RawSourceNewsVideo } from '../types'

const aiCategoryImages: Record<string, { url: string; alt: string }> = {
  Hälsa: { url: '/news-images/ai/health.webp', alt: 'Redaktionell AI-illustration om hälsa, omsorg och återhämtning.' },
  Miljö: { url: '/news-images/ai/environment.webp', alt: 'Redaktionell AI-illustration om ren energi och miljöframsteg.' },
  Natur: { url: '/news-images/ai/nature.webp', alt: 'Redaktionell AI-illustration om natur, biologisk mångfald och återhämtning.' },
  Vetenskap: { url: '/news-images/ai/science.webp', alt: 'Redaktionell AI-illustration om vetenskap, upptäckter och delad kunskap.' },
  Kultur: { url: '/news-images/ai/culture.webp', alt: 'Redaktionell AI-illustration om kultur, kreativitet och restaurerat kulturarv.' },
  Människor: { url: '/news-images/ai/community.webp', alt: 'Redaktionell AI-illustration om lokalt samarbete och gemensamma idéer.' },
  Framsteg: { url: '/news-images/ai/progress.webp', alt: 'Redaktionell AI-illustration om praktiska lösningar och framsteg.' },
}

interface RawImageFields {
  id?: string
  title: string
  source_fingerprint?: string
  ai_image?: RawAiNewsImage
  generated_image?: RawGeneratedNewsImage
  source_image_verified?: boolean
  source_image_url?: string
  source_image_alt?: string
  source_image_credit?: string
  source_image_rights_url?: string
}

function safeHttpsUrl(value = ''): string {
  try {
    const parsed = new URL(value)
    return parsed.protocol === 'https:' && !parsed.username && !parsed.password ? parsed.href : ''
  } catch { return '' }
}

function resolveSourceVideo(video?: RawSourceNewsVideo): NewsVideo | undefined {
  if (!video || !['youtube', 'dailymotion'].includes(video.provider)) return undefined
  const embedUrl = safeHttpsUrl(video.embed_url)
  const sourceUrl = safeHttpsUrl(video.source_url)
  try {
    const embed = new URL(embedUrl)
    const source = new URL(sourceUrl)
    const validYouTube = video.provider === 'youtube'
      && /^[A-Za-z0-9_-]{11}$/.test(video.video_id)
      && embed.hostname === 'www.youtube-nocookie.com'
      && embed.pathname === `/embed/${video.video_id}`
      && ['youtube.com', 'www.youtube.com', 'youtu.be'].includes(source.hostname)
    const validDailymotion = video.provider === 'dailymotion'
      && /^x[a-z0-9]+$/.test(video.video_id)
      && embed.hostname === 'geo.dailymotion.com'
      && embed.pathname === '/player.html'
      && embed.searchParams.get('video') === video.video_id
      && source.hostname === 'www.dailymotion.com'
    if (!validYouTube && !validDailymotion) return undefined
  } catch { return undefined }
  return {
    provider: video.provider,
    videoId: video.video_id,
    embedUrl,
    sourceUrl,
    title: video.title?.trim() || 'Video från källan',
  }
}

export function getAiCategoryImage(category: string): NewsImage {
  const fallback = aiCategoryImages[category] || aiCategoryImages.Framsteg
  return {
    kind: 'ai',
    aiOrigin: 'category',
    url: fallback.url,
    alt: fallback.alt,
    caption: 'AI-illustration – redaktionellt motiv, inte en dokumentation av händelsen.',
    width: 1280,
    height: 853,
  }
}

function resolveSourceImage(item: RawImageFields): NewsImage | undefined {
  const sourceUrl = safeHttpsUrl(item.source_image_url)
  const rightsUrl = safeHttpsUrl(item.source_image_rights_url)
  const credit = item.source_image_credit?.trim() || ''
  if (item.source_image_verified === true && sourceUrl && rightsUrl && credit) {
    return {
      kind: 'source',
      url: sourceUrl,
      alt: item.source_image_alt?.trim() || `Källbild till ${item.title}`,
      caption: `Källbild · ${credit}`,
      credit,
      rightsUrl,
      width: 1280,
      height: 853,
    }
  }
  return undefined
}

function resolveAiImage(item: RawImageFields): NewsImage | undefined {
  const image = item.ai_image
  const id = item.id || ''
  const fingerprint = item.source_fingerprint || ''
  if (!image || !/^[a-f0-9]{20}$/.test(id) || !/^[a-f0-9]{20}$/.test(fingerprint)) return undefined
  const expectedUrl = `/news-images/ai/articles/${id}-${fingerprint.slice(0, 8)}-v1.webp`
  const validGeneratedAt = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/.test(image.generated_at)
  if (image.url !== expectedUrl
      || image.source_fingerprint !== fingerprint
      || image.model !== 'gpt-image-2'
      || image.prompt_version !== 'editorial-concept-v1'
      || image.width !== 1280
      || image.height !== 848
      || !/^[a-f0-9]{64}$/.test(image.sha256)
      || !image.alt?.trim()
      || !validGeneratedAt
      || Number.isNaN(Date.parse(image.generated_at))) return undefined
  return {
    kind: 'ai',
    aiOrigin: 'generated',
    url: image.url,
    alt: image.alt.trim(),
    caption: 'Unik AI-illustration – redaktionellt motiv, inte en dokumentation av händelsen.',
    width: image.width,
    height: image.height,
  }
}

function resolveAutomaticIllustration(item: RawImageFields): NewsImage | undefined {
  const image = item.generated_image
  const id = item.id || ''
  const fingerprint = item.source_fingerprint || ''
  if (!image || !/^[a-f0-9]{20}$/.test(id) || !/^[a-f0-9]{20}$/.test(fingerprint)) return undefined
  const expectedUrl = `/news-images/generated/${id}-${fingerprint.slice(0, 8)}-v1.svg`
  if (image.url !== expectedUrl
      || image.source_fingerprint !== fingerprint
      || image.style_version !== 'glimt-abstract-v1'
      || image.width !== 1280
      || image.height !== 848
      || !/^[a-f0-9]{64}$/.test(image.sha256)
      || !image.alt?.trim()) return undefined
  return {
    kind: 'generated',
    url: image.url,
    alt: image.alt.trim(),
    caption: 'Automatiskt skapad redaktionell illustration.',
    width: image.width,
    height: image.height,
  }
}

function resolveNewsImages(item: RawImageFields, category: string): Pick<NewsArticle, 'image' | 'fallbackImage'> {
  const categoryImage = getAiCategoryImage(category)
  const aiImage = resolveAiImage(item)
  const automaticIllustration = resolveAutomaticIllustration(item)
  const sourceImage = resolveSourceImage(item)
  if (sourceImage) return { image: sourceImage, fallbackImage: aiImage || automaticIllustration || categoryImage }
  if (aiImage) return { image: aiImage, fallbackImage: automaticIllustration || categoryImage }
  if (automaticIllustration) return { image: automaticIllustration, fallbackImage: categoryImage }
  return { image: categoryImage }
}

export function resolveNewsImage(item: RawImageFields, category: string): NewsImage {
  return resolveNewsImages(item, category).image
}

const categoryWords: Record<string, string[]> = {
  Djur: ['animal', 'bird', 'cat', 'dog', 'kitten', 'leopard', 'otter', 'pangolin', 'pet', 'puppy', 'turtle', 'wildlife'],
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
  const category = item.category?.trim() || inferCategory(item)
  return {
    id: item.id,
    slug: `${slugify(item.title)}-${item.id.slice(0, 6)}`,
    title: item.title,
    excerpt,
    category,
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
    publicEligible: typeof item.public_eligible === 'boolean' ? item.public_eligible : undefined,
    video: resolveSourceVideo(item.source_video),
    ...resolveNewsImages(item, category),
  }
}

export function normalizeSeed(item: RawSeedNews): NewsArticle {
  const category = item.category || 'Framsteg'
  return {
    id: item.id,
    slug: item.slug || slugify(item.title),
    title: item.title,
    excerpt: item.summary,
    category,
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
    ...resolveNewsImages(item, category),
  }
}

const sensitiveCandidate = /\b(?:abandon(?:ed|ment)?|abuse|anxiety|assault|backlash|blood|bloody|bomb|chronic loneliness|closing|conflict|criticiz(?:e|ed|es|ing)|crush(?:ed|ing)?|death|desperat(?:e|ely)|distress(?:ed|ing)?|earthquake|extinct(?:ion)?|extremism|fraud|gasp(?:ing)?|harass(?:ment|ed|ing)?|harrowing|hooks? in|injur(?:ed|y|ies)|killed|loathe|locked away|lost (?:a |both |back )?legs?|mange|mangled|missing flipper|murder|onlyfans|revok(?:e|ed|es|ing)|scared|shooting|shocked|sick|stranded|strangl(?:e|ed|es|ing)|stroke|stuck in|terror|terrified|threaten(?:ed|ing)?|traffick(?:ing|ed)?|trap(?:ped)?|traumatized|treatment center|unable to move|violence|war)\b/i
const feedNoise = /\b(?:appeared first on|share the stories)\b/i
const positiveCandidate = /\b(?:achiev(?:e|ed|ement)|adopt(?:ed|ion)?|adorable|award(?:ed|s)?|best friend|birth|breakthrough|celebrat(?:e|ed|es|ing|ion)|conservation(?:ist|ists)?|cuddl(?:e|ed|es|ing|y)|discov(?:er|ered|ery)|free(?:d|ing)?|friend(?:s|ship)?|help(?:s|ed|ing)?|hope(?:ful)?|improv(?:e|ed|ement)|kitten(?:s)?|lov(?:e|ed|es|ing)|milestone|play(?:s|ed|ing|ful)?|priceless|protect(?:s|ed|ing|ion)?|pupp(?:y|ies)|recover(?:ed|y)|rescu(?:e|ed|es|ing)|restor(?:e|ed|es|ing|ation)|save(?:d|s|ing)?|second chance|smooth(?:er|est)|solv(?:e|ed|es|ing)|spoil(?:s|ed|ing)?|success(?:ful)?|surpris(?:e|ed|es|ing)|together|treat(?:s|ed|ing)?|volunteer(?:s|ed|ing)?|win(?:s|ning)?)\b/i

export function isSuitableForPublicFeed(article: NewsArticle): boolean {
  if (article.origin === 'demo') return true
  if (typeof article.publicEligible === 'boolean') return article.publicEligible
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

async function fetchJson<T>(path: string, options?: RequestInit): Promise<T | null> {
  try {
    const response = await fetch(`${import.meta.env.BASE_URL}${path.replace(/^\//, '')}`, options)
    if (!response.ok) return null
    return (await response.json()) as T
  } catch {
    return null
  }
}

export async function fetchNews(): Promise<NewsCollection> {
  const [apiData, seedData] = await Promise.all([
    fetchJson<{ items?: RawFetchedNews[]; generated_at?: string }>('/api/news', { credentials: 'same-origin' }),
    fetchJson<{ articles?: RawSeedNews[] }>('/data/seed-news.json'),
  ])
  const staticData = apiData ? null : await fetchJson<{ items?: RawFetchedNews[]; generated_at?: string }>('/data/news.json')
  const fetchedData = apiData || staticData
  if (!fetchedData && !seedData) throw new Error('Nyhetsflödet kunde inte laddas.')
  const fetched = (fetchedData?.items ?? []).map(normalizeFetched).filter(isSuitableForPublicFeed)
  const demo = (seedData?.articles ?? []).map(normalizeSeed)
  const articles = [...demo, ...fetched].sort((a, b) => Date.parse(b.publishedAt) - Date.parse(a.publishedAt))
  return {
    articles,
    fetchedCount: fetched.length,
    demoCount: demo.length,
    sourceCount: new Set(fetched.map((item) => item.source)).size,
    latestFetchedAt: fetchedData?.generated_at || '',
    fetchedAvailable: Boolean(fetchedData),
    seedAvailable: Boolean(seedData),
    warning: !fetchedData
      ? 'Det automatiska flödet kunde inte hämtas. De svenska källsammanfattningarna visas fortfarande.'
      : !seedData
        ? 'Källsammanfattningarna kunde inte hämtas. De aktuella källnotiserna visas fortfarande.'
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
