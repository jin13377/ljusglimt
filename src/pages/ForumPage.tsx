import { AlertTriangle, ArrowLeft, Bell, Check, Eye, Flag, LockKeyhole, MessageCircle, Pin, Plus, Search, Send, ShieldCheck } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { api, post, remove } from '../lib/api'
import { formatDate } from '../lib/news'
import type { ForumGroup, ForumLatest, ForumSection, ForumTopic, ForumTopicSummary } from '../types'

interface IndexData { groups: ForumGroup[]; latest: ForumLatest[]; stats: { topics: number; posts: number; members: number } }
interface SectionData { section: ForumSection; topics: ForumTopicSummary[] }
interface TopicData { section: ForumSection; topic: ForumTopic }

function Avatar({ name, url, large = false }: { name: string; url?: string | null; large?: boolean }) {
  const initials = name.split(/\s+/).slice(0, 2).map((part) => part[0]).join('').toLocaleUpperCase('sv')
  return url ? <img className={`avatar ${large ? 'large' : ''}`} src={url} alt="" /> : <span className={`avatar fallback ${large ? 'large' : ''}`}>{initials}</span>
}

function ForumShell({ children }: { children: React.ReactNode }) {
  return <><section className="forum-mast"><div className="page-wrap"><span className="eyebrow">Ljusglimt forum</span><h1>Kloka samtal i vänlig ton</h1><p>Öppet att läsa. Medlemskap krävs för att skriva, följa och rapportera.</p></div></section><div className="forum-page page-wrap">{children}</div></>
}

export function ForumIndexPage() {
  const [legacy] = useSearchParams()
  const [data, setData] = useState<IndexData | null>(null)
  const [error, setError] = useState('')
  useEffect(() => { api<IndexData>('/api/forum/index').then(setData).catch((e: Error) => setError(e.message)) }, [])
  if (legacy.get('section')) return <Navigate replace to={`/forum/sektion/${encodeURIComponent(legacy.get('section')!)}`} />
  if (legacy.get('topic')) return <Navigate replace to={`/forum/trad/${encodeURIComponent(legacy.get('topic')!)}`} />
  if (error) return <ForumShell><ForumError message={error} /></ForumShell>
  if (!data) return <ForumShell><p className="loading-copy">Laddar forumet…</p></ForumShell>
  return <ForumShell>
    <div className="forum-index-layout">
      <div className="forum-groups">{data.groups.map((group) => <section className="forum-group" key={group.id}><header><div><span className="eyebrow">{group.title}</span><h2>{group.title}</h2><p>{group.description}</p></div><span>{group.sections.length} avdelningar</span></header><div>{group.sections.map((section) => <article className="forum-section-row" key={section.id}><Link className="section-main" to={`/forum/sektion/${encodeURIComponent(section.id)}`}><span className="section-icon">{section.icon}</span><span><strong>{section.title}</strong><small>{section.description}</small></span></Link><div className="section-counts"><span><strong>{section.topicCount}</strong> trådar</span><span><strong>{section.postCount}</strong> inlägg</span></div><div className="section-latest">{section.latest ? <Link to={`/forum/trad/${encodeURIComponent(section.latest.id)}`}><strong>{section.latest.title}</strong><span>{section.latest.author} · {formatDate(section.latest.createdAt, true)}</span></Link> : <span>Starta första samtalet</span>}</div></article>)}</div></section>)}</div>
      <aside className="forum-sidebar"><section><span className="eyebrow">Senaste aktivitet</span><h2>Nytt i forumet</h2><ul>{data.latest.map((item) => <li key={item.id}><Link to={`/forum/trad/${encodeURIComponent(item.id)}`}><strong>{item.title}</strong><span>{item.sectionTitle} · {item.author}</span></Link></li>)}</ul></section><section className="forum-stats"><h2>Gemenskapen</h2><div><strong>{data.stats.topics}</strong><span>trådar</span></div><div><strong>{data.stats.posts}</strong><span>inlägg</span></div><div><strong>{data.stats.members}</strong><span>medlemmar</span></div></section><ForumRules /></aside>
    </div>
  </ForumShell>
}

