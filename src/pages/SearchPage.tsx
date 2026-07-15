import { Filter, Search, SlidersHorizontal, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { NewsCard } from '../components/NewsCard'
import { useSaved } from '../contexts/SavedContext'
import { useNews } from '../lib/useNews'
import type { NewsArticle } from '../types'

export function SearchPage() {
  const { data, loading, error, refresh } = useNews()
  const { isSaved, toggle } = useSaved()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const urlQuery = params.get('q') || ''
  const [queryDraft, setQueryDraft] = useState({ source: urlQuery, value: urlQuery })
  const category = params.get('kategori') || 'Alla'
  const origin = params.get('typ') || 'alla'
  const query = queryDraft.source === urlQuery ? queryDraft.value : urlQuery
  const resultSignature = `${query}\n${category}\n${origin}`
  const [page, setPage] = useState({ signature: resultSignature, visible: 18 })
  const visible = page.signature === resultSignature ? page.visible : 18
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
    setParams(next)
  }
  const save = async (article: NewsArticle) => { if (await toggle(article) === 'login') navigate(`/profil?next=${encodeURIComponent(location.pathname + location.search)}`) }

  if (error) return <section className="search-page page-wrap state-page"><h1>Arkivet kunde inte laddas</h1><p>{error}</p><button className="button primary" type="button" onClick={() => { void refresh().catch(() => undefined) }}>Försök igen</button></section>

  return <section className="search-page page-wrap">
    {data.warning && <div className="data-warning inline" role="status">{data.warning}</div>}
    <header className="search-hero"><span className="eyebrow">Nyhetsarkiv</span><h1>Hitta en ljusglimt</h1><p>Sök bland svenska demosammanfattningar och källnotiser från det automatiska flödet.</p>
      <form onSubmit={(e) => { e.preventDefault(); update('q', query) }}><Search aria-hidden="true" /><label className="sr-only" htmlFor="archive-search">Sök bland nyheter</label><input id="archive-search" value={query} onChange={(e) => setQueryDraft({ source: urlQuery, value: e.target.value })} placeholder="Sök ämne, plats eller källa…" /><button type="submit">Sök</button></form>
    </header>
    <div className="filter-bar"><div><Filter size={17} /><strong>Filtrera</strong></div><div className="filter-scroll" aria-label="Filtrera på kategori">{categories.map((item) => <button type="button" key={item} className={category === item ? 'active' : ''} aria-pressed={category === item} onClick={() => update('kategori', item)}>{item}</button>)}</div><label><SlidersHorizontal size={16} aria-hidden="true" /><span className="sr-only">Filtrera på innehållstyp</span><select value={origin} onChange={(e) => update('typ', e.target.value)}><option value="alla">Allt innehåll</option><option value="demo">Demosammanfattningar</option><option value="fetched">Källnotiser</option></select></label></div>
    <div className="results-heading"><h2 role="status" aria-live="polite">{loading ? 'Laddar…' : `${results.length} träffar`}</h2>{(query || category !== 'Alla' || origin !== 'alla') && <button type="button" onClick={() => { setQueryDraft({ source: '', value: '' }); setParams({}) }}><X size={15} /> Rensa</button>}</div>
    {!loading && results.length === 0 ? <div className="empty-state"><Search /><h2>Inga träffar ännu</h2><p>Prova ett bredare ord eller rensa ett filter.</p></div> : <><div className="search-results-list">{results.slice(0, visible).map((article) => <NewsCard key={article.id} article={article} variant="search" onSave={save} saved={isSaved(article.id)} />)}</div>{visible < results.length && <div className="load-more"><button className="button ghost" type="button" onClick={() => setPage({ signature: resultSignature, visible: visible + 18 })}>Visa fler ({results.length - visible} kvar)</button></div>}</>}
  </section>
}
