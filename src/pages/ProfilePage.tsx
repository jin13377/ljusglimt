import { Bookmark, CheckCircle2, LogOut, Settings, Shield, UserRound } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { AiImageBadge } from '../components/AiImageBadge'
import { useAuth } from '../contexts/AuthContext'
import { useSaved } from '../contexts/SavedContext'
import { api, post } from '../lib/api'
import { profileIcons } from '../lib/profileIcons'
import type { SavedArticle } from '../types'

declare global {
  interface Window {
    google?: { accounts: { id: { initialize: (config: { client_id: string; callback: (response: { credential: string }) => void }) => void; renderButton: (element: HTMLElement, options: Record<string, unknown>) => void } } }
  }
}

export function ProfilePage() {
  const { user, loading, login, register, logout, refresh } = useAuth()
  const { saved, error: savedError, removeSaved } = useSaved()
  const [tab, setTab] = useState<'login' | 'register'>('login')
  const [status, setStatus] = useState('')
  const [googleEnabled, setGoogleEnabled] = useState(false)
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const requestedNext = params.get('next')
  const nextPath = requestedNext?.startsWith('/') && !requestedNext.startsWith('//') ? requestedNext : '/'
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); setStatus('Arbetar…'); const values = Object.fromEntries(new FormData(event.currentTarget))
    try {
      if (tab === 'login') await login(String(values.email), String(values.password))
      else await register(String(values.name), String(values.email), String(values.password))
      navigate(nextPath)
    } catch (e) { setStatus(e instanceof Error ? e.message : 'Inloggningen misslyckades.') }
  }

  useEffect(() => {
    if (user) return
    let active = true
    api<{ googleClientId: string; googleEnabled: boolean }>('/api/config').then((config) => {
      if (active) setGoogleEnabled(config.googleEnabled)
      if (!active || !config.googleEnabled) return
      const render = () => {
        const target = document.querySelector<HTMLElement>('#google-signin')
        if (!target || !window.google) return
        window.google.accounts.id.initialize({ client_id: config.googleClientId, callback: async ({ credential }) => {
          try { await post('/api/auth/google', { credential }); await refresh(); navigate(nextPath) }
          catch (e) { setStatus(e instanceof Error ? e.message : 'Google-inloggningen misslyckades.') }
        } })
        window.google.accounts.id.renderButton(target, { theme: 'outline', size: 'large', shape: 'pill', text: 'continue_with', locale: 'sv', width: 320 })
      }
      const existing = document.querySelector<HTMLScriptElement>('script[data-google-identity]')
      if (existing) { render(); return }
      const script = document.createElement('script'); script.src = 'https://accounts.google.com/gsi/client'; script.async = true; script.dataset.googleIdentity = 'true'; script.onload = render; document.head.appendChild(script)
    }).catch(() => undefined)
    return () => { active = false }
  }, [navigate, nextPath, refresh, user])

  if (loading) return <section className="page-wrap state-page"><p>Laddar profilen…</p></section>
  if (!user) return <section className="auth-page page-wrap"><div className="auth-copy"><span className="eyebrow">Medlemskap</span><h1>Spara, följ och delta</h1><p>Ett konto gör att du kan bygga en egen läslista och delta i forumet.</p><ul><li><Bookmark /> Spara nyheter till senare</li><li><Shield /> Skriv och följ samtal i forumet</li><li><UserRound /> Hantera din profil på ett ställe</li></ul></div><div className="auth-card"><div className="auth-tabs" role="tablist" aria-label="Välj kontoåtgärd"><button type="button" role="tab" aria-selected={tab === 'login'} className={tab === 'login' ? 'active' : ''} onClick={() => { setTab('login'); setStatus('') }}>Logga in</button><button type="button" role="tab" aria-selected={tab === 'register'} className={tab === 'register' ? 'active' : ''} onClick={() => { setTab('register'); setStatus('') }}>Skapa konto</button></div><form onSubmit={submit}>{tab === 'register' && <label>Namn<input name="name" minLength={2} maxLength={50} required autoComplete="name" /></label>}<label>E-post<input name="email" type="email" required autoComplete="email" /></label><label>Lösenord<input name="password" type="password" minLength={8} maxLength={256} required autoComplete={tab === 'login' ? 'current-password' : 'new-password'} /></label><button className="button primary" type="submit">{tab === 'login' ? 'Logga in' : 'Skapa konto'}</button><p role="status" aria-live="polite" className="form-status">{status}</p></form>{googleEnabled && <div className="auth-divider"><span>eller</span></div>}<div id="google-signin" className="google-signin" />{googleEnabled && <p className="google-note">Google-inloggningen använder ditt verifierade Google-konto.</p>}</div></section>

  return <section className="profile-page page-wrap"><header><div className="profile-avatar">{user.avatarUrl ? <img src={user.avatarUrl} alt="" /> : user.name.slice(0, 1).toLocaleUpperCase('sv')}</div><div><span className="eyebrow">Din profil</span><h1>Hej {user.name}</h1><p>{user.email}</p></div><button type="button" className="button ghost" onClick={async () => { try { await logout(); navigate('/') } catch (reason) { setStatus(reason instanceof Error ? reason.message : 'Kunde inte logga ut.') } }}><LogOut size={17} /> Logga ut</button></header>{status && <p className="form-status" role="status">{status}</p>}<div className="profile-layout"><aside><a href="#sparade"><Bookmark /> Sparade nyheter</a><a href="#installningar"><Settings /> Inställningar</a><Link to="/forum"><UserRound /> Forumet</Link></aside><div><section id="sparade" className="profile-panel"><header><div><span className="eyebrow">Läslista</span><h2>Sparade nyheter</h2></div><span>{saved.length} sparade</span></header>{savedError && <p className="form-error" role="alert">{savedError}</p>}{saved.length ? <div className="saved-list">{saved.map((item) => <SavedRow key={item.article_id} item={item} onRemove={removeSaved} />)}</div> : !savedError && <div className="empty-state"><Bookmark /><h3>Läslistan är tom</h3><p>Spara en nyhet så hamnar den här.</p><Link className="button primary" to="/">Hitta nyheter</Link></div>}</section><ProfileSettings name={user.name} avatarUrl={user.avatarUrl} onUpdated={refresh} /></div></div></section>
}

