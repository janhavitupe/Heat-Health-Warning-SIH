import { useEffect, useState } from 'react'
import { api, getToken, setToken } from '../api.js'
import { ALERT_COLOR, ALERT_LABEL } from '../theme.js'

const AUDIENCES = { public: 'Public', workers: 'Outdoor workers', elderly: 'Elderly & caregivers' }
const LANGS = { en: 'English', hi: 'हिन्दी', gu: 'ગુજરાતી' }
const CHANNELS = { sms: 'SMS', whatsapp: 'WhatsApp', voice: 'Voice call' }
const STATUS = { draft: 'Draft', approved: 'Approved', rejected: 'Rejected', dispatched: 'Dispatched', superseded: 'Superseded' }

function officerName() { try { return localStorage.getItem('heat-officer') || '' } catch { return '' } }
function saveOfficer(n) { try { localStorage.setItem('heat-officer', n) } catch { /* storage unavailable */ } }

function Toggles({ options, value, onChange, disabled }) {
  return (
    <div className="toggles">
      {Object.entries(options).map(([k, l]) => (
        <label key={k}><input type="checkbox" disabled={disabled} checked={value.includes(k)}
          onChange={(e) => onChange(e.target.checked ? [...value, k] : value.filter((x) => x !== k))} /> {l}</label>
      ))}
    </div>
  )
}

