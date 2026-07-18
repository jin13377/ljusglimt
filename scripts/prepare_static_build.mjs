import { copyFile, mkdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const dist = process.env.LJUSGLIMT_DIST_DIR ? resolve(process.env.LJUSGLIMT_DIST_DIR) : resolve(root, 'dist')
const dataDir = process.env.LJUSGLIMT_DATA_DIR ? resolve(process.env.LJUSGLIMT_DATA_DIR) : resolve(root, 'data')
const output = resolve(dist, 'data')
const files = ['news.json', 'seed-news.json']
const siteUrl = 'https://ljusglimt.daniel-eklund1981.workers.dev'

const escapeXml = (value) => String(value).replace(/[<>&"']/g, (character) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;', "'": '&apos;' })[character])
const escapeHtml = (value) => String(value).replace(/[<>&"']/g, (character) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;', "'": '&#39;' })[character])
const slugify = (value) => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('sv').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 90)
const isText = (value) => typeof value === 'string' && Boolean(value.trim())
const safeHttpsUrl = (value = '') => {
  try {
    const parsed = new URL(value)
    return parsed.protocol === 'https:' && !parsed.username && !parsed.password ? parsed.href : ''
  } catch { return '' }
}
const absoluteImageUrl = (value = '') => {
  const httpsUrl = safeHttpsUrl(value)
  if (httpsUrl) return httpsUrl
  return /^\/news-images\/(?:ai|generated)\/[A-Za-z0-9._/-]+$/.test(value) && !value.includes('..') ? `${siteUrl}${value}` : ''
}
const categoryImages = {
  Hälsa: '/news-images/ai/health.webp',
  Miljö: '/news-images/ai/environment.webp',
  Natur: '/news-images/ai/nature.webp',
  Vetenskap: '/news-images/ai/science.webp',
  Kultur: '/news-images/ai/culture.webp',
  Människor: '/news-images/ai/community.webp',
  Framsteg: '/news-images/ai/progress.webp',
}

const resolveSourceImage = (article) => article.source_image_verified === true
  && safeHttpsUrl(article.source_image_rights_url)
  && isText(article.source_image_credit)
  ? safeHttpsUrl(article.source_image_url)
  : ''

const resolveAiImage = (article) => {
  const image = article.ai_image
  const id = article.id || ''
  const fingerprint = article.source_fingerprint || ''
  if (!image || !/^[a-f0-9]{20}$/.test(id) || !/^[a-f0-9]{20}$/.test(fingerprint)) return ''
  const expectedUrl = `/news-images/ai/articles/${id}-${fingerprint.slice(0, 8)}-v1.webp`
  const validGeneratedAt = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/.test(image.generated_at)
  return image.url === expectedUrl
    && image.source_fingerprint === fingerprint
    && image.model === 'gpt-image-2'
    && image.prompt_version === 'editorial-concept-v1'
    && image.width === 1280
    && image.height === 848
    && /^[a-f0-9]{64}$/.test(image.sha256)
    && isText(image.alt)
    && validGeneratedAt
    && !Number.isNaN(Date.parse(image.generated_at))
    ? expectedUrl
    : ''
}

const resolveGeneratedImage = (article) => {
  const image = article.generated_image
  const id = article.id || ''
  const fingerprint = article.source_fingerprint || ''
  if (!image || !/^[a-f0-9]{20}$/.test(id) || !/^[a-f0-9]{20}$/.test(fingerprint)) return ''
  const expectedUrl = `/news-images/generated/${id}-${fingerprint.slice(0, 8)}-v1.svg`
  return image.url === expectedUrl
    && image.source_fingerprint === fingerprint
    && image.style_version === 'glimt-abstract-v1'
    && image.width === 1280
    && image.height === 848
    && /^[a-f0-9]{64}$/.test(image.sha256)
    && isText(image.alt)
    ? expectedUrl
    : ''
}

const resolveArticleImage = (article, category) => absoluteImageUrl(
  resolveSourceImage(article)
  || resolveAiImage(article)
  || resolveGeneratedImage(article)
  || categoryImages[category]
  || categoryImages.Framsteg,
)

const requireArticleFields = (article, kind) => {
  for (const field of ['slug', 'title', 'description', 'publishedAt', 'category', 'source']) {
    if (!isText(article[field])) throw new Error(`${kind} article has invalid ${field}`)
  }
  if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(article.slug)) throw new Error(`${kind} article has unsafe slug: ${article.slug}`)
  if (Number.isNaN(Date.parse(article.publishedAt))) throw new Error(`${kind} article has invalid publishedAt: ${article.slug}`)
  return article
}

const [news, seed] = await Promise.all(files.map((file) => readFile(resolve(dataDir, file), 'utf8').then(JSON.parse)))
if (!Array.isArray(news.items) || !Array.isArray(seed.articles)) throw new Error('News data must contain items and articles arrays')

const sourceNames = {
  'NASA News Releases': 'NASA:s nyheter',
  'UN News': 'FN-nyheter',
}
const seedServerArticles = seed.articles.map((article) => {
  const category = isText(article.category) ? article.category : 'Framsteg'
  const normalized = requireArticleFields({
    slug: article.slug || (isText(article.title) ? slugify(article.title) : ''),
    title: article.title,
    description: article.summary,
    publishedAt: article.publishedAt,
    category,
    source: article.source?.name || 'Originalkälla',
    sourceUrl: safeHttpsUrl(article.source?.url),
    image: resolveArticleImage(article, category),
    origin: 'seed',
  }, 'Seed')
  return normalized
})
const fetchedServerArticles = news.items
  .filter((article) => article.public_eligible && article.display_title_sv && article.agent_summary)
  .map((article) => {
    if (!isText(article.title) || !/^[a-f0-9]{20}$/.test(article.id || '')) throw new Error('Fetched article has invalid title or id')
    const category = isText(article.category) ? article.category : 'Framsteg'
    return requireArticleFields({
      slug: `${slugify(article.title)}-${article.id.slice(0, 6)}`,
      title: article.display_title_sv,
      description: article.agent_summary,
      publishedAt: article.published_at,
      category,
      source: sourceNames[article.source] || article.source || 'Originalkälla',
      sourceUrl: safeHttpsUrl(article.url),
      image: resolveArticleImage(article, category),
      origin: 'fetched',
    }, 'Fetched')
  })
const serverArticles = [...seedServerArticles, ...fetchedServerArticles]
const slugs = new Set()
for (const article of serverArticles) {
  if (slugs.has(article.slug)) throw new Error(`Duplicate article slug: ${article.slug}`)
  slugs.add(article.slug)
}

const staticPages = [
  { path: '/', priority: '1.0', frequency: 'daily' },
  { path: '/sok', priority: '0.8', frequency: 'daily' },
  { path: '/forum', priority: '0.7', frequency: 'daily' },
  { path: '/om', priority: '0.5', frequency: 'monthly' },
]
const articlePages = serverArticles.map((article) => ({
  path: `/nyhet/${encodeURIComponent(article.slug)}`,
  updated: article.publishedAt,
  image: article.image,
  imageTitle: article.title,
}))

const upsertHead = (html, pattern, tag) => pattern.test(html)
  ? html.replace(pattern, tag)
  : html.replace('</head>', `${tag}\n</head>`)

const renderArticleHtml = (shell, article) => {
  const path = `/nyhet/${encodeURIComponent(article.slug)}`
  const canonical = `${siteUrl}${path}`
  const title = `${article.title} – Ljusglimt`
  const author = { '@type': 'Organization', name: article.source, ...(article.sourceUrl ? { url: article.sourceUrl } : {}) }
  const jsonLd = JSON.stringify({
    '@context': 'https://schema.org',
    '@type': 'NewsArticle',
    headline: article.title,
    description: article.description,
    image: [article.image],
    datePublished: article.publishedAt,
    dateModified: article.publishedAt,
    inLanguage: 'sv-SE',
    isAccessibleForFree: true,
    mainEntityOfPage: canonical,
    author,
    publisher: { '@type': 'Organization', name: 'Ljusglimt', url: siteUrl, logo: { '@type': 'ImageObject', url: `${siteUrl}/sun.svg` } },
    ...(article.sourceUrl ? { citation: article.sourceUrl } : {}),
    articleSection: article.category,
  }).replace(/</g, '\\u003c')

  let html = shell.replace(/<title>[\s\S]*?<\/title>/i, `<title>${escapeHtml(title)}</title>`)
  html = upsertHead(html, /<meta\s+name=["']description["'][^>]*>/i, `<meta name="description" content="${escapeHtml(article.description)}">`)
  html = upsertHead(html, /<link\s+rel=["']canonical["'][^>]*>/i, `<link rel="canonical" href="${canonical}">`)
  html = upsertHead(html, /<meta\s+property=["']og:title["'][^>]*>/i, `<meta property="og:title" content="${escapeHtml(title)}">`)
  html = upsertHead(html, /<meta\s+property=["']og:description["'][^>]*>/i, `<meta property="og:description" content="${escapeHtml(article.description)}">`)
  html = upsertHead(html, /<meta\s+property=["']og:type["'][^>]*>/i, '<meta property="og:type" content="article">')
  html = upsertHead(html, /<meta\s+property=["']og:url["'][^>]*>/i, `<meta property="og:url" content="${canonical}">`)
  html = upsertHead(html, /<meta\s+property=["']og:image["'][^>]*>/i, `<meta property="og:image" content="${escapeHtml(article.image)}">`)
  html = upsertHead(html, /<meta\s+name=["']twitter:title["'][^>]*>/i, `<meta name="twitter:title" content="${escapeHtml(title)}">`)
  html = upsertHead(html, /<meta\s+name=["']twitter:description["'][^>]*>/i, `<meta name="twitter:description" content="${escapeHtml(article.description)}">`)
  html = upsertHead(html, /<meta\s+name=["']twitter:image["'][^>]*>/i, `<meta name="twitter:image" content="${escapeHtml(article.image)}">`)
  html = html.replace('</head>', `<script type="application/ld+json" data-ljusglimt-jsonld="true">${jsonLd}</script>\n</head>`)
  const source = article.sourceUrl
    ? `<a href="${escapeHtml(article.sourceUrl)}">${escapeHtml(article.source)}</a>`
    : escapeHtml(article.source)
  const staticArticle = `<main><article><h1>${escapeHtml(article.title)}</h1><p>${escapeHtml(article.description)}</p><p>Källa: ${source}</p></article></main>`
  return html.replace(/<div\s+id=["']root["']\s*><\/div>/i, `<div id="root">${staticArticle}</div>`)
}

const urlEntry = ({ path, updated, priority, frequency, image, imageTitle }) => {
  const lastmod = updated && !Number.isNaN(Date.parse(updated)) ? `<lastmod>${new Date(updated).toISOString()}</lastmod>` : ''
  const changefreq = frequency ? `<changefreq>${frequency}</changefreq>` : ''
  const priorityTag = priority ? `<priority>${priority}</priority>` : ''
  const imageTag = image ? `<image:image><image:loc>${escapeXml(image)}</image:loc><image:title>${escapeXml(imageTitle)}</image:title></image:image>` : ''
  return `<url><loc>${escapeXml(`${siteUrl}${path}`)}</loc>${lastmod}${changefreq}${priorityTag}${imageTag}</url>`
}

const shell = await readFile(resolve(dist, 'index.html'), 'utf8')
const articleOutput = resolve(dist, 'seo', 'articles')
const sitemap = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n${[...staticPages, ...articlePages].map(urlEntry).join('\n')}\n</urlset>\n`

await mkdir(output, { recursive: true })
await Promise.all(files.map((file) => copyFile(resolve(dataDir, file), resolve(output, file))))
console.log(`Static news data copied to ${output}`)
await writeFile(resolve(dist, 'sitemap.xml'), sitemap, 'utf8')
console.log(`Sitemap generated with ${staticPages.length + articlePages.length} URLs`)
await mkdir(articleOutput, { recursive: true })
await Promise.all(serverArticles.map((article) => writeFile(resolve(articleOutput, `${article.slug}.html`), renderArticleHtml(shell, article), 'utf8')))
await writeFile(resolve(dist, 'seo', 'article-slugs.json'), JSON.stringify([...slugs].sort()), 'utf8')
console.log(`Server-readable HTML generated for ${serverArticles.length} articles`)
