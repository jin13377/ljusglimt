import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchNews, inferCategory, isSuitableForPublicFeed, normalizeFetched, normalizeSeed } from './news'

afterEach(() => { vi.unstubAllGlobals() })

describe('news normalizer', () => {
  const generatedImage = {
    url: '/news-images/ai/articles/0123456789abcdefabcd-aabbccdd-v1.webp',
    alt: 'Redaktionell AI-illustration av ett lokalt naturprojekt.',
    model: 'gpt-image-2',
    prompt_version: 'editorial-concept-v1',
    source_fingerprint: 'aabbccddeeff00112233',
    width: 1280,
    height: 848,
    sha256: 'a'.repeat(64),
    generated_at: '2026-07-15T10:00:00Z',
  }
  const freeIllustration = {
    url: '/news-images/generated/0123456789abcdefabcd-aabbccdd-v1.svg',
    alt: 'Automatiskt skapad redaktionell illustration.',
    style_version: 'glimt-abstract-v1',
    source_fingerprint: 'aabbccddeeff00112233',
    width: 1280,
    height: 848,
    sha256: 'b'.repeat(64),
  }

  it('infers a category without relying on missing API fields', () => {
    expect(inferCategory({ id: '1', title: 'New solar energy record', url: 'https://example.com', source: 'Test' })).toBe('Miljö')
  })

  it('marks fetched items as fetched and uses source excerpts', () => {
    const item = normalizeFetched({ id: 'abc123', title: 'A hopeful study', url: 'https://example.com', source: 'NASA', source_excerpt: 'Useful context.' })
    expect(item.origin).toBe('fetched')
    expect(item.excerpt).toBe('Useful context.')
    expect(item.location).toBe('')
    expect(item.excerptLanguage).toBe('en')
    expect(item.image.kind).toBe('ai')
    expect(item.image.url).toBe('/news-images/ai/science.webp')
  })

  it('preserves demo source transparency', () => {
    const item = normalizeSeed({ id: 'demo', title: 'En ljus nyhet', summary: 'Sammanfattning', source: { name: 'WHO', url: 'https://who.int' } })
    expect(item.origin).toBe('demo')
    expect(item.source).toBe('WHO')
  })

  it('marks an agent summary as Swedish without changing the source-title language', () => {
    const item = normalizeFetched({ id: 'abc123', title: 'A hopeful study', url: 'https://example.com', source: 'NASA', language: 'en', agent_summary: 'En källbunden sammanfattning.' })
    expect(item.language).toBe('en')
    expect(item.excerptLanguage).toBe('sv')
    expect(item.hasAgentSummary).toBe(true)
  })

  it('uses a source image only with explicit verification, credit and rights evidence', () => {
    const verified = normalizeFetched({
      id: 'image', title: 'Community volunteers reach a milestone', url: 'https://example.com/story', source: 'Feed',
      source_image_verified: true, source_image_url: 'https://images.example.com/photo.jpg', source_image_alt: 'Volunteers at work',
      source_image_credit: 'Foto: Example', source_image_rights_url: 'https://example.com/rights',
    })
    const incomplete = normalizeFetched({
      id: 'unsafe', title: 'Community volunteers reach a milestone', url: 'https://example.com/story-2', source: 'Feed',
      source_image_verified: true, source_image_url: 'https://images.example.com/photo.jpg',
    })
    expect(verified.image.kind).toBe('source')
    expect(verified.image.credit).toBe('Foto: Example')
    expect(incomplete.image.kind).toBe('ai')
  })

  it('uses a source-bound unique AI image before the category fallback', () => {
    const item = normalizeFetched({
      id: '0123456789abcdefabcd', title: 'Volunteers restore a local wetland', url: 'https://example.com/story', source: 'Feed',
      source_fingerprint: 'aabbccddeeff00112233', ai_image: generatedImage,
    })
    expect(item.image.kind).toBe('ai')
    expect(item.image.aiOrigin).toBe('generated')
    expect(item.image.url).toBe(generatedImage.url)
    expect(item.fallbackImage?.aiOrigin).toBe('category')
  })

  it('uses a free local illustration without treating it as an AI image', () => {
    const item = normalizeFetched({
      id: '0123456789abcdefabcd', title: 'Volunteers restore a local wetland', url: 'https://example.com/free', source: 'Feed',
      source_fingerprint: 'aabbccddeeff00112233', generated_image: freeIllustration,
    })
    expect(item.image.kind).toBe('generated')
    expect(item.image.url).toBe(freeIllustration.url)
    expect(item.fallbackImage?.aiOrigin).toBe('category')
  })

  it('rejects stale AI images and keeps a generated backup behind a verified source image', () => {
    const stale = normalizeFetched({
      id: '0123456789abcdefabcd', title: 'Volunteers restore a local wetland', url: 'https://example.com/stale', source: 'Feed',
      source_fingerprint: 'ffffffffffffffffffff', ai_image: generatedImage,
    })
    const sourced = normalizeFetched({
      id: '0123456789abcdefabcd', title: 'Volunteers restore a local wetland', url: 'https://example.com/source', source: 'Feed',
      source_fingerprint: 'aabbccddeeff00112233', ai_image: generatedImage,
      source_image_verified: true, source_image_url: 'https://images.example.com/photo.jpg',
      source_image_credit: 'Foto: Example', source_image_rights_url: 'https://example.com/rights',
    })
    expect(stale.image.aiOrigin).toBe('category')
    expect(sourced.image.kind).toBe('source')
    expect(sourced.fallbackImage?.aiOrigin).toBe('generated')
  })

  it('filters sensitive candidates from the public feed', () => {
    const item = normalizeFetched({ id: 'abc123', title: 'A bloody rescue story', url: 'https://example.com', source: 'Feed' })
    expect(isSuitableForPublicFeed(item)).toBe(false)
  })

  it('filters audience prompts and syndicated feed noise', () => {
    const prompt = normalizeFetched({ id: 'question', title: 'What positive change have you seen?', url: 'https://example.com', source: 'Feed', source_excerpt: 'Share the stories you have witnessed. The post appeared first on Feed.' })
    expect(isSuitableForPublicFeed(prompt)).toBe(false)
  })

  it('requires a clear positive signal and rejects distressing rescue language', () => {
    const generic = normalizeFetched({ id: 'generic', title: 'A new policy update', url: 'https://example.com', source: 'Feed', source_excerpt: 'Officials shared the latest details.' })
    const distressing = normalizeFetched({ id: 'distressing', title: 'Volunteers rescue turtle with a crushed shell', url: 'https://example.com', source: 'Feed', source_excerpt: 'The animal is recovering.' })
    const stranded = normalizeFetched({ id: 'stranded', title: 'Rescuers find an animal stranded in a trap', url: 'https://example.com', source: 'Feed', source_excerpt: 'It was in distress and unable to move.' })
    const constructive = normalizeFetched({ id: 'constructive', title: 'Volunteers restore a local wetland', url: 'https://example.com', source: 'Feed', source_excerpt: 'The project reached a new milestone.' })
    expect(isSuitableForPublicFeed(generic)).toBe(false)
    expect(isSuitableForPublicFeed(distressing)).toBe(false)
    expect(isSuitableForPublicFeed(stranded)).toBe(false)
    expect(isSuitableForPublicFeed(constructive)).toBe(true)
  })

  it('uses the pipeline public eligibility decision when present', () => {
    const hidden = normalizeFetched({ id: 'hidden', title: 'Volunteers restore a local wetland', url: 'https://example.com/hidden', source: 'Feed', public_eligible: false })
    const approved = normalizeFetched({ id: 'approved', title: 'A neutral update', url: 'https://example.com/approved', source: 'Feed', public_eligible: true })
    expect(isSuitableForPublicFeed(hidden)).toBe(false)
    expect(isSuitableForPublicFeed(approved)).toBe(true)
  })

  it('keeps demo news available when the live API is temporarily down', async () => {
    const mockedFetch = vi.fn()
      .mockResolvedValueOnce(new Response('{"error":"offline"}', { status: 503 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ articles: [{ id: 'demo', title: 'En ljus nyhet', summary: 'Sammanfattning', source: { name: 'WHO', url: 'https://who.int' } }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', mockedFetch)
    const result = await fetchNews()
    expect(result.demoCount).toBe(1)
    expect(result.fetchedCount).toBe(0)
    expect(result.fetchedAvailable).toBe(false)
    expect(result.warning).toContain('automatiska flödet')
  })

  it('uses the bundled news feed when the API is unavailable on static hosting', async () => {
    const mockedFetch = vi.fn()
      .mockResolvedValueOnce(new Response('<!doctype html><title>Ljusglimt</title>', { status: 200, headers: { 'Content-Type': 'text/html' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ articles: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [{ id: 'static-1', title: 'A constructive update', url: 'https://example.com/news', source: 'Example', public_eligible: true }], generated_at: '2026-07-15T12:00:00Z' }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', mockedFetch)

    const result = await fetchNews()

    expect(mockedFetch).toHaveBeenNthCalledWith(3, '/data/news.json', undefined)
    expect(result.fetchedAvailable).toBe(true)
    expect(result.fetchedCount).toBe(1)
    expect(result.warning).toBe('')
  })
})