function Review({ id, onChanged }) {
  const [a, setA] = useState(null)
  const [audit, setAudit] = useState([])
  const [err, setErr] = useState(null)
  const [officer, setOfficer] = useState(officerName())
  const [lang, setLang] = useState('en')
  const [aud, setAud] = useState('public')
  const [draft, setDraft] = useState(null)       // unsaved edits: {wards, audiences, languages, channels, sms, long}
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)

  const load = () => Promise.all([api.alert(id), api.audit(id)])
    .then(([x, au]) => { setA(x); setAudit(au.entries); setDraft(null); setErr(null) })
    .catch((e) => setErr(e.message))
  useEffect(() => { load() }, [id]) // eslint-disable-line react-hooks/exhaustive-deps

  if (err && !a) return <p className="empty">{err}</p>
  if (!a) return <p className="empty">Loading…</p>
  const editable = a.status === 'draft'
  const cur = draft ?? { wards: a.wards, audiences: a.audiences, languages: a.languages, channels: a.channels }
  const tpl = a.templates[lang][aud]
  const text = { sms: draft?.sms ?? tpl.sms, long: draft?.long ?? tpl.long }
  const prev = a.previews[lang]?.[aud]
  const names = Object.fromEntries(a.wards.map((w, i) => [w, a.ward_names[i]]))

  async function act(fn) {
    if (!officer.trim()) { setErr('Enter your name first: every decision is recorded with it.'); return }
    saveOfficer(officer.trim())
    setBusy(true)
    try { await fn(); await load(); onChanged() } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }
  const save = () => act(() => api.editAlert(id, {
    officer, wards: cur.wards, audiences: cur.audiences, languages: cur.languages, channels: cur.channels,
    templates: draft?.sms !== undefined || draft?.long !== undefined ? { [lang]: { [aud]: { sms: text.sms, long: text.long } } } : null,
  }))
  const edit = (patch) => setDraft({ ...cur, ...(draft ?? {}), ...patch })

  return (
    <div className="review-box">
      <div className="rhead">
        <span className="badge"><span className="dot" style={{ background: ALERT_COLOR[a.level] }} />{ALERT_LABEL[a.level]} · {a.date}</span>
        <span className={`st st-${a.status}`}>{STATUS[a.status]}</span>
        {a.kind === 'preparedness' && <span className="st">Preparedness</span>}
      </div>
      <p className="meta">{a.reason}{a.decided_by ? ` · ${STATUS[a.status]} by ${a.decided_by}${a.decision_note ? `: “${a.decision_note}”` : ''}` : ''}</p>

      <label className="fld">Your name (recorded in the audit log)
        <input value={officer} onChange={(e) => setOfficer(e.target.value)} placeholder="e.g. Deputy Health Officer" /></label>

      <h4>Wards ({cur.wards.length})</h4>
      <div className="chips">
        {a.wards.map((w) => (
          <button key={w} className="chip" aria-pressed={cur.wards.includes(w)} disabled={!editable}
            onClick={() => edit({ wards: cur.wards.includes(w) ? cur.wards.filter((x) => x !== w) : [...cur.wards, w] })}>{names[w]}</button>
        ))}
      </div>
      <h4>Audiences</h4><Toggles options={AUDIENCES} value={cur.audiences} disabled={!editable} onChange={(v) => edit({ audiences: v })} />
      <h4>Languages</h4><Toggles options={LANGS} value={cur.languages} disabled={!editable} onChange={(v) => edit({ languages: v })} />
      <h4>Channels</h4><Toggles options={CHANNELS} value={cur.channels} disabled={!editable} onChange={(v) => edit({ channels: v })} />

      <h4>Message</h4>
      <div className="adv-controls">
        <div className="seg small" role="group" aria-label="Language">
          {Object.entries(LANGS).map(([k, l]) => <button key={k} aria-pressed={lang === k} onClick={() => { setLang(k); setDraft(draft && { ...draft, sms: undefined, long: undefined }) }}>{l}</button>)}
        </div>
        <select aria-label="Audience" value={aud} onChange={(e) => { setAud(e.target.value); setDraft(draft && { ...draft, sms: undefined, long: undefined }) }}>
          {Object.entries(AUDIENCES).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
      </div>
      {lang !== 'en' && <p className="review">Draft translation: needs native-speaker review before real use.</p>}
      <label className="fld">SMS template <textarea rows={3} lang={lang} value={text.sms} disabled={!editable} onChange={(e) => edit({ sms: e.target.value })} /></label>
      <label className="fld">WhatsApp / voice template <textarea rows={5} lang={lang} value={text.long} disabled={!editable} onChange={(e) => edit({ long: e.target.value })} /></label>
      <p className="meta">Placeholders such as {'{ward}'}, {'{day}'}, {'{window}'}, {'{cooling}'} are filled per ward. Preview for {a.preview_ward}{draft ? ' (save to refresh)' : ''}:</p>
      {prev && <div className="adv" lang={lang}><div className="lbl">SMS · {prev.sms_chars} characters{prev.sms_fits ? '' : ' · TOO LONG'}</div><p>{prev.sms}</p></div>}
      {a.problems.length > 0 && <p className="review">Cannot approve yet: {a.problems.slice(0, 3).join('; ')}</p>}
      {err && <p className="review" role="alert">{err}</p>}

      <div className="rbtns">
        {editable && <button disabled={busy || !draft} onClick={save}>Save changes</button>}
        {editable && <input className="note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Note or rejection reason" />}
        {editable && <button className="ok" disabled={busy || !!draft} onClick={() => act(() => api.approve(id, officer, note))}>Approve</button>}
        {editable && <button className="bad" disabled={busy || !note.trim()} title={note.trim() ? '' : 'Write a reason first'}
          onClick={() => act(() => api.reject(id, officer, note))}>Reject</button>}
        {a.status === 'approved' && <button className="ok" disabled={busy} onClick={() => {
          if (window.confirm(`Dispatch this alert to ${cur.wards.length} ward(s) by ${cur.channels.join(', ')}? (${a.dispatch_mode} mode)`)) act(() => api.dispatch(id, officer))
        }}>Dispatch ({a.dispatch_mode})</button>}
        <a href={`/alerts/${id}/cap.xml`} target="_blank" rel="noreferrer">CAP XML</a>
      </div>

      {a.deliveries.length > 0 && (<>
        <h4>Deliveries ({a.deliveries.length})</h4>
        <table className="list"><thead><tr><th>Channel</th><th>To</th><th>Ward</th><th>Lang</th><th>Status</th></tr></thead>
          <tbody>{a.deliveries.map((d, i) => <tr key={i} style={{ cursor: 'default' }}><td>{CHANNELS[d.channel]}</td><td>{d.recipient}</td>
            <td>{names[d.ward_id] ?? d.ward_id}</td><td>{d.lang}</td><td title={d.detail}>{d.status}{d.status === 'failed' && d.detail ? `: ${d.detail}` : ''}</td></tr>)}</tbody></table>
        {a.deliveries.some((d) => /ContentSid/i.test(d.detail || '')) && <p className="meta">WhatsApp only accepts free text within 24 hours of the recipient messaging the sandbox. Ask them to send the join code (or any message) to the sandbox number, then dispatch a new alert.</p>}
      </>)}
      <h4>Audit trail</h4>
      <ul className="audit">{audit.map((x) => <li key={x.id}><b>{x.action.replace('alert_', '')}</b> · {x.actor} · {new Date(x.at).toLocaleString('en-IN')}</li>)}</ul>
    </div>
  )
}

