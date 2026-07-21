import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchNews, inferCategory, isSuitableForPublicFeed, normalizeFetched, normalizeSeed, selectDailyHero, selectFetchedHighlights, selectWorldHighlights } from './news'

afterEach(() => { vi.unstubAllGlobals() })

describe('news normalizer', () => {
  const generatedImage = {
    url: '/news-images/ai/articles/0123456789abcdefabcd-aabbccddeeff00112233-v1.webp',
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

  it('keeps the animal category and accepts only a validated YouTube embed', () => {
    const item = normalizeFetched({
      id: 'animal-video', title: 'Adorable animals become best friends', url: 'https://www.youtube.com/watch?v=PahtM3xtRus', source: 'The Dodo', category: 'Djur',
      source_video: {
        provider: 'youtube', video_id: 'PahtM3xtRus', title: 'Adorable animals become best friends',
        embed_url: 'https://www.youtube-nocookie.com/embed/PahtM3xtRus', source_url: 'https://www.youtube.com/watch?v=PahtM3xtRus',
      },
    })
    expect(item.category).toBe('Djur')
    expect(item.video?.videoId).toBe('PahtM3xtRus')
    expect(item.video?.embedUrl).toBe('https://www.youtube-nocookie.com/embed/PahtM3xtRus')
  })

  it('accepts a validated Dailymotion source video', () => {
    const item = normalizeFetched({
      id: 'animal-dailymotion', title: 'Surprise foster kittens find love', url: 'https://www.dailymotion.com/video/xamx6nm', source: 'The Dodo', category: 'Djur',
      source_video: {
        provider: 'dailymotion', video_id: 'xamx6nm', title: 'Surprise foster kittens find love',
        embed_url: 'https://geo.dailymotion.com/player.html?video=xamx6nm', source_url: 'https://www.dailymotion.com/video/xamx6nm',
      },
    })
    expect(item.video?.provider).toBe('dailymotion')
    expect(item.video?.embedUrl).toBe('https://geo.dailymotion.com/player.html?video=xamx6nm')
  })

  it('accepts a validated YouTube video on a regular science news article', () => {
    const item = normalizeFetched({
      id: 'nasa-video', title: 'NASA Uses Subscale Aircraft to Accelerate Flight Innovation',
      url: 'https://www.nasa.gov/example/flight-innovation', source: 'NASA News Releases',
      source_excerpt: 'The research platform advances practical innovation.',
      display_title_sv: 'NASA testar små flygplan för snabbare innovation',
      agent_summary: 'NASA provar nya flygidéer med små testflygplan.',
      public_eligible: true,
      source_video: {
        provider: 'youtube', video_id: 'Fb08ooo7MhI', title: 'NASA flight innovation',
        embed_url: 'https://www.youtube-nocookie.com/embed/Fb08ooo7MhI', source_url: 'https://www.youtube.com/watch?v=Fb08ooo7MhI',
      },
    })
    expect(item.category).toBe('Vetenskap')
    expect(item.title).toBe('NASA testar små flygplan för snabbare innovation')
    expect(item.source).toBe('NASA:s nyheter')
    expect(item.video?.provider).toBe('youtube')
    expect(isSuitableForPublicFeed(item)).toBe(true)
  })

  it('preserves demo source transparency', () => {
    const item = normalizeSeed({ id: 'demo', title: 'En ljus nyhet', summary: 'Sammanfattning', source: { name: 'WHO', url: 'https://who.int' } })
    expect(item.origin).toBe('demo')
    expect(item.source).toBe('WHO')
  })

  it('rotates the daily hero on consecutive Stockholm calendar days', () => {
    const stories = [
      normalizeFetched({ id: 'daily-a', title: 'A', display_title_sv: 'Nyhet A', agent_summary: 'Svensk sammanfattning A.', published_at: '2026-07-16T08:00:00Z', url: 'https://example.com/a', source: 'KÃ¤lla', public_eligible: true }),
      normalizeFetched({ id: 'daily-b', title: 'B', display_title_sv: 'Nyhet B', agent_summary: 'Svensk sammanfattning B.', published_at: '2026-07-15T08:00:00Z', url: 'https://example.com/b', source: 'KÃ¤lla', public_eligible: true }),
      normalizeFetched({ id: 'daily-c', title: 'C', display_title_sv: 'Nyhet C', agent_summary: 'Svensk sammanfattning C.', published_at: '2026-07-14T08:00:00Z', url: 'https://example.com/c', source: 'KÃ¤lla', public_eligible: true }),
    ]
    const first = selectDailyHero(stories, new Date('2026-07-17T08:00:00Z'))
    const laterSameDay = selectDailyHero(stories, new Date('2026-07-17T20:00:00Z'))
    const nextDay = selectDailyHero(stories, new Date('2026-07-18T08:00:00Z'))

    expect(laterSameDay?.id).toBe(first?.id)
    expect(nextDay?.id).not.toBe(first?.id)
  })

  it('chooses the daily hero only from the three newest approved stories', () => {
    const stories = [
      normalizeFetched({ id: 'fresh-a', title: 'A', display_title_sv: 'Nyhet A', agent_summary: 'Svensk sammanfattning A.', published_at: '2026-07-16T08:00:00Z', url: 'https://example.com/a', source: 'Källa', public_eligible: true }),
      normalizeFetched({ id: 'fresh-b', title: 'B', display_title_sv: 'Nyhet B', agent_summary: 'Svensk sammanfattning B.', published_at: '2026-07-15T08:00:00Z', url: 'https://example.com/b', source: 'Källa', public_eligible: true }),
      normalizeFetched({ id: 'fresh-c', title: 'C', display_title_sv: 'Nyhet C', agent_summary: 'Svensk sammanfattning C.', published_at: '2026-07-14T08:00:00Z', url: 'https://example.com/c', source: 'Källa', public_eligible: true }),
      normalizeFetched({ id: 'older-d', title: 'D', display_title_sv: 'Nyhet D', agent_summary: 'Svensk sammanfattning D.', published_at: '2026-07-13T08:00:00Z', url: 'https://example.com/d', source: 'Källa', public_eligible: true }),
    ]

    const hero = selectDailyHero(stories, new Date('2026-07-17T08:00:00Z'))

    expect(['fresh-a', 'fresh-b', 'fresh-c']).toContain(hero?.id)
  })

  it('prefers approved stories published within the last seven days', () => {
    const stories = [
      normalizeFetched({ id: 'within-week', title: 'Fresh', display_title_sv: 'Färsk nyhet', agent_summary: 'En färsk svensk sammanfattning.', published_at: '2026-07-18T08:00:00Z', url: 'https://example.com/fresh', source: 'Källa', public_eligible: true }),
      normalizeFetched({ id: 'stale-a', title: 'Stale A', display_title_sv: 'Äldre nyhet A', agent_summary: 'En äldre svensk sammanfattning.', published_at: '2026-07-05T08:00:00Z', url: 'https://example.com/stale-a', source: 'Källa', public_eligible: true }),
      normalizeFetched({ id: 'stale-b', title: 'Stale B', display_title_sv: 'Äldre nyhet B', agent_summary: 'En äldre svensk sammanfattning.', published_at: '2026-07-04T08:00:00Z', url: 'https://example.com/stale-b', source: 'Källa', public_eligible: true }),
    ]

    expect(selectDailyHero(stories, new Date('2026-07-19T08:00:00Z'))?.id).toBe('within-week')
  })

  it('prefers a fresh Swedish original source for the daily hero', () => {
    const swedish = normalizeFetched({ id: 'swedish', title: 'Svensk originalnyhet', source_excerpt: 'Ett svenskt forskningsframsteg.', language: 'sv', published_at: '2026-07-16T08:00:00Z', url: 'https://example.se/svensk', source: 'Svensk källa', public_eligible: true })
    const international = normalizeFetched({ id: 'international', title: 'International progress', display_title_sv: 'Internationellt framsteg', agent_summary: 'En svensk sammanfattning.', language: 'en', published_at: '2026-07-15T08:00:00Z', url: 'https://example.com/world', source: 'International source', public_eligible: true })

    expect(selectDailyHero([swedish, international], new Date('2026-07-17T08:00:00Z'))?.id).toBe('swedish')
  })

  it('keeps the daily hero out of the fresh-news section', () => {
    const hero = normalizeFetched({ id: 'hero', title: 'Hero', display_title_sv: 'Huvudnyhet', agent_summary: 'Svensk sammanfattning.', language: 'sv', published_at: '2026-07-18T08:00:00Z', url: 'https://example.com/hero', source: 'Källa', public_eligible: true })
    const next = normalizeFetched({ id: 'next', title: 'Next', display_title_sv: 'Nästa nyhet', agent_summary: 'Svensk sammanfattning.', language: 'sv', published_at: '2026-07-17T08:00:00Z', url: 'https://example.com/next', source: 'Källa', public_eligible: true })

    expect(selectFetchedHighlights([hero, next], hero.id).map((article) => article.id)).toEqual(['next'])
  })

  it('collects only international original sources in the world section', () => {
    const swedish = normalizeFetched({ id: 'swedish', title: 'Svensk nyhet', source_excerpt: 'Ett svenskt framsteg.', language: 'sv', published_at: '2026-07-18T08:00:00Z', url: 'https://example.se/svensk', source: 'Svensk källa', public_eligible: true })
    const world = normalizeFetched({ id: 'world', title: 'World progress', display_title_sv: 'Framsteg i världen', agent_summary: 'En svensk sammanfattning.', language: 'en', published_at: '2026-07-17T08:00:00Z', url: 'https://example.com/world', source: 'International source', public_eligible: true })

    expect(selectWorldHighlights([swedish, world]).map((article) => article.id)).toEqual(['world'])
  })

  it('uses the featured source summary when no suitable fetched hero exists', () => {
    const featured = normalizeSeed({ id: 'fallback', title: 'Reservnyhet', summary: 'Sammanfattning', featured: true, source: { name: 'WHO', url: 'https://who.int' } })
    const english = normalizeFetched({ id: 'english', title: 'English story', source_excerpt: 'English summary', published_at: '2026-07-16T08:00:00Z', url: 'https://example.com/en', source: 'Feed' })

    expect(selectDailyHero([english, featured], new Date('2026-07-17T08:00:00Z'))?.id).toBe('fallback')
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
    const constructive = normalizeFetched({ id: 'constructive', title: 'Volunteers restore a local wetland', url: 'https://example.com', source: 'Feed', source_excerpt: 'The project reached a new milestone.', display_title_sv: 'Volontärer återställer en våtmark', agent_summary: 'Projektet nådde en ny milstolpe.', public_eligible: true })
    expect(isSuitableForPublicFeed(generic)).toBe(false)
    expect(isSuitableForPublicFeed(distressing)).toBe(false)
    expect(isSuitableForPublicFeed(stranded)).toBe(false)
    expect(isSuitableForPublicFeed(constructive)).toBe(true)
  })

  it('uses the pipeline public eligibility decision when present', () => {
    const hidden = normalizeFetched({ id: 'hidden', title: 'Volunteers restore a local wetland', url: 'https://example.com/hidden', source: 'Feed', public_eligible: false })
    const approved = normalizeFetched({ id: 'approved', title: 'A neutral update', url: 'https://example.com/approved', source: 'Feed', display_title_sv: 'En svensk nyhet', agent_summary: 'En svensk sammanfattning.', public_eligible: true })
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
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [{ id: 'static-1', title: 'A constructive update', display_title_sv: 'En konstruktiv nyhet', agent_summary: 'En svensk sammanfattning.', url: 'https://example.com/news', source: 'Example', public_eligible: true }], generated_at: '2026-07-15T12:00:00Z' }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', mockedFetch)

    const result = await fetchNews()

    expect(mockedFetch).toHaveBeenNthCalledWith(3, '/data/news.json', undefined)
    expect(result.fetchedAvailable).toBe(true)
    expect(result.fetchedCount).toBe(1)
    expect(result.warning).toBe('')
  })
})
