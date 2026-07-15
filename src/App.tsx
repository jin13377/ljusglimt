import { MotionConfig } from 'framer-motion'
import { BrowserRouter, Route, Routes, useLocation } from 'react-router-dom'
import { lazy, Suspense, useEffect, useRef } from 'react'
import { Layout } from './components/Layout'
import { AuthProvider } from './contexts/AuthContext'
import { SavedProvider } from './contexts/SavedContext'

const HomePage = lazy(() => import('./pages/HomePage').then((module) => ({ default: module.HomePage })))
const ArticlePage = lazy(() => import('./pages/ArticlePage').then((module) => ({ default: module.ArticlePage })))
const SearchPage = lazy(() => import('./pages/SearchPage').then((module) => ({ default: module.SearchPage })))
const ProfilePage = lazy(() => import('./pages/ProfilePage').then((module) => ({ default: module.ProfilePage })))
const AboutPage = lazy(() => import('./pages/AboutPage').then((module) => ({ default: module.AboutPage })))
const NotFoundPage = lazy(() => import('./pages/NotFoundPage').then((module) => ({ default: module.NotFoundPage })))
const ForumIndexPage = lazy(() => import('./pages/ForumPage').then((module) => ({ default: module.ForumIndexPage })))
const ForumSectionPage = lazy(() => import('./pages/ForumPage').then((module) => ({ default: module.ForumSectionPage })))
const ForumThreadPage = lazy(() => import('./pages/ForumPage').then((module) => ({ default: module.ForumThreadPage })))

function ScrollManager() {
  const { pathname, hash } = useLocation()
  const firstRender = useRef(true)
  useEffect(() => {
    const title = pathname === '/' || pathname === '/nyheter' ? 'Ljusglimt – nyheter som ger perspektiv'
      : pathname === '/sok' ? 'Sök nyheter – Ljusglimt'
        : pathname.startsWith('/nyhet/') ? 'Nyhet – Ljusglimt'
          : pathname.startsWith('/forum/trad/') ? 'Forumtråd – Ljusglimt'
            : pathname.startsWith('/forum/sektion/') ? 'Forumavdelning – Ljusglimt'
              : pathname === '/forum' ? 'Forum – Ljusglimt'
                : pathname === '/profil' ? 'Profil – Ljusglimt'
                  : pathname === '/om' ? 'Om Ljusglimt'
                    : 'Sidan hittades inte – Ljusglimt'
    document.title = title
    const timer = window.setTimeout(() => {
      if (hash) document.getElementById(decodeURIComponent(hash.slice(1)))?.scrollIntoView()
      else window.scrollTo({ top: 0, behavior: 'auto' })
      if (!firstRender.current) document.querySelector<HTMLElement>('#main')?.focus({ preventScroll: true })
      firstRender.current = false
    }, 50)
    return () => window.clearTimeout(timer)
  }, [hash, pathname])
  return null
}

export default function App() {
  return <MotionConfig reducedMotion="user">
    <BrowserRouter>
      <AuthProvider>
        <SavedProvider>
          <ScrollManager />
          <Layout>
            <Suspense fallback={<div className="route-loading" role="status">Laddar sidan…</div>}>
              <Routes>
                <Route path="/" element={<HomePage />} />
                <Route path="/nyheter" element={<HomePage />} />
                <Route path="/nyhet/:id" element={<ArticlePage />} />
                <Route path="/sok" element={<SearchPage />} />
                <Route path="/forum" element={<ForumIndexPage />} />
                <Route path="/forum/sektion/:sectionId" element={<ForumSectionPage />} />
                <Route path="/forum/trad/:topicId" element={<ForumThreadPage />} />
                <Route path="/profil" element={<ProfilePage />} />
                <Route path="/om" element={<AboutPage />} />
                <Route path="*" element={<NotFoundPage />} />
              </Routes>
            </Suspense>
          </Layout>
        </SavedProvider>
      </AuthProvider>
    </BrowserRouter>
  </MotionConfig>
}