export function ForumSectionPage() {
  const { sectionId = '' } = useParams()
  const [data, setData] = useState<SectionData | null>(null)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const { user } = useAuth()
  const load = useCallback(() => api<SectionData>(`/api/forum/topics?section=${encodeURIComponent(sectionId)}`).then(setData).catch((e: Error) => setError(e.message)), [sectionId])
  useEffect(() => { void load() }, [load])
  const topics = useMemo(() => (data?.topics || []).filter((topic) => `${topic.title} ${topic.body} ${topic.author}`.toLocaleLowerCase('sv').includes(search.toLocaleLowerCase('sv'))), [data, search])
  if (error) return <ForumShell><ForumError message={error} /></ForumShell>
  if (!data) return <ForumShell><p className="loading-copy">Laddar avdelningen…</p></ForumShell>
  return <ForumShell>
    <div className="breadcrumbs"><Link to="/forum">Forum</Link><span>›</span><strong>{data.section.title}</strong></div>
    <header className="forum-section-head"><div className="section-title"><span className="section-icon large">{data.section.icon}</span><div><span className="eyebrow">{data.section.groupTitle}</span><h2>{data.section.title}</h2><p>{data.section.description}</p></div></div>{user ? <NewTopicForm section={data.section} onCreated={load} /> : <Link className="button primary" to={`/profil?next=${encodeURIComponent(location.pathname)}`}><Plus size={17} /> Logga in för ny tråd</Link>}</header>
    <div className="forum-toolbar"><label><span className="sr-only">Sök i avdelningen</span><Search size={17} /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Sök i avdelningen…" /></label><span>{topics.length} trådar</span></div>
    <div className="topic-list">{topics.length ? topics.map((topic) => <article className="topic-row" key={topic.id}><Link className="topic-main" to={`/forum/trad/${encodeURIComponent(topic.id)}`}><Avatar name={topic.author} url={topic.avatarUrl} /><span><strong>{topic.title}</strong><small>{topic.pinned && <em><Pin size={11} /> Fäst</em>} {topic.locked && <em><LockKeyhole size={11} /> Låst</em>} {topic.status !== 'published' && <em>Väntar på granskning</em>}</small><small>Startad av {topic.author} · {formatDate(topic.createdAt, true)}</small></span></Link><div className="topic-counts"><span><MessageCircle size={14} /> {topic.replyCount}</span><span><Eye size={14} /> {topic.views}</span></div><span className="last-active">Senast {formatDate(topic.lastActivity, true)}</span></article>) : <div className="empty-state"><MessageCircle /><h2>Här är det lugnt</h2><p>Prova en annan sökning eller starta den första tråden.</p></div>}</div>
  </ForumShell>
}

function NewTopicForm({ section, onCreated }: { section: ForumSection; onCreated: () => void }) {
  const [open, setOpen] = useState(false)
  const [status, setStatus] = useState('')
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); setStatus('Skickar…')
    const form = event.currentTarget
    const values = Object.fromEntries(new FormData(form))
    try { const result = await post<{ message: string }>('/api/forum/topics', values); setStatus(result.message); form.reset(); setTimeout(onCreated, 500) }
    catch (e) { setStatus(e instanceof Error ? e.message : 'Kunde inte skapa tråden.') }
  }
  return <div className="compose-pop"><button className="button primary" type="button" onClick={() => setOpen(!open)}><Plus size={17} /> Ny tråd</button>{open && <form className="compose-card" onSubmit={submit}><h3>Ny tråd i {section.title}</h3><input type="hidden" name="sectionId" value={section.id} /><label>Rubrik<input name="title" required minLength={5} maxLength={100} /></label><label>Inlägg<textarea name="body" required minLength={10} maxLength={2000} rows={6} /></label><button className="button primary" type="submit"><Send size={16} /> Skicka till moderering</button><p role="status">{status}</p></form>}</div>
}

