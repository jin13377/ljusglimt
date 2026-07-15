import { Filter, Search, SlidersHorizontal, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { NewsCard } from '../components/NewsCard'
import { useSaved } from '../contexts/SavedContext'
import { useNews } from '../lib/useNews'
import { useNavigate } from 'react-router-dom'
import type { NewsArticle } from '../types'

export function SearchPage() {
  const { data, loading } = useNews()
  const { isSaved, toggle } = useSaved()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const [query, setQuery] = useState(params.get('q') || '')
  const category = params.get('kategori') || 'Alla'
  const origin = params.get('typ') || 'alla'
  const categories = ['Alla', ...new Set(data.articles.map((item) => item.category))]
  const results = useMemo(() => data.articles.filter((item) => {
    const text = `${item.title} ${item.excerpt} ${item.source} ${item.location}`.toLocaleLowerCase('sv')
    return (!query.trim() || text.includes(query.trim().toLocaleLowerCase('sv')))
      && (category === 'Alla' || item.category === category)
      && (origin === 'alla' || item.origin === origin)
  }), [category, data.articles, origin, query])

  const update = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value === 'Alla' || value === 'alla' || !value) next.delete(key)
    else next.set(key, value)
    setParams(next, { replace: true })
  }
  const save = async (article: NewsArticle) => { if (await toggle(article) === 'login') navigate(`/profil?next=${encodeURIComponent(location.pathname + location.search)}`) }

  return <section className="search-page page-wrap">
    <header className="search-hero"><span className="eyebrow">Nyhetsarkiv</span><h1>Hitta en ljusglimt</h1><p>Sök bland svenska demosammanfattningar och källnotiser från det nattliga flödet.</p>
      <form onSubmit={(e) => { e.preventDefault(); update('q', query) }}><Search /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Sök ämne, plats eller källa…" autoFocus /><button type="submit">Sök</button></form>
    </header>
    <div className="filter-bar"><div><Filter size={17} /><strong>Filtrera</strong></div><div className="filter-scroll">{categories.map((item) => <button key={item} className={category === item ? 'active' : ''} onClick={() => update('kategori', item)}>{item}</button>)}</div><label><SlidersHorizontal size={16} /><select value={origin} onChange={(e) => update('typ', e.target.value)}><option value="alla">Allt innehåll</option><option value="demo">Demosammanfattningar</option><option value="fetched">Engelska källnotiser</option></select></label></div>
    <div className="results-heading"><h2>{loading ? 'Laddar…' : `${results.length} träffar`}</h2>{(query || category !== 'Alla' || origin !== 'alla') && <button onClick={() => { setQuery(''); setParams({}) }}><X size={15} /> Rensa</button>}</div>
    {!loading && results.length === 0 ? <div className="empty-state"><Search /><h2>Inga träffar ännu</h2><p>Prova ett bredare ord eller rensa ett filter.</p></div> : <div className="news-grid">{results.map((article) => <NewsCard key={article.id} article={article} onSave={save} saved={isSaved(article.id)} />)}</div>}
  </section>
}
