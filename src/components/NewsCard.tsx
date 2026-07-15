import { Bookmark, ExternalLink, MapPin } from 'lucide-react'
import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import { formatDate, excerpt } from '../lib/news'
import type { NewsArticle } from '../types'
import { NewsVisual } from './NewsVisual'

export type NewsCardVariant = 'lead' | 'standard' | 'compact' | 'text' | 'search'

export function OriginBadge({ article }: { article: NewsArticle }) {
  return article.origin === 'demo'
    ? <span className="origin-badge demo">Demo · sammanfattning av källan</span>
    : <span className="origin-badge fetched">{article.hasAgentSummary ? 'Källnotis · svensk agentsammanfattning' : 'Källnotis · engelska'}</span>
}

export function NewsCard({ article, onSave, saved = false, variant = 'standard' }: { article: NewsArticle; onSave?: (article: NewsArticle) => void; saved?: boolean; variant?: NewsCardVariant }) {
  const imageLabel = article.image.kind === 'ai' ? 'AI-illustration' : `Källbild${article.image.credit ? ` av ${article.image.credit}` : ''}`
  return (
    <motion.article className={`news-card ${variant}`} initial={{ opacity: 0, y: 14 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, amount: .15 }}>
      {variant !== 'text' && <div className="news-card-art">
        <Link to={`/nyhet/${encodeURIComponent(article.id)}`} className="news-card-image-link" aria-label={`${imageLabel}. Läs ${article.title}`}>
          <NewsVisual article={article} variant={variant === 'search' ? 'search' : 'card'} />
          <span className="category-pill">{article.category}</span>
        </Link>
      </div>}
      <div className="news-card-body">
        <OriginBadge article={article} />
        {article.image.kind === 'source' && article.image.credit && article.image.rightsUrl && <div className="card-image-credit">Källbild: {article.image.credit} · <a href={article.image.rightsUrl} target="_blank" rel="noreferrer">bildrättigheter</a></div>}
        <h3 lang={article.language}><Link to={`/nyhet/${encodeURIComponent(article.id)}`}>{article.title}</Link></h3>
        <p lang={article.excerptLanguage}>{excerpt(article.excerpt)}</p>
        {article.location && <div className="news-card-location"><MapPin size={14} /> {article.location}</div>}
        <footer>
          <span><time dateTime={article.publishedAt}>{formatDate(article.publishedAt)}</time> · {article.readTime} min</span>
          <div className="card-actions">
            {onSave && <button type="button" className={saved ? 'saved' : ''} onClick={() => onSave(article)} aria-pressed={saved} aria-label={saved ? 'Ta bort från sparade' : 'Spara nyheten'}><Bookmark size={17} fill={saved ? 'currentColor' : 'none'} /></button>}
            <a href={article.url} target="_blank" rel="noreferrer" aria-label="Öppna källsidan i ny flik"><ExternalLink size={17} /></a>
          </div>
        </footer>
      </div>
    </motion.article>
  )
}
