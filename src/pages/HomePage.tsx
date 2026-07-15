import { ArrowRight, Atom, Clock3, Database, HeartPulse, Leaf, Lightbulb, Newspaper, Palette, Quote, RefreshCw, ShieldCheck, Sparkles, Trees, Users } from 'lucide-react'
import { motion } from 'framer-motion'
import { Link, useNavigate } from 'react-router-dom'
import { CategoryArt } from '../components/CategoryArt'
import { NewsCard, OriginBadge } from '../components/NewsCard'
import { NewsletterForm } from '../components/NewsletterForm'
import { useSaved } from '../contexts/SavedContext'
import { formatDate } from '../lib/news'
import { useNews } from '../lib/useNews'
import type { NewsArticle } from '../types'

export function HomePage() {
  const { data, loading, error, refresh } = useNews()
  const { isSaved, toggle } = useSaved()
  const navigate = useNavigate()
  const demos = data.articles.filter((item) => item.origin === 'demo')
  const fetched = data.articles.filter((item) => item.origin === 'fetched')
  const hero = demos.find((item) => item.featured) || demos[0]
  const demoHighlights = demos.filter((item) => item.id !== hero?.id).slice(0, 3)
  const fetchedHighlights = fetched.slice(0, 6)

  const save = async (article: NewsArticle) => {
    if (await toggle(article) === 'login') navigate(`/profil?next=${encodeURIComponent('/')}`)
  }

  if (loading) return <LoadingPage />
  if (error) return <section className="page-wrap state-page"><h1>Flödet tar en liten paus</h1><p>{error}</p><button className="button primary" type="button" onClick={() => { void refresh().catch(() => undefined) }}>Försök igen</button></section>

  return <>
    {data.warning && <div className="data-warning" role="status"><div className="page-wrap">{data.warning}</div></div>}
    <section className="hero page-wrap">
      <div className="hero-copy">
        <motion.span className="eyebrow" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>Dagens ljusglimt</motion.span>
        <motion.h1 initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }}>{hero?.title || 'Nyheter som gör världen lite större'}</motion.h1>
        <p>{hero?.excerpt || 'Vi samlar framsteg och initiativ från tydligt märkta källor.'}</p>
        {hero && <><OriginBadge article={hero} /><div className="hero-meta"><span>{hero.category}</span>{hero.location && <span>{hero.location}</span>}<time dateTime={hero.publishedAt}>{formatDate(hero.publishedAt)}</time></div>
        <div className="hero-buttons"><Link className="button primary" to={`/nyhet/${encodeURIComponent(hero.id)}`}>Läs sammanfattningen <ArrowRight size={18} /></Link><a className="button ghost" href={hero.url} target="_blank" rel="noreferrer">Öppna källsidan</a></div></>}
      </div>
      <div className="hero-art-wrap">{hero && <CategoryArt category={hero.category} className="hero-art" />}<div className="hero-caption"><span>{hero?.source}</span><small>Illustration anpassad efter ämnet</small></div></div>
    </section>

    <section className="trust-strip">
      <div className="page-wrap trust-grid">
        <div><Database /><strong>{data.fetchedCount}</strong><span>källnotiser i flödet</span></div>
        <div><Newspaper /><strong>{data.sourceCount}</strong><span>olika källor</span></div>
        <div><RefreshCw /><strong>{data.latestFetchedAt ? formatDate(data.latestFetchedAt, true) : 'Nästa körning'}</strong><span>senaste hämtning</span></div>
        <div><Clock3 /><strong>00:00 & 12:00</strong><span>dagliga körningar</span></div>
      </div>
    </section>

    <section className="section page-wrap">
      <header className="section-header"><div><span className="eyebrow">Källbelagda exempel</span><h2>Svenska demosammanfattningar</h2><p>Exempel på hur en lugn och tydligt källmärkt nyhetsupplevelse kan fungera.</p></div><Link to="/sok?typ=demo">Visa alla demos <ArrowRight size={16} /></Link></header>
      <div className="news-grid">{demoHighlights.map((article) => <NewsCard key={article.id} article={article} onSave={save} saved={isSaved(article.id)} />)}</div>
    </section>

    {fetchedHighlights.length > 0 && <section className="section fetched-news-section"><div className="page-wrap">
      <header className="section-header"><div><span className="eyebrow">Automatiskt flöde</span><h2>Senast källhämtat</h2><p>Aktuella kandidater från offentliga flöden. Rubrik och utdrag märks med språk – källsidan är alltid facit.</p></div><Link to="/sok?typ=fetched">Se alla källnotiser <ArrowRight size={16} /></Link></header>
      <div className="news-grid">{fetchedHighlights.map((article) => <NewsCard key={article.id} article={article} onSave={save} saved={isSaved(article.id)} />)}</div>
    </div></section>}

    <CategoryCompass />

    <section className="problem-solution page-wrap"><div><span className="eyebrow">Varför Ljusglimt?</span><h2>När flödet känns tungt behövs inte mindre verklighet – utan mer perspektiv.</h2></div><div><p>Många nyhetsflöden prioriterar konflikt och dramatik. Det kan göra verkliga framsteg svåra att upptäcka.</p><p className="solution"><Sparkles /> Ljusglimt samlar konstruktiva källnotiser på en lugn plats, visar deras ursprung och låter dig öppna källan direkt.</p></div></section>

    <section className="editorial-band">
      <div className="page-wrap editorial-grid">
        <div><Quote size={46} /><blockquote>”Vi samlar det som går framåt – och visar alltid var uppgifterna kommer ifrån.”</blockquote><p>Ljusglimts metodlöfte</p></div>
        <div className="editorial-points"><article><ShieldCheck /><div><h3>Tydlig märkning</h3><p>Demo och källhämtat innehåll hålls isär på varje sida.</p></div></article><article><Sparkles /><div><h3>Automatik med gränser</h3><p>Känsliga kandidater filtreras bort, men automatiken kan göra misstag. Källsidan ger hela sammanhanget.</p></div></article><Link className="button light" to="/om">Läs om metoden</Link></div>
      </div>
    </section>

    <ForumTeaser />
    <section className="journey-section"><div className="page-wrap"><header><span className="eyebrow">Tre enkla steg</span><h2>Från nyfiken till källan</h2></header><div className="journey-grid"><article><span>01</span><h3>Upptäck</h3><p>Välj ett ämne i Kategorikompassen eller sök i hela arkivet.</p></article><article><span>02</span><h3>Förstå märkningen</h3><p>Se direkt om det är en demosammanfattning eller engelsk källnotis.</p></article><article><span>03</span><h3>Öppna källsidan</h3><p>Gå vidare till ursprungspubliceringen för hela sammanhanget.</p></article></div></div></section>
    <FinalCta />
  </>
}

