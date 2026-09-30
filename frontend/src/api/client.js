const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const TOKEN_KEY = 'medicerca_token'

export class ApiError extends Error {
  constructor(message, status, detail) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

function toQuery(params) {
  const entries = Object.entries(params || {}).filter(([, v]) => v !== undefined && v !== null && v !== '')
  if (entries.length === 0) return ''
  return `?${new URLSearchParams(entries).toString()}`
}

async function request(path, { method = 'GET', body, auth = false, headers = {} } = {}) {
  const finalHeaders = { ...headers }
  let finalBody
  if (body instanceof FormData) {
    // El navegador pone el Content-Type con el boundary correcto solo si
    // no lo fijamos nosotros a mano.
    finalBody = body
  } else if (body !== undefined) {
    finalHeaders['Content-Type'] = 'application/json'
    finalBody = JSON.stringify(body)
  }
  if (auth) {
    const token = getToken()
    if (token) finalHeaders.Authorization = `Bearer ${token}`
  }

  let response
  try {
    response = await fetch(`${BASE_URL}${path}`, { method, headers: finalHeaders, body: finalBody })
  } catch {
    throw new ApiError('No se pudo conectar con el servidor. Verifica que el backend esté disponible.', 0, null)
  }

  if (response.status === 204) return null

  const text = await response.text()
  let data = null
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = text
    }
  }

  if (!response.ok) {
    let detail = data && typeof data === 'object' ? data.detail : data
    if (Array.isArray(detail)) {
      // FastAPI 422: lista de errores de validación de Pydantic.
      detail = detail.map((item) => item.msg || JSON.stringify(item)).join(' · ')
    }
    throw new ApiError(detail || response.statusText || 'Ocurrió un error inesperado', response.status, detail)
  }

  return data
}

export const api = {
  get: (path, params, opts) => request(`${path}${toQuery(params)}`, { ...opts, method: 'GET' }),
  post: (path, body, opts) => request(path, { ...opts, method: 'POST', body }),
  patch: (path, body, opts) => request(path, { ...opts, method: 'PATCH', body }),
}
