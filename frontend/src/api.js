// Thin client for the FastAPI service. Paths are relative: proxied by Vite in
// development and served by FastAPI itself in production.

async function get(path, params = {}) {
  const q = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== null && v !== undefined && v !== ''))
  const res = await fetch(`${path}${q.size ? `?${q}` : ''}`)
  if (!res.ok) {
    let detail = res.statusText
    try { detail = (await res.json()).detail ?? detail } catch { /* not JSON */ }
    throw new Error(`${res.status}: ${detail}`)
  }
  return res.json()
}

export const api = {
  status: () => get('/status'),
  days: (replay) => get('/days', { replay }),
  wards: (day, replay) => get('/wards', { day, replay }),
  ward: (id, replay) => get(`/ward/${encodeURIComponent(id)}`, { replay }),
  events: (replay) => get('/events', { replay }),
}