function CategoryCompass() {
  const items = [{ name: 'Miljö', icon: Leaf }, { name: 'Natur', icon: Trees }, { name: 'Hälsa', icon: HeartPulse }, { name: 'Vetenskap', icon: Atom }, { name: 'Människor', icon: Users }, { name: 'Kultur', icon: Palette }, { name: 'Framsteg', icon: Lightbulb }]
  return <section className="compass-section page-wrap"><header><span className="eyebrow">Kategorikompass</span><h2>Vad vill du bli hoppfull om?</h2></header><div className="compass-grid">{items.map(({ name, icon: Icon }) => <Link key={name} to={`/sok?kategori=${encodeURIComponent(name)}`}><Icon /><span>{name}</span><ArrowRight /></Link>)}</div></section>
}

function FinalCta() {
  return <section className="final-cta"><div className="page-wrap"><div><span className="eyebrow light">Nyhetsbrev · demo</span><h2>Fem ljusglimtar. När nyhetsbrevet öppnar.</h2><p>Testa formuläret. Inga mejl skickas och adressen sparas inte ännu.</p></div><NewsletterForm /></div></section>
}

function ForumTeaser() {
  return <section className="section page-wrap forum-teaser"><div><span className="eyebrow">Ljusglimt forum</span><h2>Samtal med lite mer syre</h2><p>Ett modererat rum för positiva initiativ, vardagsglädje och idéer som går att prova.</p><Link className="button primary" to="/forum">Gå till forumet <ArrowRight size={17} /></Link></div><div className="teaser-threads" aria-label="Exempel på forumämnen"><article><span>Exempel · Goda idéer</span><h3>Något gott vi kan göra tillsammans</h3><p>Beskriv problemet, idén och första steget.</p></article><article><span>Exempel · Dagens glädje</span><h3>Vad gjorde dig glad idag?</h3><p>Små saker räknas också.</p></article></div></section>
}

function LoadingPage() {
  return <section className="page-wrap loading-page" aria-busy="true"><span className="sr-only" role="status">Hämtar de senaste ljusglimtarna…</span><div className="loading-line wide" /><div className="loading-line" /><div className="loading-grid"><span /><span /><span /></div></section>
}