export function ForumThreadPage() {
  const { topicId = '' } = useParams()
  const [data, setData] = useState<TopicData | null>(null)
  const [error, setError] = useState('')
  const [status, setStatus] = useState('')
  const { user } = useAuth()
  const navigate = useNavigate()
  const load = useCallback(() => api<TopicData>(`/api/forum/topic?id=${encodeURIComponent(topicId)}`).then(setData).catch((e: Error) => setError(e.message)), [topicId])
  useEffect(() => { void load() }, [load])
  if (error) return <ForumShell><ForumError message={error} /></ForumShell>
  if (!data) return <ForumShell><p className="loading-copy">Laddar tråden…</p></ForumShell>
  const { topic, section } = data
  const follow = async () => {
    if (!user) { navigate(`/profil?next=${encodeURIComponent(location.pathname)}`); return }
    try {
      const result = topic.followed ? await remove<{ followed: boolean }>(`/api/forum/follow/${encodeURIComponent(topic.id)}`) : await post<{ followed: boolean; message?: string }>('/api/forum/follow', { topicId: topic.id })
      setData({ ...data, topic: { ...topic, followed: result.followed } }); setStatus(result.followed ? 'Du följer tråden.' : 'Du följer inte längre tråden.')
    } catch (e) { setStatus(e instanceof Error ? e.message : 'Kunde inte ändra följning.') }
  }
  const report = async () => {
    if (!user) { navigate(`/profil?next=${encodeURIComponent(location.pathname)}`); return }
    const reason = window.prompt('Beskriv kort vad moderatorerna bör granska:')
    if (!reason) return
    try { const result = await post<{ message: string }>('/api/forum/report', { topicId: topic.id, reason }); setStatus(result.message) }
    catch (e) { setStatus(e instanceof Error ? e.message : 'Kunde inte rapportera.') }
  }
  return <ForumShell>
    <div className="breadcrumbs"><Link to="/forum">Forum</Link><span>›</span><Link to={`/forum/sektion/${section.id}`}>{section.title}</Link><span>›</span><strong>{topic.title}</strong></div>
    <header className="thread-head"><div><span className="eyebrow">{section.title}</span><h2>{topic.title}</h2><p>{topic.replies.length + 1} inlägg · {topic.views} visningar</p></div><div><button className="button ghost" type="button" onClick={follow} aria-pressed={topic.followed}><Bell size={16} /> {topic.followed ? 'Följer' : 'Följ tråden'}</button><button className="text-action" type="button" onClick={report}><Flag size={15} /> Rapportera</button></div></header>
    {status && <div className="status-banner" role="status"><Check size={17} /> {status}</div>}
    <div className="post-list"><ForumPost title={topic.title} body={topic.body} author={topic.author} createdAt={topic.createdAt} status={topic.status} opening />{topic.replies.map((reply, index) => <ForumPost key={reply.id} body={reply.body} author={reply.author} createdAt={reply.createdAt} status={reply.status} index={index + 1} />)}</div>
    {topic.locked ? <div className="locked-banner"><LockKeyhole /> Tråden är låst för nya svar.</div> : user ? <ReplyForm topicId={topic.id} onCreated={load} /> : <div className="login-prompt"><MessageCircle /><div><strong>Delta i samtalet</strong><p>Logga in för att skriva ett vänligt och konstruktivt svar.</p></div><Link className="button primary" to={`/profil?next=${encodeURIComponent(location.pathname)}`}>Logga in</Link></div>}
    <Link className="back-link" to={`/forum/sektion/${section.id}`}><ArrowLeft size={16} /> Tillbaka till {section.title}</Link>
  </ForumShell>
}

function ForumPost({ title, body, author, createdAt, status, opening, index }: { title?: string; body: string; author: { name: string; avatarUrl?: string | null; memberSince?: string | null; role?: string }; createdAt: string; status: string; opening?: boolean; index?: number }) {
  return <article className={`forum-post ${status !== 'published' ? 'pending' : ''}`}><aside><Avatar name={author.name} url={author.avatarUrl} large /><strong>{author.name}</strong><span>{author.role === 'admin' ? 'Administratör' : author.role === 'moderator' ? 'Moderator' : 'Medlem'}</span></aside><div><header><span>{opening ? 'Trådstart' : `Svar #${index}`}</span><time>{formatDate(createdAt, true)}</time></header>{status !== 'published' && <p className="pending-note">Syns bara för dig tills moderatorerna har granskat inlägget.</p>}{opening && <h2>{title}</h2>}<p>{body}</p></div></article>
}

function ReplyForm({ topicId, onCreated }: { topicId: string; onCreated: () => void }) {
  const [status, setStatus] = useState('')
  return <form className="reply-form" onSubmit={async (event) => {
    event.preventDefault(); setStatus('Skickar…'); const form = event.currentTarget
    try { const result = await post<{ message: string }>('/api/forum/replies', { topicId, body: new FormData(form).get('body') }); setStatus(result.message); form.reset(); setTimeout(onCreated, 500) }
    catch (e) { setStatus(e instanceof Error ? e.message : 'Kunde inte skicka svaret.') }
  }}><label>Skriv ett svar<textarea name="body" minLength={10} maxLength={1600} required rows={6} placeholder="Håll tonen vänlig, saklig och konkret." /></label><div><button className="button primary" type="submit"><Send size={16} /> Skicka till moderering</button><span role="status">{status}</span></div></form>
}

function ForumRules() { return <section className="forum-rules"><ShieldCheck /><h2>Så håller vi tonen</h2><ol><li>Var vänlig och saklig.</li><li>Skydda personuppgifter.</li><li>Länka källan vid faktapåståenden.</li></ol><p>Nya inlägg förhandsmodereras.</p></section> }
function ForumError({ message }: { message: string }) { return <div className="empty-state"><AlertTriangle /><h2>Forumet kunde inte laddas</h2><p>{message}</p><Link className="button primary" to="/forum">Försök från forumstarten</Link></div> }
