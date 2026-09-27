import { useEffect, useState } from 'react'
import { api } from '../api.js'

const AGE = ['0-4', '5-14', '15-44', '45-59', '60+']
const SEVERITY = { mild: 'Mild (heat rash, cramps)', moderate: 'Moderate (heat exhaustion)', severe: 'Severe (heat stroke)' }
const OUTCOME = { treated: 'Treated', referred: 'Referred', died: 'Died' }
const ROLE = { asha: 'ASHA', anm: 'ANM', phc_doctor: 'PHC doctor', uhc_staff: 'UHC staff', hospital: 'Hospital' }

// Health-worker feedback (Innovation 6): anonymous case counts, anomaly flags, recalibration proposal.
export default function ReportsTab({ wards, day, replay, selected, onChanged }) {
  const all = (wards?.features ?? []).map((f) => f.properties).sort((a, b) => a.ward_name.localeCompare(b.ward_name))
  const [form, setForm] = useState({ ward_id: selected ?? '', age_band: '60+', severity: 'moderate', outcome: 'treated', role: 'asha' })
  const [sum, setSum] = useState(null)
  const [recal, setRecal] = useState(null)
  const [msg, setMsg] = useState(null)

  const load = () => Promise.all([api.reportSummary(replay, day), api.recalibration(replay)])
    .then(([s, r]) => { setSum(s); setRecal(r) }).catch((e) => setMsg(e.message))
  useEffect(() => { load() }, [day, replay]) // eslint-disable-line react-hooks/exhaustive-deps

  async function submit(e) {
    e.preventDefault()
    if (!form.ward_id) { setMsg('Choose a ward.'); return }
    try { await api.report({ ...form, date: day }, replay); setMsg('Report recorded as a count. No personal details are stored.'); load(); onChanged() }
    catch (err) { setMsg(err.message) }
  }
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })
  const today = sum?.day?.wards ?? []

  return (
    <div>
      <form className="report-form" onSubmit={submit}>
        <p className="meta">Report a suspected heat-illness case for <b>{day}</b>. Do not enter names, phone numbers or any other identifier: only the fields below are kept, as counts.</p>
        <label className="fld">Ward<select value={form.ward_id} onChange={set('ward_id')} required>
          <option value="">Choose…</option>{all.map((w) => <option key={w.ward_id} value={w.ward_id}>{w.ward_name}</option>)}</select></label>
        <label className="fld">Age band<select value={form.age_band} onChange={set('age_band')}>{AGE.map((a) => <option key={a}>{a}</option>)}</select></label>
        <label className="fld">Severity<select value={form.severity} onChange={set('severity')}>{Object.entries(SEVERITY).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
        <label className="fld">Outcome<select value={form.outcome} onChange={set('outcome')}>{Object.entries(OUTCOME).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
        <label className="fld">Reported by<select value={form.role} onChange={set('role')}>{Object.entries(ROLE).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
        <div className="rbtns"><button className="ok" type="submit">Submit report</button>
          {replay && <button type="button" onClick={() => api.seedReports(replay).then(() => { setMsg('Synthetic demo reports added (clearly labelled).'); load(); onChanged() }).catch((e) => setMsg(e.message))}>Add synthetic demo reports</button>}</div>
        {msg && <p className="review" role="status">{msg}</p>}
      </form>

      {sum && (<>
        {sum.includes_synthetic && <p className="review">Includes SYNTHETIC demo reports (69 cases spread by modelled risk, plus a planted cluster in Vatva on 23–24 May).</p>}
        <h3>Wards with more cases than expected</h3>
        {sum.flags.length === 0 ? <p className="meta">No anomalies. A ward is flagged at ≥ 3 reports, ≥ 2× its expected share and a Poisson p below 0.01.</p> : (
          <table className="list"><thead><tr><th>Date</th><th>Ward</th><th>Reports</th><th>Expected</th></tr></thead>
            <tbody>{sum.flags.map((f, i) => <tr key={i} style={{ cursor: 'default' }}><td>{f.date}</td><td><b>{f.ward_name}</b></td>
              <td className="n">{f.reports}</td><td className="n">{f.expected.toFixed(1)} ({f.ratio}×)</td></tr>)}</tbody></table>)}
        <h3>Reports on {day} ({today.reduce((a, w) => a + w.reports, 0)})</h3>
        {today.length === 0 ? <p className="meta">None.</p> : (
          <table className="list"><thead><tr><th>Ward</th><th>Reports</th><th>Expected share</th></tr></thead>
            <tbody>{today.sort((a, b) => b.reports - a.reports).map((w) => <tr key={w.ward_id} style={{ cursor: 'default' }}>
              <td>{w.ward_name}</td><td className="n">{w.reports}</td><td className="n">{w.expected.toFixed(1)}</td></tr>)}</tbody></table>)}
        <p className="meta">Expected share = the day's reports split by population × modelled mortality risk.</p>
      </>)}

      {recal?.wards?.length > 0 && (<>
        <h3>Post-season recalibration (proposal only)</h3>
        <p className="meta">{recal.note}</p>
        <table className="list"><thead><tr><th>Ward</th><th>Reported / expected</th><th>H_m now → proposed</th></tr></thead>
          <tbody>{recal.wards.filter((w) => w.evidence === 'significant').map((w) => <tr key={w.ward_id} style={{ cursor: 'default' }}>
            <td>{w.ward_name}</td><td className="n">{w.reported} / {w.expected}</td><td className="n">{w.current_h_m} → <b>{w.proposed_h_m}</b></td></tr>)}</tbody></table>
        {recal.wards.every((w) => w.evidence !== 'significant') && <p className="meta">No ward differs significantly from expectation, so no change is proposed.</p>}
      </>)}
    </div>
  )
}
