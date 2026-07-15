import { ArrowRight, Clock3, Database, HeartPulse, Leaf, Newspaper, Palette, Quote, RefreshCw, ShieldCheck, Sparkles, Users } from 'lucide-react'
import { motion } from 'framer-motion'
import { Link, useNavigate } from 'react-router-dom'
import { CategoryArt } from '../components/CategoryArt'
import { NewsCard, OriginBadge } from '../components/NewsCard'
import { useSaved } from '../contexts/SavedContext'
import { formatDate } from '../lib/news'
import { useNews } from '../lib/useNews'
import type { NewsArticle } from '../types'

const risky = /blood|bloody|harass|abuse|stroke|onlyfans|killed|death|murder|violence|assault/i

export function HomePage() {
  const { data, loading, error } = useNews()
  const { isSaved, toggle } = useSaved()
  const navigate = useNavigate()
  const demos = data.articles.filter((item) => item.origin === 'demo')
  const hero = demos.find((item) => item.featured) || demos[0]
  const prominent = [...demos.filter((item) => item.id !== hero?.id), ...data.articles.filter((item) => item.origin === 'fetched' && !risky.test(item.title))].slice(0, 6)

  const save = async (article: NewsArticle) => {
    if (await toggle(article) === 'login') navigate(`/profil?next=${encodeURIComponent('/')}`)
  }

  if (loading) return <LoadingPage />
  if (error) return <section className="page-wrap state-page"><h1>Flödet tar en liten paus</h1><p>{error}</p><button onClick={() => location.reload()}>Försök igen</button></section>

  return <>
    <section className="hero page-wrap">
      <div className="hero-copy">
        <motion.span className="eyebrow" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>Dagens ljusglimt</motion.span>
        <motion.h1 initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }}>{hero?.title || 'Nyheter som gör världen lite större'}</motion.h1>
        <p>{hero?.excerpt || 'Vi samlar framsteg och initiativ från tydligt märkta källor.'}</p>
        {hero && <><OriginBadge article={hero} /><div className="hero-meta"><span>{hero.category}</span><span>{hero.location}</span><span>{formatDate(hero.publishedAt)}</span></div>
        <div className="hero-buttons"><Link className="button primary" to={`/nyhet/${encodeURIComponent(hero.id)}`}>Läs sammanfattningen <ArrowRight size={18} /></Link><a className="button ghost" href={hero.url} target="_blank" rel="noreferrer">Öppna källsidan</a></div></>}
      </div>
      <div className="hero-art-wrap">{hero && <CategoryArt category={hero.category} className="hero-art" />}<div className="hero-caption"><span>{hero?.source}</span><small>Illustration anpassad efter ämnet</small></div></div>
    </section>

    <section className="trust-strip">
      <div className="page-wrap trust-grid">
        <div><Database /><strong>{data.fetchedCount}</strong><span>källnotiser i flödet</span></div>
        <div><Newspaper /><strong>{data.sourceCount}</strong><span>olika källor</span></div>
        <div><RefreshCw /><strong>{data.latestFetchedAt ? formatDate(data.latestFetchedAt) : 'Nästa natt'}</strong><span>senaste hämtning</span></div>
        <div><Clock3 /><strong>02:00</strong><span>schemalagd nattkörning</span></div>
      </div>
    </section>

    <section className="section page-wrap">
      <header className="section-header"><div><span className="eyebrow">Utvalt för dig</span><h2>Fler ljusglimtar</h2><p>Svenska demosammanfattningar först, därefter varsamt valda källnotiser.</p></div><Link to="/sok">Se hela arkivet <ArrowRight size={16} /></Link></header>
      <div className="news-grid">{prominent.map((article) => <NewsCard key={article.id} article={article} onSave={save} saved={isSaved(article.id)} />)}</div>
    </section>

    <CategoryCompass />

    <section className="problem-solution page-wrap"><div><span className="eyebrow">Varför Ljusglimt?</span><h2>När flödet känns tungt behövs inte mindre verklighet – utan mer perspektiv.</h2></div><div><p>Många nyhetsflöden prioriterar konflikt och dramatik. Det kan göra verkliga framsteg svåra att upptäcka.</p><p className="solution"><Sparkles /> Ljusglimt samlar konstruktiva källnotiser på en lugn plats, visar deras ursprung och låter dig öppna källan direkt.</p></div></section>

    <section className="editorial-band">
      <div className="page-wrap editorial-grid">
        <div><Quote size={46} /><blockquote>”Vi samlar det som går framåt – och visar alltid var uppgifterna kommer ifrån.”</blockquote><p>Ljusglimts metodlöfte</p></div>
        <div className="editorial-points"><article><ShieldCheck /><div><h3>Tydlig märkning</h3><p>Demo och källhämtat innehåll hålls isär på varje sida.</p></div></article><article><Sparkles /><div><h3>Lugn presentation</h3><p>Inga chockrubriker, inga generiska fotografier och inga oklara påståenden.</p></div></article><Link className="button light" to="/om">Läs om metoden</Link></div>
      </div>
    </section>

    <ForumTeaser />
    <section className="journey-section"><div className="page-wrap"><header><span className="eyebrow">Tre enkla steg</span><h2>Från nyfiken till källan</h2></header><div className="journey-grid"><article><span>01</span><h3>Upptäck</h3><p>Välj ett ämne i Kategorikompassen eller sök i hela arkivet.</p></article><article><span>02</span><h3>Förstå märkningen</h3><p>Se direkt om det är en demosammanfattning eller engelsk källnotis.</p></article><article><span>03</span><h3>Öppna källsidan</h3><p>Gå vidare till ursprungspubliceringen för hela sammanhanget.</p></article></div></div></section>
    <FinalCta />
  </>
}