// Simulated resident chat with the WhatsApp reply bot: same code as the live webhook, nothing is sent.
function WhatsAppPreview({ replay }) {
  const [text, setText] = useState('')
  const [chat, setChat] = useState([])
  const [busy, setBusy] = useState(false)
  async function ask(e) {
    e.preventDefault()
    const q = text.trim()
    if (!q) return
    setBusy(true)
    try {
      const r = await api.whatsappPreview(q, replay)
      setChat((c) => [...c.slice(-6), { me: q, bot: r.reply }])
      setText('')
    } catch (err) { setChat((c) => [...c, { me: q, bot: `Error: ${err.message}` }]) }
    setBusy(false)
  }
  return (
    <details className="wa">
      <summary>Resident WhatsApp preview <span className="wa-tag">simulated</span></summary>
      <p className="meta">A resident sends their ward name (optionally “hindi” or “gujarati”) and gets the alert an officer has approved. Nothing is sent from here.</p>
      <div className="wa-chat" aria-live="polite">
        {chat.length === 0 && <p className="meta">Try “Baherampura” or “Vatva gujarati”.</p>}
        {chat.map((m, i) => (<div key={i}><p className="wa-me">{m.me}</p><p className="wa-bot">{m.bot}</p></div>))}
      </div>
      <form className="rbtns" onSubmit={ask}>
        <input aria-label="Message to the WhatsApp bot" value={text} onChange={(e) => setText(e.target.value)} placeholder="Ward name…" maxLength={100} />
        <button className="ok" disabled={busy || !text.trim()} type="submit">Send</button>
      </form>
    </details>
  )
}

export default function AlertsTab({ replay, onChanged }) {
  const [list, setList] = useState(null)
  const [sel, setSel] = useState(() => Number(new URLSearchParams(location.search).get('alert')) || null)   // ?alert=<id> opens one alert
  const [err, setErr] = useState(null)
  const [token, setTok] = useState(getToken())
  const load = () => api.alerts(replay).then((x) => { setList(x); setErr(null) }).catch((e) => setErr(e.message))
  useEffect(() => { load() }, [replay]) // eslint-disable-line react-hooks/exhaustive-deps

  if (sel) return (<div><button className="linkish" onClick={() => { setSel(null); load() }}>← All alerts</button>
    <Review id={sel} onChanged={() => { load(); onChanged() }} /></div>)
  return (
    <div>
      <p className="meta">Alerts are drafted automatically when wards reach Orange or Red. <b>Nothing is sent until an officer approves and dispatches it.</b></p>
      <div className="rbtns">
        <button onClick={() => api.generate(replay).then(() => { load(); onChanged() }).catch((e) => setErr(e.message))}>Check for new alerts</button>
        <label className="meta">API token <input type="password" value={token} onChange={(e) => { setTok(e.target.value); setToken(e.target.value) }} placeholder="if required" /></label>
      </div>
      {err && <p className="review" role="alert">{err}</p>}
      <WhatsAppPreview replay={replay} />
      {!list ? <p className="empty">Loading…</p> : list.alerts.length === 0 ? <p className="empty">No alerts yet.</p> : (
        <table className="list">
          <thead><tr><th>Date</th><th>Level</th><th>Wards</th><th>Status</th></tr></thead>
          <tbody>{list.alerts.map((x) => (
            <tr key={x.alert_id} onClick={() => setSel(x.alert_id)} tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && setSel(x.alert_id)}>
              <td>{x.date}{x.kind === 'preparedness' ? ' (prep.)' : ''}</td>
              <td><span className="badge"><span className="dot" style={{ background: ALERT_COLOR[x.level] }} />{ALERT_LABEL[x.level]}</span></td>
              <td className="n">{x.wards.length}</td>
              <td><span className={`st st-${x.status}`}>{STATUS[x.status]}</span></td>
            </tr>))}</tbody>
        </table>
      )}
    </div>
  )
}
