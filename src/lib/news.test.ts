import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchNews, inferCategory, isSuitableForPublicFeed, normalizeFetched, normalizeSeed } from './news'

afterEach(() => { vi.unstubAllGlobals() })

describe('news normalizer', () => {
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
    const constructive = normalizeFetched({ id: 'constructive', title: 'Volunteers restore a local wetland', url: 'https://example.com', source: 'Feed', source_excerpt: 'The project reached a new milestone.' })
    expect(isSuitableForPublicFeed(generic)).toBe(false)
    expect(isSuitableForPublicFeed(distressing)).toBe(false)
    expect(isSuitableForPublicFeed(constructive)).toBe(true)
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
})