function SavedRow({ item, onRemove }: { item: SavedArticle; onRemove: (id: string) => Promise<void> }) {
  const [status, setStatus] = useState('')
  const [removing, setRemoving] = useState(false)
  return <article>{item.image && <div className="saved-thumb-wrap"><img className="saved-thumb" src={item.image} width="160" height="107" loading="lazy" decoding="async" alt="" /><AiImageBadge /></div>}<div><span>{item.source}</span><h3>{item.title}</h3><p>{item.summary}</p></div><div><a href={item.url} target="_blank" rel="noreferrer">Öppna källan</a><button type="button" disabled={removing} onClick={async () => { setRemoving(true); setStatus(''); try { await onRemove(item.article_id) } catch (reason) { setStatus(reason instanceof Error ? reason.message : 'Kunde inte ta bort nyheten.'); setRemoving(false) } }}>{removing ? 'Tar bort…' : 'Ta bort'}</button>{status && <span className="form-error" role="status">{status}</span>}</div></article>
}

function ProfileSettings({ name, avatarUrl, onUpdated }: { name: string; avatarUrl?: string | null; onUpdated: () => Promise<void> }) {
  const [status, setStatus] = useState('')
  return <section id="installningar" className="profile-panel settings-panel"><span className="eyebrow">Inställningar</span><h2>Profil och ikon</h2><form onSubmit={async (event) => { event.preventDefault(); setStatus('Sparar…'); try { await post('/api/profile', Object.fromEntries(new FormData(event.currentTarget))); await onUpdated(); setStatus('Profilen är sparad.') } catch (e) { setStatus(e instanceof Error ? e.message : 'Kunde inte spara.') } }}><label>Namn<input name="name" defaultValue={name} minLength={2} maxLength={50} required /></label><fieldset className="avatar-picker"><legend>Välj en profilikon</legend><p>Ikonen syns på din profil och bredvid dina inlägg i forumet.</p><div>{profileIcons.map((icon) => <label key={icon.id} className="avatar-choice"><input type="radio" name="avatarUrl" value={icon.url} defaultChecked={avatarUrl === icon.url} /><span><img src={icon.url} alt="" /><strong>{icon.label}</strong></span></label>)}</div></fieldset><button className="button primary" type="submit"><CheckCircle2 size={17} /> Spara profil</button><span role="status">{status}</span></form></section>
}
