export class ApiError extends Error {
  status: number
  code?: string

  constructor(message: string, status: number, code?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

export async function api<T>(url: string, options: RequestInit = {}): Promise<T> {
  const timeout = AbortSignal.timeout(15000)
  const signal = options.signal ? AbortSignal.any([options.signal, timeout]) : timeout
  const headers = new Headers(options.headers)
  if (options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  try {
    const response = await fetch(url, {
      credentials: 'same-origin',
      ...options,
      headers,
      signal,
    })
    let data: unknown = {}
    const contentType = response.headers.get('content-type') || ''
    if (!contentType.toLowerCase().includes('application/json')) {
      throw new ApiError('Serverdelen är inte tillgänglig på den statiska webbplatsen.', 503, 'BACKEND_UNAVAILABLE')
    }
    try {
      data = await response.json()
    } catch {
      signal.throwIfAborted()
      throw new ApiError('Servern skickade ett oläsbart svar. Försök igen.', 502, 'INVALID_RESPONSE')
    }
    if (!response.ok) {
      const payload = data && typeof data === 'object' ? data as { error?: string; code?: string } : {}
      throw new ApiError(payload.error || 'Något gick fel. Försök igen.', response.status, payload.code)
    }
    return data as T
  } catch (reason) {
    if (timeout.aborted && !options.signal?.aborted) {
      throw new ApiError('Servern svarade inte i tid. Försök igen.', 504, 'REQUEST_TIMEOUT')
    }
    throw reason
  }
}

export function post<T>(url: string, payload: unknown): Promise<T> {
  return api<T>(url, { method: 'POST', body: JSON.stringify(payload) })
}

export function remove<T>(url: string): Promise<T> {
  return api<T>(url, { method: 'DELETE' })
}
