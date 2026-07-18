import { describe, expect, it } from 'vitest'
import worker from './index'

function createEnvironment(
  requestedPaths: string[],
  knownSlugs = ['en-saker-slug'],
  manifestFailure?: 'missing' | 'invalid' | 'throw' | 'throw-all',
) {
  return {
    ASSETS: {
      fetch(input: RequestInfo | URL) {
        const request = input instanceof Request ? input : new Request(input)
        const path = new URL(request.url).pathname
        requestedPaths.push(path)
        if (manifestFailure === 'throw-all') return Promise.reject(new Error('All assets unavailable'))
        if (path === '/seo/article-slugs.json') {
          if (manifestFailure === 'missing') return Promise.resolve(new Response('', { status: 404 }))
          if (manifestFailure === 'invalid') return Promise.resolve(new Response('{', { headers: { 'content-type': 'application/json' } }))
          if (manifestFailure === 'throw') return Promise.reject(new Error('Asset unavailable'))
          return Promise.resolve(Response.json(knownSlugs))
        }
        return Promise.resolve(new Response('<!doctype html><html><head><title>Ljusglimt</title><link rel="canonical" href="https://example.com/"></head><body><div id="root"></div><script type="module" src="/assets/app.js"></script></body></html>', {
          headers: { 'content-type': 'text/html; charset=UTF-8' },
        }))
      },
    },
  }
}

describe('article asset routing', () => {
  it.each(['GET', 'HEAD'])('serves %s article routes from extensionless generated assets', async (method) => {
    const requestedPaths: string[] = []
    const response = await worker.fetch(
      new Request('https://example.com/nyhet/en-saker-slug', { method }),
      createEnvironment(requestedPaths) as never,
    )

    expect(response.status).toBe(200)
    expect(requestedPaths).toEqual(['/seo/article-slugs.json', '/seo/articles/en-saker-slug'])
  })

  it('returns a noindex 404 shell for an unknown article slug', async () => {
    const requestedPaths: string[] = []
    const response = await worker.fetch(
      new Request('https://example.com/nyhet/finns-inte'),
      createEnvironment(requestedPaths) as never,
    )
    const html = await response.text()

    expect(response.status).toBe(404)
    expect(response.headers.get('content-type')).toContain('text/html')
    expect(html).toContain('<meta name="robots" content="noindex, nofollow">')
    expect(html).toContain('<div id="root"></div>')
    expect(html).toContain('src="/assets/app.js"')
    expect(html).not.toContain('rel="canonical"')
  })

  it('returns an empty no-store 404 response to HEAD for an unknown article slug', async () => {
    const response = await worker.fetch(
      new Request('https://example.com/nyhet/finns-inte', { method: 'HEAD' }),
      createEnvironment([]) as never,
    )

    expect(response.status).toBe(404)
    expect(response.headers.get('content-type')).toContain('text/html')
    expect(response.headers.get('cache-control')).toBe('no-store')
    expect(await response.text()).toBe('')
  })

  it.each([
    ['en-saker-slug', 'missing'],
    ['finns-inte', 'invalid'],
    ['en-saker-slug', 'throw'],
    ['en-saker-slug', 'throw-all'],
  ] as const)('returns a noindex 503 shell when the article manifest is unavailable: %s / %s', async (slug, failure) => {
    const response = await worker.fetch(
      new Request(`https://example.com/nyhet/${slug}`),
      createEnvironment([], ['en-saker-slug'], failure) as never,
    )
    const html = await response.text()

    expect(response.status).toBe(503)
    expect(response.headers.get('content-type')).toContain('text/html')
    expect(response.headers.get('cache-control')).toBe('no-store')
    expect(response.headers.get('retry-after')).toBe('60')
    expect(html).toContain('<meta name="robots" content="noindex, nofollow">')
    expect(html).toContain('<div id="root"></div>')
    expect(html).not.toContain('rel="canonical"')
  })

  it.each([
    '/nyhet/%E0%A4%A',
    '/nyhet/en%2Fannan-slug',
  ])('falls back safely for malformed or nested article paths: %s', async (path) => {
    const requestedPaths: string[] = []
    const response = await worker.fetch(
      new Request(`https://example.com${path}`),
      createEnvironment(requestedPaths) as never,
    )

    expect(response.status).toBe(200)
    expect(requestedPaths).toEqual([path])
  })
})

describe('security headers', () => {
  it.each([
    '/',
    '/nyhet/en-saker-slug',
    '/nyhet/finns-inte',
  ])('protects responses for %s', async (path) => {
    const response = await worker.fetch(
      new Request(`https://example.com${path}`),
      createEnvironment([]) as never,
    )

    expect(response.headers.get('x-content-type-options')).toBe('nosniff')
    expect(response.headers.get('referrer-policy')).toBe('strict-origin-when-cross-origin')
    expect(response.headers.get('x-frame-options')).toBe('DENY')
  })
})
