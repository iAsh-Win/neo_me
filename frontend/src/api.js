const KEY = 'neo_token'

export const getToken = () => localStorage.getItem(KEY)
export const setToken = (t) => (t ? localStorage.setItem(KEY, t) : localStorage.removeItem(KEY))

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

async function request(method, url, body, isForm) {
  const headers = {}
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  if (body && !isForm) headers['Content-Type'] = 'application/json'
  let res
  try {
    res = await fetch(url, { method, headers, body: isForm ? body : body ? JSON.stringify(body) : undefined })
  } catch {
    throw new ApiError('Cannot reach the server. Please check your connection and try again.', 0)
  }
  if (res.status === 401 && token && !url.includes('/auth/login')) {
    setToken(null)
    window.dispatchEvent(new Event('neo-logout'))
  }
  let data = null
  try {
    data = await res.json()
  } catch {
    /* no body */
  }
  if (!res.ok) throw new ApiError(data?.detail || 'Something went wrong. Please try again.', res.status)
  return data
}

export const api = {
  get: (u) => request('GET', u),
  post: (u, b) => request('POST', u, b ?? {}),
  put: (u, b) => request('PUT', u, b),
  patch: (u, b) => request('PATCH', u, b),
  del: (u) => request('DELETE', u),
  upload: (u, form) => request('POST', u, form, true),
}

// links that open in the browser (downloads) cannot send headers, so they carry the token
export const fileUrl = (path) => `${path}${path.includes('?') ? '&' : '?'}token=${getToken()}`
