import { AnimatePresence, motion } from 'framer-motion'
import { Globe2, Menu, Search, UserRound, X } from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { NewsletterForm } from './NewsletterForm'

const nav = [
  ['Nyheter', '/'],
  ['Djur', '/sok?kategori=Djur'],
  ['Sök', '/sok'],
  ['Forum', '/forum'],
  ['Om Ljusglimt', '/om'],
]

function GlobeMenu() {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const close = (event: MouseEvent) => { if (!ref.current?.contains(event.target as Node)) setOpen(false) }
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', escape)
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', escape) }
  }, [])
  return (
    <div className="globe-menu" ref={ref}>
      <button type="button" className="icon-label-button" onClick={() => setOpen(!open)} aria-expanded={open} aria-label="Välj språk och region"><Globe2 size={19} /><span>Sverige · SV</span></button>
      <AnimatePresence>{open && <motion.div className="globe-popover" initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}>
        <span className="popover-kicker">Språk och region</span>
        <strong>Sverige</strong><p>Svenska · SEK</p>
        <div className="popover-rule" />
        <button type="button" onClick={() => setOpen(false)}>Svenska <span>Valt</span></button>
        <small>Fler språk kommer senare. Allt innehåll på Ljusglimt visas på svenska.</small>
      </motion.div>}</AnimatePresence>
    </div>
  )
}

export function Layout({ children }: { children: ReactNode }) {
  const [menuPath, setMenuPath] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const { user } = useAuth()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const menuOpen = menuPath === pathname
  useEffect(() => {
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') setMenuPath(null) }
    document.addEventListener('keydown', escape)
    return () => document.removeEventListener('keydown', escape)
  }, [])
  return (
    <div className="app-shell">
      <a href="#main" className="skip-link">Hoppa till innehållet</a>
      <div className="top-note">Positiva nyheter från tydliga källor · Uppdateras 00:00 och 12:00</div>
      <header className="site-header">
        <div className="header-container">
          <Link to="/" className="brand" aria-label="Ljusglimt startsida"><span className="brand-sun">☀</span><span>Ljusglimt<small>NYHETER SOM GER PERSPEKTIV</small></span></Link>
          <nav className="desktop-nav" aria-label="Huvudmeny">{nav.map(([label, href]) => label === 'Djur' ? <Link key={href} to={href}>{label}</Link> : <NavLink key={href} to={href} end={href === '/'}>{label}</NavLink>)}</nav>
          <div className="header-actions">
            <GlobeMenu />
            <form className="header-search" onSubmit={(e) => { e.preventDefault(); navigate(`/sok?q=${encodeURIComponent(search)}`) }}><Search size={17} /><input aria-label="Sök" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Sök" /></form>
            <Link className="profile-button" to="/profil"><UserRound size={18} /><span>{user?.name || 'Logga in'}</span></Link>
            <button type="button" className="mobile-menu-button" onClick={() => setMenuPath(menuOpen ? null : pathname)} aria-expanded={menuOpen} aria-label={menuOpen ? 'Stäng meny' : 'Öppna meny'}>{menuOpen ? <X /> : <Menu />}</button>
          </div>
        </div>
        <AnimatePresence>{menuOpen && <motion.nav className="mobile-nav" aria-label="Mobilmeny" initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }}>{nav.map(([label, href]) => label === 'Djur' ? <Link key={href} to={href} onClick={() => setMenuPath(null)}>{label}</Link> : <NavLink key={href} to={href} onClick={() => setMenuPath(null)}>{label}</NavLink>)}<Link to="/profil" onClick={() => setMenuPath(null)}>{user?.name || 'Logga in'}</Link></motion.nav>}</AnimatePresence>
      </header>
      <main id="main" tabIndex={-1}>{children}</main>
      <footer className="site-footer">
        <div className="footer-main page-wrap">
          <div><Link to="/" className="brand footer-brand"><span className="brand-sun">☀</span><span>Ljusglimt</span></Link><p>En varsamt formgiven samling av positiva nyheter, tydliga källor och konstruktiva samtal.</p></div>
          <div><h2>Utforska</h2><Link to="/">Nyheter</Link><Link to="/sok?kategori=Djur">Djur</Link><Link to="/sok">Sök och filtrera</Link><Link to="/forum">Forum</Link></div>
          <div><h2>Transparens</h2><Link to="/om">Om och metod</Link><Link to="/om#kallor">Källor och märkning</Link><Link to="/profil">Mitt konto</Link></div>
          <div><h2>Nyhetsbrev · kommer snart</h2><p>Testa formuläret. Adressen sparas inte ännu.</p><NewsletterForm compact /></div>
        </div>
        <div className="footer-bottom page-wrap"><span>© 2026 Ljusglimt</span><span>Byggd med omtanke i Sverige</span></div>
      </footer>
    </div>
  )
}
