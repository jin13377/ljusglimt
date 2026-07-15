import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from './api'

describe('api', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('rejects an HTML SPA fallback instead of treating it as API data', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<!doctype html>', {
      status: 200,
      headers: { 'Content-Type': 'text/html' },
    })))

    await expect(api('/api/forum/index')).rejects.toMatchObject({
      status: 503,
      code: 'BACKEND_UNAVAILABLE',
    })
  })

  it('returns valid JSON responses', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })))

    await expect(api<{ ok: boolean }>('/api/check')).resolves.toEqual({ ok: true })
  })
})
