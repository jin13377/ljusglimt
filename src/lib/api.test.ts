import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from './api'

describe('api', () => {
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); vi.useRealTimers() })

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

  it('rejects malformed JSON instead of returning an empty success', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{broken', {headers: {'Content-Type': 'application/json'}})))
    await expect(api('/api/saved')).rejects.toMatchObject({status: 502, code: 'INVALID_RESPONSE'})
  })

  it('keeps Headers instances and the caller cancellation signal', async () => {
    const controller = new AbortController()
    const fetchMock = vi.fn().mockResolvedValue(new Response('{}', {headers: {'Content-Type': 'application/json'}}))
    vi.stubGlobal('fetch', fetchMock)
    await api('/api/check', {body: '{}', headers: new Headers({'X-Check': 'yes'}), signal: controller.signal})
    const options = fetchMock.mock.calls[0][1] as RequestInit
    expect(new Headers(options.headers).get('X-Check')).toBe('yes')
    expect(new Headers(options.headers).get('Content-Type')).toBe('application/json')
    controller.abort()
    expect(options.signal?.aborted).toBe(true)
  })

  it('bounds an unresponsive request and reports a retryable timeout', async () => {
    vi.useFakeTimers()
    const controller = new AbortController()
    vi.spyOn(AbortSignal, 'timeout').mockImplementation(ms => { setTimeout(() => controller.abort(), ms); return controller.signal })
    vi.stubGlobal('fetch', vi.fn((_url, options: RequestInit) => new Promise((_resolve, reject) => options.signal?.addEventListener('abort', () => reject(new Error('aborted'))))))
    const assertion = expect(api('/api/check')).rejects.toMatchObject({status: 504, code: 'REQUEST_TIMEOUT'})
    await vi.advanceTimersByTimeAsync(15000)
    await assertion
    vi.restoreAllMocks()
  })
})
