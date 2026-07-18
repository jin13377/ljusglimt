import { describe, expect, it } from 'vitest'
import worker from './index'

function createEnvironment(requestedPaths: string[]) {
  return {
    ASSETS: {
      fetch(input: RequestInfo | URL) {
        const request = input instanceof Request ? input : new Request(input)
        requestedPaths.push(new URL(request.url).pathname)
        return Promise.resolve(new Response('<!doctype html><div id="root"></div>', {
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
    expect(requestedPaths).toEqual(['/seo/articles/en-saker-slug'])
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