function CategoryCompass() {
  const items = [{ name: 'Miljö', icon: Leaf }, { name: 'Hälsa', icon: HeartPulse }, { name: 'Människor', icon: Users }, { name: 'Kultur', icon: Palette }]
  return <section className="compass-section page-wrap"><header><span className="eyebrow">Kategorikompass</span><h2>Vad vill du bli hoppfull om?</h2></header><div className="compass-grid">{items.map(({ name, icon: Icon }) => <Link key={name} to={`/sok?kategori=${encodeURIComponent(name)}`}><Icon /><span>{name}</span><ArrowRight /></Link>)}</div></section>
}

function FinalCta() {
  return <section className="final-cta"><div className="page-wrap"><div><span className="eyebrow light">En lugnare start</span><h2>Fem ljusglimtar. När nyhetsbrevet öppnar.</h2><p>Formuläret är förberett men utskicket är inte aktiverat ännu.</p></div><form onSubmit={async (event) => { event.preventDefault(); const form = event.currentTarget; const email = new FormData(form).get('email'); await fetch('/api/newsletter', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email }) }); form.reset(); alert('Tack! Formuläret fungerar. Nyhetsbrevet är inte aktiverat ännu.') }}><input type="email" name="email" required placeholder="din@epost.se" aria-label="E-postadress" /><button type="submit">Anmäl intresse <ArrowRight size={17} /></button></form></div></section>
}

function ForumTeaser() {
  return <section className="section page-wrap forum-teaser"><div><span className="eyebrow">Ljusglimt forum</span><h2>Samtal med lite mer syre</h2><p>Ett modererat rum för positiva initiativ, vardagsglädje och idéer som går att prova.</p><Link className="button primary" to="/forum">Gå till forumet <ArrowRight size={17} /></Link></div><div className="teaser-threads"><article><span>Goda idéer</span><h3>Något gott vi kan göra tillsammans</h3><p>Beskriv problemet, idén och första steget.</p></article><article><span>Dagens glädje</span><h3>Vad gjorde dig glad idag?</h3><p>Små saker räknas också.</p></article></div></section>
}

function LoadingPage() {
  return <section className="page-wrap loading-page" aria-busy="true"><div className="loading-line wide" /><div className="loading-line" /><div className="loading-grid"><span /><span /><span /></div></section>
}
