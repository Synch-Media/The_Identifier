export async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const headers: Record<string, string> = { 'X-Identifier-Local': '1' }
  if (body && !(body instanceof FormData)) headers['Content-Type'] = 'application/json'
  const response = await fetch('/api' + path, { method, headers, body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined })
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(typeof data.detail === 'string' ? data.detail : `Request failed (${response.status}). Check the local backend.`)
  }
  return response.json()
}
