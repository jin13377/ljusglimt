import { ArrowRight, Atom, Clock3, Database, HeartPulse, Leaf, Lightbulb, Newspaper, Palette, PawPrint, Quote, RefreshCw, ShieldCheck, Sparkles, Trees, Users } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { NewsCard, OriginBadge } from '../components/NewsCard'
import { NewsletterForm } from '../components/NewsletterForm'
import { NewsVisual } from '../components/NewsVisual'
import { useSaved } from '../contexts/SavedContext'
import { formatDate, selectDailyHero, selectFetchedHighlights, selectWorldHighlights } from '../lib/news'
import { useNews } from '../lib/useNews'
import type { NewsArticle } from '../types'

export function HomePage() {
  const { data, loading, error, refresh } = useNews()
  const { isSaved, toggle } = useSaved()
  const navigate = useNavigate()
  const demos = data.articles.filter((item) => item.origin === 'demo')
  const fetched = data.articles.filter((item) => item.origin === 'fetched')
  const hero = selectDailyHero(data.articles)
  const demoHighlights = demos.filter((item) => item.id !== hero?.id).slice(0, 3)
  const animalStories = fetched.filter((item) => item.category === 'Djur' && item.image.kind === 'source').slice(0, 4)
  const fetchedHighlights = selectFetchedHighlights(data.articles, hero?.id)
  const worldHighlights = selectWorldHighlights(data.articles, hero?.id)

  const save = async (article: NewsArticle) => {
    if (await toggle(article) === 'login') navigate(`/profil?next=${encodeURIComponent('/')}`)
  }

  if (loading) return <LoadingPage />
  if (error) return <section className="page-wrap state-page"><h1>Flödet tar en liten paus</h1><p>{error}</p><button className="button primary" type="button" onClick={() => { void refresh().catch(() => undefined) }}>Försök igen</button></section>

  return <>
    {data.warning && <div className="data-warning" role="status"><div className="page-wrap">{data.warning}</div></div>}
    <section className="hero page-wrap">
      <div className="hero-copy">
        <span className="eyebrow">Dagens ljusglimt</span>
        <h1>{hero?.title || 'Nyheter som gör världen lite större'}</h1>
        <p>{hero?.excerpt || 'Vi samlar framsteg och initiativ från tydligt märkta källor.'}</p>
        {hero && <><OriginBadge article={hero} /><div className="hero-meta"><span>{hero.category}</span>{hero.location && <span>{hero.location}</span>}<time dateTime={hero.publishedAt}>{formatDate(hero.publishedAt)}</time></div>
        <div className="hero-buttons"><Link className="button primary" to={`/nyhet/${encodeURIComponent(hero.slug)}`}>Läs sammanfattningen <ArrowRight size={18} /></Link><a className="button ghost" href={hero.url} target="_blank" rel="noreferrer">Öppna källsidan</a></div></>}
      </div>
      <div className="hero-art-wrap">{hero && <NewsVisual article={hero} variant="hero" priority showCaption />}</div>
    </section>

    {fetchedHighlights.length > 0 && <section className="section fetched-news-section"><div className="page-wrap">
      <header className="section-header"><div><span className="eyebrow">Färskt först</span><h2>Senast källhämtat</h2><p>De senaste godkända nyheterna visas först. Rubrik och sammanfattning måste finnas på svenska, och källsidan är alltid facit.</p></div><Link to="/sok?typ=fetched">Se alla källnotiser <ArrowRight size={16} /></Link></header>
      <div className="news-grid editorial-news-grid">{fetchedHighlights.map((article, index) => <NewsCard key={article.id} article={article} variant={homeCardVariant(index)} onSave={save} saved={isSaved(article.id)} />)}</div>
    </div></section>}

    <section className="trust-strip">
      <div className="page-wrap trust-grid">
        <div><Database /><strong>{data.fetchedCount}</strong><span>källnotiser i flödet</span></div>
        <div><Newspaper /><strong>{data.sourceCount}</strong><span>olika källor</span></div>
        <div><RefreshCw /><strong>{data.latestFetchedAt ? formatDate(data.latestFetchedAt, true) : 'Nästa körning'}</strong><span>senaste hämtning</span></div>
        <div><Clock3 /><strong>00:00 & 12:00</strong><span>dagliga körningar</span></div>
      </div>
    </section>

    {animalStories.length > 0 && <section className="section animal-section" id="djur"><div className="page-wrap">
      <header className="section-header"><div><span className="eyebrow">Djur som gör en glad</span><h2>Söta möten, vänskap och nya hem</h2><p>Här visar vi bara nyheter med en riktig bild från källans eget flöde. När källan erbjuder video kan du spela den direkt på nyhetssidan.</p></div><Link to="/sok?kategori=Djur">Se alla djurnyheter <ArrowRight size={16} /></Link></header>
      <div className="animal-showcase">
        <div className="animal-feature"><NewsCard article={animalStories[0]} variant="lead" onSave={save} saved={isSaved(animalStories[0].id)} /></div>
        {animalStories.length > 1 && <div className="animal-rail">{animalStories.slice(1).map((article) => <NewsCard key={article.id} article={article} variant="compact" onSave={save} saved={isSaved(article.id)} />)}</div>}
      </div>
    </div></section>}

    {worldHighlights.length > 0 && <section className="section world-news-section"><div className="page-wrap">
      <header className="section-header"><div><span className="eyebrow">Internationellt komplement</span><h2>Ljusglimtar från världen</h2><p>Starka konstruktiva nyheter från internationella originalkällor, presenterade på svenska och alltid med länk till källan.</p></div><Link to="/sok?typ=fetched">Se alla källnotiser <ArrowRight size={16} /></Link></header>
      <div className="news-grid editorial-news-grid">{worldHighlights.map((article, index) => <NewsCard key={article.id} article={article} variant={homeCardVariant(index)} onSave={save} saved={isSaved(article.id)} />)}</div>
    </div></section>}

    <section className="section page-wrap">
      <header className="section-header"><div><span className="eyebrow">Ur arkivet</span><h2>Utvalda framsteg</h2><p>Äldre källbelagda sammanfattningar som fortfarande ger värdefullt perspektiv.</p></div><Link to="/sok?typ=sammanfattning">Visa alla utvalda framsteg <ArrowRight size={16} /></Link></header>
      <div className="news-grid editorial-news-grid">{demoHighlights.map((article, index) => <NewsCard key={article.id} article={article} variant={homeCardVariant(index)} onSave={save} saved={isSaved(article.id)} />)}</div>
    </section>

    <CategoryCompass />

    <section className="problem-solution page-wrap"><div><span className="eyebrow">Varför Ljusglimt?</span><h2>När flödet känns tungt behövs inte mindre verklighet – utan mer perspektiv.</h2></div><div><p>Många nyhetsflöden prioriterar konflikt och dramatik. Det kan göra verkliga framsteg svåra att upptäcka.</p><p className="solution"><Sparkles /> Ljusglimt samlar konstruktiva källnotiser på en lugn plats, visar deras ursprung och låter dig öppna källan direkt.</p></div></section>

    <section className="editorial-band">
      <div className="page-wrap editorial-grid">
        <div><Quote size={46} /><blockquote>”Vi samlar det som går framåt – och visar alltid var uppgifterna kommer ifrån.”</blockquote><p>Ljusglimts metodlöfte</p></div>
        <div className="editorial-points"><article><ShieldCheck /><div><h3>Tydlig märkning</h3><p>Sammanfattningar och källhämtat innehåll märks tydligt på varje sida.</p></div></article><article><Sparkles /><div><h3>Automatik med gränser</h3><p>Känsliga kandidater filtreras bort, men automatiken kan göra misstag. Källsidan ger hela sammanhanget.</p></div></article><Link className="button light" to="/om">Läs om metoden</Link></div>
      </div>
    </section>

    <ForumTeaser />
    <section className="journey-section"><div className="page-wrap"><header><span className="eyebrow">Tre enkla steg</span><h2>Från nyfiken till källan</h2></header><div className="journey-grid"><article><span>01</span><h3>Upptäck</h3><p>Välj ett ämne i Kategorikompassen eller sök i hela arkivet.</p></article><article><span>02</span><h3>Läs på svenska</h3><p>Rubriker och sammanfattningar visas på svenska, även när originalkällan använder ett annat språk.</p></article><article><span>03</span><h3>Öppna källsidan</h3><p>Gå vidare till ursprungspubliceringen för hela sammanhanget.</p></article></div></div></section>
    <FinalCta />
  </>
}

