import { ArrowLeft, Bookmark, ExternalLink, MapPin, Share2 } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useState } from 'react'
import { NewsCard, OriginBadge } from '../components/NewsCard'
import { NewsVisual } from '../components/NewsVisual'
import { SourceVideoPlayer } from '../components/SourceVideoPlayer'
import { useAuth } from '../contexts/AuthContext'
import { useSaved } from '../contexts/SavedContext'
import { formatDate } from '../lib/news'
import { useNews } from '../lib/useNews'
import { SITE_NAME, SITE_URL, usePageMetadata } from '../lib/seo'

export function ArticlePage() {
  const { id = '' } = useParams()
  const { data, loading, error, refresh } = useNews()
  const { user } = useAuth()
  const { isSaved, toggle } = useSaved()
  const navigate = useNavigate()
  const [message, setMessage] = useState('')
  const [saving, setSaving] = useState(false)
  const article = data.articles.find((item) => item.id === decodeURIComponent(id) || item.slug === decodeURIComponent(id))
  const articlePath = article ? `/nyhet/${encodeURIComponent(article.slug)}` : `/nyhet/${encodeURIComponent(id)}`
  const articleJsonLd = article ? {
    '@context': 'https://schema.org',
    '@type': 'NewsArticle',
    headline: article.title,
    description: article.excerpt,
    image: [article.image.url.startsWith('http') ? article.image.url : `${SITE_URL}${article.image.url}`],
    datePublished: article.publishedAt,
    dateModified: article.publishedAt,
    inLanguage: 'sv-SE',
    isAccessibleForFree: true,
    mainEntityOfPage: `${SITE_URL}${articlePath}`,
    author: { '@type': 'Organization', name: article.source, url: article.url },
    publisher: { '@type': 'Organization', name: SITE_NAME, url: SITE_URL, logo: { '@type': 'ImageObject', url: `${SITE_URL}/sun.svg` } },
    citation: article.url,
    articleSection: article.category,
  } : undefined
  usePageMetadata({
    title: article?.title || 'Nyhet',
    description: article?.excerpt || 'En positiv nyhet från Ljusglimt.',
    canonicalPath: articlePath,
    image: article?.image.url,
    imageAlt: article?.image.alt,
    type: 'article',
    noIndex: !loading && !article,
    jsonLd: articleJsonLd,
  })
  if (loading) return <section className="page-wrap state-page"><p>Laddar nyheten…</p></section>
  if (error) return <section className="page-wrap state-page"><h1>Nyheten kunde inte laddas</h1><p>{error}</p><button className="button primary" type="button" onClick={() => { void refresh().catch(() => undefined) }}>Försök igen</button></section>
  if (!article && !data.fetchedAvailable) return <section className="page-wrap state-page"><h1>Källnotisen kunde inte hämtas</h1><p>Det automatiska flödet är tillfälligt otillgängligt.</p><button className="button primary" type="button" onClick={() => { void refresh().catch(() => undefined) }}>Försök igen</button></section>
  if (!article) return <section className="page-wrap state-page"><h1>Nyheten hittades inte</h1><Link className="button primary" to="/">Till startsidan</Link></section>
  const related = data.articles.filter((item) => item.id !== article.id && item.category === article.category).slice(0, 3)

  const save = async () => {
    if (!user) { navigate(`/profil?next=${encodeURIComponent(location.pathname)}`); return }
    setSaving(true)
    try {
      const result = await toggle(article)
      setMessage(result === 'removed' ? 'Borttagen från läslistan.' : 'Sparad i din läslista.')
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Kunde inte spara.') }
    finally { setSaving(false) }
  }
  const share = async () => {
    try {
      if (navigator.share) await navigator.share({ title: article.title, url: location.href })
      else { await navigator.clipboard.writeText(location.href); setMessage('Länken är kopierad.') }
    } catch (reason) {
      if (reason instanceof DOMException && reason.name === 'AbortError') return
      setMessage('Länken kunde inte delas. Kopiera adressen från webbläsaren i stället.')
    }
  }

  return <>
    <article className="article-page page-wrap">
      <Link className="back-link" to="/"><ArrowLeft size={17} /> Tillbaka till nyheterna</Link>
      <div className="article-layout">
        <div className="article-main">
          <OriginBadge article={article} />
          <h1 lang={article.language}>{article.title}</h1>
          <p className="article-lead" lang={article.excerptLanguage}>{article.excerpt}</p>
          <div className="article-meta"><span>{article.category}</span>{article.location && <span><MapPin size={14} /> {article.location}</span>}<time dateTime={article.publishedAt}>{formatDate(article.publishedAt)}</time><span>{article.readTime} min läsning</span></div>
          <NewsVisual article={article} variant="article" priority showCaption />
          {article.video && <SourceVideoPlayer video={article.video} poster={article.image} />}
          <div className="article-copy">
            {article.origin === 'demo' ? <>
              <h2>Om sammanfattningen</h2>
              <p>Ingressen ovan sammanfattar den länkade källan på svenska. Öppna källsidan för hela sammanhanget och eventuella uppdateringar.</p>
            </> : <>
              <h2>Om källnotisen</h2>
              <p>Rubriken och ingressen är en svensk, källbunden återgivning av den angivna publiceringen. Öppna källsidan för hela publiceringen och dess sammanhang.</p>
            </>}
          </div>
        </div>
        <aside className="article-aside">
          <div className="source-card"><span className="eyebrow">Källa</span><h2>{article.source}</h2><p>{article.origin === 'demo' ? 'Sammanfattning av källan' : 'Svensk källsammanfattning'}</p><a className="button primary" href={article.url} target="_blank" rel="noreferrer">{article.origin === 'demo' ? 'Öppna originalkällan' : 'Öppna källsidan'} <ExternalLink size={16} /></a></div>
          <div className="article-tools"><button type="button" disabled={saving} onClick={save} aria-pressed={isSaved(article.id)} aria-label={isSaved(article.id) ? 'Ta bort från sparade' : 'Spara nyheten'}><Bookmark size={18} fill={isSaved(article.id) ? 'currentColor' : 'none'} /> {saving ? 'Sparar…' : isSaved(article.id) ? 'Sparad' : 'Spara'}</button><button type="button" onClick={share}><Share2 size={18} /> Dela</button>{message && <p role="status">{message}</p>}</div>
        </aside>
      </div>
    </article>
    {related.length > 0 && <section className="section page-wrap related"><header className="section-header"><div><span className="eyebrow">Läs vidare</span><h2>Liknande ljusglimtar</h2></div></header><div className="news-grid">{related.map((item) => <NewsCard key={item.id} article={item} />)}</div></section>}
  </>
}
