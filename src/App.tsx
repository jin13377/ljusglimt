import { MotionConfig } from 'framer-motion'
import { BrowserRouter, Route, Routes, useLocation } from 'react-router-dom'
import { lazy, Suspense, useEffect, useRef } from 'react'
import { Layout } from './components/Layout'
import { AuthProvider } from './contexts/AuthContext'
import { SavedProvider } from './contexts/SavedContext'
import { usePageMetadata, websiteJsonLd } from './lib/seo'

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

function RouteMetadata() {
  const { pathname } = useLocation()
  const metadata = pathname === '/' || pathname === '/nyheter'
    ? { canonicalPath: '/', jsonLd: websiteJsonLd() }
    : pathname === '/sok'
      ? { title: 'Sök positiva nyheter', description: 'Sök bland Ljusglimts positiva nyheter och svenska källsammanfattningar.', canonicalPath: '/sok' }
      : pathname === '/forum'
        ? { title: 'Forum', description: 'Delta i vänliga och konstruktiva samtal i Ljusglimts forum.', canonicalPath: '/forum' }
        : pathname === '/profil'
          ? { title: 'Din profil', description: 'Hantera din profil och dina sparade nyheter på Ljusglimt.', canonicalPath: '/profil', noIndex: true }
          : pathname === '/om'
            ? { title: 'Om Ljusglimt', description: 'Så hittar, sammanfattar och märker Ljusglimt positiva nyheter och deras källor.', canonicalPath: '/om' }
            : pathname.startsWith('/nyhet/') || pathname.startsWith('/forum/')
              ? null
              : { title: 'Sidan hittades inte', canonicalPath: pathname, noIndex: true }
  return metadata ? <Metadata {...metadata} /> : null
}

function Metadata(metadata: Parameters<typeof usePageMetadata>[0]) {
  usePageMetadata(metadata)
  return null
}

export default function App() {
  return <MotionConfig reducedMotion="user">
    <BrowserRouter>
      <AuthProvider>
        <SavedProvider>
          <ScrollManager />
          <RouteMetadata />
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
