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

// Optional API token for write actions (set by the officer in the Alerts tab when the server requires it)
export function getToken() { try { return localStorage.getItem('heat-api-token') || '' } catch { return '' } }
export function setToken(t) { try { localStorage.setItem('heat-api-token', t) } catch { /* storage unavailable */ } }

async function send(method, path, body) {
  const headers = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (token) headers['X-API-Token'] = token
  const res = await fetch(path, { method, headers, body: body ? JSON.stringify(body) : undefined })
  let data = null
  try { data = await res.json() } catch { /* empty */ }
  if (!res.ok) throw new Error(`${res.status}: ${data?.detail ?? res.statusText}`)
  return data
}

export const api = {
  status: () => get('/status'),
  days: (replay) => get('/days', { replay }),
  wards: (day, replay) => get('/wards', { day, replay }),
  ward: (id, replay) => get(`/ward/${encodeURIComponent(id)}`, { replay }),
  events: (replay) => get('/events', { replay }),
  actions: (id, day, replay) => get(`/ward/${encodeURIComponent(id)}/actions`, { day, replay }),
  workWindows: (id, day, replay, acclimatized) => get(`/ward/${encodeURIComponent(id)}/work-windows`, { day, replay, acclimatized }),
  advisories: (id, day, replay) => get(`/ward/${encodeURIComponent(id)}/advisories`, { day, replay }),
  priorities: (day, replay, view) => get('/priorities', { day, replay, view }),
  cooling: () => get('/cooling'),
  allocation: (day, replay, cooling_units, ambulances) => get('/allocation', { day, replay, cooling_units, ambulances }),
  dashboard: (day, replay, view) => get('/dashboard', { day, replay, view }),
  alerts: (replay) => get('/alerts', { replay }),
  alert: (id) => get(`/alerts/${id}`),
  preview: (id, ward, lang, audience) => get(`/alerts/${id}/preview`, { ward, lang, audience }),
  audit: (alertId) => get('/audit', { alert_id: alertId, limit: 50 }),
  generate: (replay) => send('POST', `/alerts/generate${replay ? `?replay=${encodeURIComponent(replay)}` : ''}`),
  editAlert: (id, body) => send('PATCH', `/alerts/${id}`, body),
  approve: (id, officer, note) => send('POST', `/alerts/${id}/approve`, { officer, note }),
  reject: (id, officer, reason) => send('POST', `/alerts/${id}/reject`, { officer, reason }),
  dispatch: (id, officer) => send('POST', `/alerts/${id}/dispatch`, { officer }),
  runScenario: (changes, replay) => send('POST', '/scenarios/run', { changes, replay }),
  saveScenario: (name, author, changes, replay) => send('POST', '/scenarios', { name, author, changes, replay }),
  scenarios: () => get('/scenarios'),
  scenario: (id) => get(`/scenarios/${id}`),
  report: (body, replay) => send('POST', `/reports${replay ? `?replay=${encodeURIComponent(replay)}` : ''}`, body),
  reportSummary: (replay, day) => get('/reports/summary', { replay, day }),
  recalibration: (replay) => get('/reports/recalibration', { replay }),
  seedReports: (replay) => send('POST', `/reports/synthetic?replay=${encodeURIComponent(replay)}`),
}