function homeCardVariant(index: number): 'lead' | 'standard' | 'compact' | 'text' {
  if (index === 0) return 'lead'
  if (index < 3) return 'standard'
  if (index < 5) return 'compact'
  return 'text'
}

function CategoryCompass() {
  const items = [{ name: 'Djur', icon: PawPrint }, { name: 'Miljö', icon: Leaf }, { name: 'Natur', icon: Trees }, { name: 'Hälsa', icon: HeartPulse }, { name: 'Vetenskap', icon: Atom }, { name: 'Människor', icon: Users }, { name: 'Kultur', icon: Palette }, { name: 'Framsteg', icon: Lightbulb }]
  return <section className="compass-section page-wrap"><header><span className="eyebrow">Kategorikompass</span><h2>Vad vill du bli hoppfull om?</h2></header><div className="compass-grid">{items.map(({ name, icon: Icon }) => <Link key={name} to={`/sok?kategori=${encodeURIComponent(name)}`}><Icon /><span>{name}</span><ArrowRight /></Link>)}</div></section>
}

function FinalCta() {
  return <section className="final-cta"><div className="page-wrap"><div><span className="eyebrow light">Nyhetsbrev · kommer snart</span><h2>Fem ljusglimtar. När nyhetsbrevet öppnar.</h2><p>Testa formuläret. Inga mejl skickas och adressen sparas inte ännu.</p></div><NewsletterForm /></div></section>
}

function ForumTeaser() {
  return <section className="section page-wrap forum-teaser"><div><span className="eyebrow">Ljusglimt forum</span><h2>Samtal med lite mer syre</h2><p>Ett modererat rum för positiva initiativ, vardagsglädje och idéer som går att prova.</p><Link className="button primary" to="/forum">Gå till forumet <ArrowRight size={17} /></Link></div><div className="teaser-threads" aria-label="Exempel på forumämnen"><article><span>Exempel · Goda idéer</span><h3>Något gott vi kan göra tillsammans</h3><p>Beskriv problemet, idén och första steget.</p></article><article><span>Exempel · Dagens glädje</span><h3>Vad gjorde dig glad idag?</h3><p>Små saker räknas också.</p></article></div></section>
}

function LoadingPage() {
  return <section className="page-wrap loading-page" aria-busy="true"><span className="sr-only" role="status">Hämtar de senaste ljusglimtarna…</span><div className="loading-line wide" /><div className="loading-line" /><div className="loading-grid"><span /><span /><span /></div></section>
}
