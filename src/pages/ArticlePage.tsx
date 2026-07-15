import { ArrowLeft, Bookmark, ExternalLink, MapPin, Share2 } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useState } from 'react'
import { CategoryArt } from '../components/CategoryArt'
import { NewsCard, OriginBadge } from '../components/NewsCard'
import { useAuth } from '../contexts/AuthContext'
import { useSaved } from '../contexts/SavedContext'
import { formatDate } from '../lib/news'
import { useNews } from '../lib/useNews'

export function ArticlePage() {
  const { id = '' } = useParams()
  const { data, loading } = useNews()
  const { user } = useAuth()
  const { isSaved, toggle } = useSaved()
  const navigate = useNavigate()
  const [message, setMessage] = useState('')
  const article = data.articles.find((item) => item.id === decodeURIComponent(id) || item.slug === decodeURIComponent(id))
  if (loading) return <section className="page-wrap state-page"><p>Laddar nyheten…</p></section>
  if (!article) return <section className="page-wrap state-page"><h1>Nyheten hittades inte</h1><Link className="button primary" to="/">Till startsidan</Link></section>
  const related = data.articles.filter((item) => item.id !== article.id && item.category === article.category).slice(0, 3)

  const save = async () => {
    if (!user) { navigate(`/profil?next=${encodeURIComponent(location.pathname)}`); return }
    try {
      const result = await toggle(article)
      setMessage(result === 'removed' ? 'Borttagen från läslistan.' : 'Sparad i din läslista.')
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Kunde inte spara.') }
  }
  const share = async () => {
    if (navigator.share) await navigator.share({ title: article.title, url: location.href })
    else { await navigator.clipboard.writeText(location.href); setMessage('Länken är kopierad.') }
  }

  return <>
    <article className="article-page page-wrap">
      <Link className="back-link" to="/"><ArrowLeft size={17} /> Tillbaka till nyheterna</Link>
      <div className="article-layout">
        <div className="article-main">
          <OriginBadge article={article} />
          <h1 lang={article.language}>{article.title}</h1>
          <p className="article-lead" lang={article.language}>{article.excerpt}</p>
          <div className="article-meta"><span>{article.category}</span><span><MapPin size={14} /> {article.location}</span><span>{formatDate(article.publishedAt)}</span><span>{article.readTime} min läsning</span></div>
          <CategoryArt category={article.category} className="article-art" />
          <div className="article-copy">
            {article.origin === 'demo' ? <>
              <h2>Det här vet vi från källan</h2>
              <p>{article.excerpt}</p>
              <p>Texten ovan är en nyskriven svensk demosammanfattning av den länkade källan. Den är inte Ljusglimts egen rapportering. Kontrollera alltid källsidan för fullständigt sammanhang, metod och eventuella uppdateringar.</p>
            </> : <>
              <h2>Om källnotisen</h2>
              <p lang="en">{article.excerpt}</p>
              <p>Detta är en automatiskt hämtad engelsk källnotis. Ljusglimt återger inte en full artikel här. Öppna källsidan för hela publiceringen och dess sammanhang.</p>
            </>}
          </div>
        </div>
        <aside className="article-aside">
          <div className="source-card"><span className="eyebrow">Källa</span><h2>{article.source}</h2><p>{article.origin === 'demo' ? 'Demo · sammanfattning av källan' : 'Engelsk källnotis'}</p><a className="button primary" href={article.url} target="_blank" rel="noreferrer">{article.origin === 'demo' ? 'Öppna originalkällan' : 'Öppna källsidan'} <ExternalLink size={16} /></a></div>
          <div className="article-tools"><button type="button" onClick={save} aria-pressed={isSaved(article.id)} aria-label={isSaved(article.id) ? 'Ta bort från sparade' : 'Spara nyheten'}><Bookmark size={18} fill={isSaved(article.id) ? 'currentColor' : 'none'} /> {isSaved(article.id) ? 'Sparad' : 'Spara'}</button><button type="button" onClick={share}><Share2 size={18} /> Dela</button>{message && <p role="status">{message}</p>}</div>
        </aside>
      </div>
    </article>
    {related.length > 0 && <section className="section page-wrap related"><header className="section-header"><div><span className="eyebrow">Läs vidare</span><h2>Liknande ljusglimtar</h2></div></header><div className="news-grid">{related.map((item) => <NewsCard key={item.id} article={item} />)}</div></section>}
  </>
}
