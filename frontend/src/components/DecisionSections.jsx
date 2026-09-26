import { useEffect, useState } from 'react'
import { api } from '../api.js'

const WORKLOADS = { light: 'Light', moderate: 'Moderate', heavy: 'Heavy', very_heavy: 'Very heavy' }
const AUDIENCES = { public: 'General public', workers: 'Outdoor workers', elderly: 'Elderly & caregivers' }
const LANGS = { en: 'English', hi: 'हिन्दी', gu: 'ગુજરાતી' }

function useFetch(fn, deps) {
  const [state, setState] = useState({ data: null, error: null })
  useEffect(() => {
    let live = true
    fn().then((data) => live && setState({ data, error: null })).catch((e) => live && setState({ data: null, error: e.message }))
    return () => { live = false }
  }, deps) // eslint-disable-line react-hooks/exhaustive-deps
  return state
}

export function Actions({ wardId, day, replay }) {
  const { data, error } = useFetch(() => api.actions(wardId, day, replay), [wardId, day, replay])
  if (error) return <p className="meta">Actions unavailable: {error}</p>
  if (!data) return <p className="meta">Loading…</p>
  if (!data.actions.length) return <p className="meta">No ward actions at this alert level. Routine summer measures apply.</p>
  const byDept = {}
  for (const a of data.actions) (byDept[a.department] ??= []).push(a)
  return (
    <div className="actions">
      {Object.entries(byDept).map(([dept, list]) => (
        <div key={dept} className="dept">
          <div className="dname">{dept}</div>
          {list.map((a) => (
            <div key={a.id} className="act">
              <div>{a.action}</div>
              <div className="why">{a.reason} · {a.lead}</div>
            </div>
          ))}
        </div>
      ))}
      <p className="srcnote">Actions and departments follow the Ahmedabad Heat Action Plan (2019).</p>
    </div>
  )
}

export function WorkWindows({ wardId, day, replay }) {
  const [acclimatized, setAcclimatized] = useState(null)       // null = use the suggested mode
  const { data, error } = useFetch(() => api.workWindows(wardId, day, replay, acclimatized), [wardId, day, replay, acclimatized])
  if (error) return <p className="meta">Work windows unavailable: {error}</p>
  if (!data) return <p className="meta">Loading…</p>
  if (!data.available) return <p className="meta">No hourly data for this day.</p>
  const acc = data.acclimatized
  return (
    <div>
      <div className="seg small" role="group" aria-label="Worker acclimatization">
        <button aria-pressed={acc} onClick={() => setAcclimatized(true)}>Acclimatized</button>
        <button aria-pressed={!acc} onClick={() => setAcclimatized(false)}>New to the heat</button>
      </div>
      <ul className="work">
        {Object.entries(data.workloads).map(([k, w]) => (
          <li key={k}><b>{WORKLOADS[k]}:</b> {w.summary.replace(/^[^:]+: /, '')}</li>
        ))}
      </ul>
      <p className="meta">Peak WBGT {data.max_wbgt} °C. {data.note}
        {data.suggested_acclimatized !== acc && ' (not the suggested mode for this day)'}</p>
    </div>
  )
}

export function Advisories({ wardId, day, replay }) {
  const [lang, setLang] = useState('en')
  const [audience, setAudience] = useState('public')
  const { data, error } = useFetch(() => api.advisories(wardId, day, replay), [wardId, day, replay])
  if (error) return <p className="meta">Advisories unavailable: {error}</p>
  if (!data) return <p className="meta">Loading…</p>
  if (!data.advisories.length) return <p className="meta">No advisory on Green days.</p>
  const a = data.advisories.find((x) => x.lang === lang && x.audience === audience)
  return (
    <div>
      <div className="adv-controls">
        <div className="seg small" role="group" aria-label="Language">
          {Object.entries(LANGS).map(([k, l]) => <button key={k} aria-pressed={lang === k} onClick={() => setLang(k)} lang={k}>{l}</button>)}
        </div>
        <select aria-label="Audience" value={audience} onChange={(e) => setAudience(e.target.value)}>
          {Object.entries(AUDIENCES).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
      </div>
      {a.review_status !== 'final' && <p className="review">Draft translation: needs native-speaker review before use.</p>}
      <div className="adv" lang={lang}>
        <div className="lbl">SMS · {a.sms_chars} characters</div>
        <p>{a.sms}</p>
        <div className="lbl">WhatsApp / voice script</div>
        <p>{a.long}</p>
      </div>
    </div>
  )
}
