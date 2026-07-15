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
  const response = await fetch(url, {
    credentials: 'same-origin',
    ...options,
    headers: options.body
      ? { 'Content-Type': 'application/json', ...(options.headers ?? {}) }
      : options.headers,
  })
  let data: unknown = {}
  try {
    data = await response.json()
  } catch {
    data = {}
  }
  if (!response.ok) {
    const payload = data as { error?: string; code?: string }
    throw new ApiError(payload.error || 'Något gick fel. Försök igen.', response.status, payload.code)
  }
  return data as T
}

export function post<T>(url: string, payload: unknown): Promise<T> {
  return api<T>(url, { method: 'POST', body: JSON.stringify(payload) })
}

export function remove<T>(url: string): Promise<T> {
  return api<T>(url, { method: 'DELETE' })
}
