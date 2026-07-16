import { useEffect } from 'react'

export const SITE_URL = 'https://ljusglimt.daniel-eklund1981.workers.dev'
export const SITE_NAME = 'Ljusglimt'
export const DEFAULT_TITLE = 'Ljusglimt – positiva nyheter som ger perspektiv'
export const DEFAULT_DESCRIPTION = 'Ljusglimt samlar positiva nyheter, konstruktiva framsteg och vänliga samtal med tydliga länkar till originalkällorna.'

type JsonLd = Record<string, unknown> | Record<string, unknown>[]

export interface PageMetadata {
  title?: string
  description?: string
  canonicalPath?: string
  image?: string
  imageAlt?: string
  type?: 'website' | 'article'
  noIndex?: boolean
  jsonLd?: JsonLd
}

function absoluteUrl(value: string): string {
  if (/^https?:\/\//i.test(value)) return value
  return new URL(value.startsWith('/') ? value : `/${value}`, SITE_URL).toString()
}

function setMeta(selector: string, attributes: Record<string, string>) {
  let element = document.head.querySelector<HTMLMetaElement>(selector)
  if (!element) {
    element = document.createElement('meta')
    element.dataset.ljusglimtSeo = 'true'
    document.head.appendChild(element)
  }
  Object.entries(attributes).forEach(([name, value]) => element!.setAttribute(name, value))
}

function setCanonical(url: string) {
  let element = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]')
  if (!element) {
    element = document.createElement('link')
    element.rel = 'canonical'
    element.dataset.ljusglimtSeo = 'true'
    document.head.appendChild(element)
  }
  element.href = url
}

export function usePageMetadata({
  title,
  description = DEFAULT_DESCRIPTION,
  canonicalPath = '/',
  image = '/news-images/ai/community.webp',
  imageAlt = 'Ljusglimt – positiva nyheter som ger perspektiv',
  type = 'website',
  noIndex = false,
  jsonLd,
}: PageMetadata) {
  useEffect(() => {
    const fullTitle = title ? `${title} – ${SITE_NAME}` : DEFAULT_TITLE
    const canonical = absoluteUrl(canonicalPath)
    const socialImage = absoluteUrl(image)
    document.title = fullTitle
    setCanonical(canonical)
    setMeta('meta[name="description"]', { name: 'description', content: description })
    setMeta('meta[name="robots"]', { name: 'robots', content: noIndex ? 'noindex, nofollow' : 'index, follow, max-image-preview:large' })
    setMeta('meta[property="og:title"]', { property: 'og:title', content: fullTitle })
    setMeta('meta[property="og:description"]', { property: 'og:description', content: description })
    setMeta('meta[property="og:type"]', { property: 'og:type', content: type })
    setMeta('meta[property="og:url"]', { property: 'og:url', content: canonical })
    setMeta('meta[property="og:image"]', { property: 'og:image', content: socialImage })
    setMeta('meta[property="og:image:alt"]', { property: 'og:image:alt', content: imageAlt })
    setMeta('meta[name="twitter:card"]', { name: 'twitter:card', content: 'summary_large_image' })
    setMeta('meta[name="twitter:title"]', { name: 'twitter:title', content: fullTitle })
    setMeta('meta[name="twitter:description"]', { name: 'twitter:description', content: description })
    setMeta('meta[name="twitter:image"]', { name: 'twitter:image', content: socialImage })
    const googleVerification = import.meta.env.VITE_GOOGLE_SITE_VERIFICATION?.trim()
    if (googleVerification) setMeta('meta[name="google-site-verification"]', { name: 'google-site-verification', content: googleVerification })

    document.head.querySelectorAll('script[data-ljusglimt-jsonld]').forEach((element) => element.remove())
    const entries = jsonLd ? (Array.isArray(jsonLd) ? jsonLd : [jsonLd]) : []
    entries.forEach((entry) => {
      const script = document.createElement('script')
      script.type = 'application/ld+json'
      script.dataset.ljusglimtJsonld = 'true'
      script.text = JSON.stringify(entry).replace(/</g, '\\u003c')
      document.head.appendChild(script)
    })
  }, [canonicalPath, description, image, imageAlt, jsonLd, noIndex, title, type])
}

export function websiteJsonLd(): JsonLd {
  return [
    {
      '@context': 'https://schema.org',
      '@type': 'Organization',
      name: SITE_NAME,
      url: SITE_URL,
      logo: `${SITE_URL}/sun.svg`,
    },
    {
      '@context': 'https://schema.org',
      '@type': 'WebSite',
      name: SITE_NAME,
      url: SITE_URL,
      inLanguage: 'sv-SE',
      potentialAction: {
        '@type': 'SearchAction',
        target: `${SITE_URL}/sok?q={search_term_string}`,
        'query-input': 'required name=search_term_string',
      },
    },
  ]
}
