import { copyFile, mkdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const output = resolve(root, 'dist', 'data')
const files = ['news.json', 'seed-news.json']

await mkdir(output, { recursive: true })
await Promise.all(files.map((file) => copyFile(resolve(root, 'data', file), resolve(output, file))))

console.log(`Static news data copied to ${output}`)

const siteUrl = 'https://ljusglimt.daniel-eklund1981.workers.dev'
const escapeXml = (value) => String(value).replace(/[<>&"']/g, (character) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;', "'": '&apos;' })[character])
const slugify = (value) => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('sv').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 90)
const [news, seed] = await Promise.all([
  readFile(resolve(root, 'data', 'news.json'), 'utf8').then(JSON.parse),
  readFile(resolve(root, 'data', 'seed-news.json'), 'utf8').then(JSON.parse),
])

const staticPages = [
  { path: '/', priority: '1.0', frequency: 'daily' },
  { path: '/sok', priority: '0.8', frequency: 'daily' },
  { path: '/forum', priority: '0.7', frequency: 'daily' },
  { path: '/om', priority: '0.5', frequency: 'monthly' },
]
const seedArticles = (seed.articles || []).map((article) => ({
  path: `/nyhet/${encodeURIComponent(article.slug || slugify(article.title))}`,
  updated: article.publishedAt,
  image: article.source_image_url,
  imageTitle: article.title,
}))
const fetchedArticles = (news.items || [])
  .filter((article) => article.public_eligible && article.display_title_sv && article.agent_summary)
  .map((article) => ({
    path: `/nyhet/${encodeURIComponent(`${slugify(article.title)}-${article.id.slice(0, 6)}`)}`,
    updated: article.published_at,
    image: article.source_image_verified ? article.source_image_url : article.generated_image?.url || article.ai_image?.url,
    imageTitle: article.display_title_sv,
  }))

const urlEntry = ({ path, updated, priority, frequency, image, imageTitle }) => {
  const lastmod = updated && !Number.isNaN(Date.parse(updated)) ? `<lastmod>${new Date(updated).toISOString()}</lastmod>` : ''
  const changefreq = frequency ? `<changefreq>${frequency}</changefreq>` : ''
  const priorityTag = priority ? `<priority>${priority}</priority>` : ''
  const imageTag = image ? `<image:image><image:loc>${escapeXml(new URL(image, siteUrl).toString())}</image:loc><image:title>${escapeXml(imageTitle)}</image:title></image:image>` : ''
  return `<url><loc>${escapeXml(`${siteUrl}${path}`)}</loc>${lastmod}${changefreq}${priorityTag}${imageTag}</url>`
}
const sitemap = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n${[...staticPages, ...seedArticles, ...fetchedArticles].map(urlEntry).join('\n')}\n</urlset>\n`
await writeFile(resolve(root, 'dist', 'sitemap.xml'), sitemap, 'utf8')
console.log(`Sitemap generated with ${staticPages.length + seedArticles.length + fetchedArticles.length} URLs`)
