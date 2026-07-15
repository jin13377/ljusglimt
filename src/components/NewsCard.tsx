import { Bookmark, ExternalLink, MapPin } from 'lucide-react'
import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import { formatDate, excerpt } from '../lib/news'
import type { NewsArticle } from '../types'
import { CategoryArt } from './CategoryArt'

export function OriginBadge({ article }: { article: NewsArticle }) {
  return article.origin === 'demo'
    ? <span className="origin-badge demo">Demo · sammanfattning av källan</span>
    : <span className="origin-badge fetched">{article.hasAgentSummary ? 'Källnotis · svensk agentsammanfattning' : 'Källnotis · engelska'}</span>
}

export function NewsCard({ article, onSave, saved = false }: { article: NewsArticle; onSave?: (article: NewsArticle) => void; saved?: boolean }) {
  return (
    <motion.article className="news-card" initial={{ opacity: 0, y: 14 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, amount: .15 }}>
      <Link to={`/nyhet/${encodeURIComponent(article.id)}`} className="news-card-art" aria-label={`Läs ${article.title}`}>
        <CategoryArt category={article.category} />
        <span className="category-pill">{article.category}</span>
      </Link>
      <div className="news-card-body">
        <OriginBadge article={article} />
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
