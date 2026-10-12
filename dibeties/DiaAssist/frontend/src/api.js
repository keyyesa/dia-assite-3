// Small fetch wrapper: adds the bearer token and turns API errors into readable messages.
const KEY = 'diaassist_token'
export const getToken = () => { try { return localStorage.getItem(KEY) } catch { return null } }
export const setToken = (t) => { try { t ? localStorage.setItem(KEY, t) : localStorage.removeItem(KEY) } catch { /* private mode */ } }

async function request(method, path, body, isForm = false) {
  const headers = {}
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  if (body && !isForm) headers['Content-Type'] = 'application/json'
  let res
  try {
    res = await fetch(`/api${path}`, { method, headers, body: body ? (isForm ? body : JSON.stringify(body)) : undefined })
  } catch {
    throw new Error('Cannot reach the server. Is the backend running on port 8000?')
  }
  let data = null
  try { data = await res.json() } catch { /* empty body */ }
  if (!res.ok) {
    const d = data && (data.detail ?? data.message)
    const msg = typeof d === 'string' ? d : Array.isArray(d) ? d.map((e) => e.msg).join('; ') : `Request failed (${res.status})`
    const err = new Error(msg); err.status = res.status
    throw err
  }
  return data
}

export const api = {
  get: (p) => request('GET', p),
  post: (p, b = {}) => request('POST', p, b),
  put: (p, b = {}) => request('PUT', p, b),
  del: (p) => request('DELETE', p),
  form: (p, formData) => request('POST', p, formData, true),
}

export const money = (n) => `Rs ${Number(n || 0).toLocaleString()}`
export const isoDate = (d) => {
  const x = new Date(d.getTime() - d.getTimezoneOffset() * 60000)
  return x.toISOString().slice(0, 10)
}
export const nextDays = (n = 14) => Array.from({ length: n }, (_, i) => { const d = new Date(); d.setDate(d.getDate() + i); return d })
export const dayLabel = (d) => d.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' })
