import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { ALERT_COLOR, ALERT_LABEL } from '../theme.js'

// City plan for the chosen day: action priority, city-wide measures, and resource allocation.
export default function PlanTab({ day, replay, role, onSelect }) {
  const view = role === 'healthcare' ? 'healthcare' : 'municipal'
  const [prio, setPrio] = useState(null)
  const [units, setUnits] = useState(5)
  const [amb, setAmb] = useState(10)
  const [plan, setPlan] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let live = true
    api.priorities(day, replay, view).then((p) => live && setPrio(p)).catch((e) => live && setError(e.message))
    return () => { live = false }
  }, [day, replay, view])

  useEffect(() => {
    let live = true
    api.allocation(day, replay, units, amb).then((p) => live && setPlan(p)).catch((e) => live && setError(e.message))
    return () => { live = false }
  }, [day, replay, units, amb])

  if (error) return <p className="empty">Plan unavailable: {error}</p>
  if (!prio) return <p className="empty">Loading…</p>
  const score = view === 'healthcare' ? 'hri' : 'mri'

  return (
    <div>
      <h3 style={{ marginTop: 0 }}>City-wide measures ({ALERT_LABEL[prio.worst_level]} is the highest level today)</h3>
      {prio.city_actions.length ? (
        <ul className="work">{prio.city_actions.map((a) => <li key={a.id}><b>{a.department}:</b> {a.action}</li>)}</ul>
      ) : <p className="meta">No city-wide heat measures needed.</p>}

      <h3>Where to act first ({view === 'healthcare' ? 'hospitalization risk' : 'mortality risk'}; chance of Red breaks ties)</h3>
      <table className="list">
        <thead><tr><th>#</th><th>Ward</th><th>{score.toUpperCase()}</th><th>P(Red)</th></tr></thead>
        <tbody>
          {prio.wards.slice(0, 10).map((w) => (
            <tr key={w.ward_id} onClick={() => onSelect(w.ward_id)} tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && onSelect(w.ward_id)}>
              <td className="n">{w.priority}</td>
              <td>{w.ward_name}</td>
              <td className="n"><span className="badge"><span className="dot" style={{ background: ALERT_COLOR[w[`alert_${score}`]] }} />{w[score].toFixed(0)}</span></td>
              <td className="n">{w.p_red === null || w.p_red === undefined ? '—' : `${Math.round(w.p_red * 100)}%`}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>Resource allocation</h3>
      <div className="alloc-form">
        <label>Mobile cooling units <input type="number" min="0" max="50" value={units} onChange={(e) => setUnits(Math.max(0, Math.min(50, +e.target.value || 0)))} /></label>
        <label>Ambulances <input type="number" min="0" max="200" value={amb} onChange={(e) => setAmb(Math.max(0, Math.min(200, +e.target.value || 0)))} /></label>
      </div>
      {plan && (<>
        <table className="list">
          <caption className="meta" style={{ textAlign: 'left' }}>Cooling units: placed where they bring the most at-risk people within a 15-min walk.</caption>
          <thead><tr><th>Unit</th><th>Ward</th><th>People within walk</th></tr></thead>
          <tbody>{plan.cooling_units.map((u) => (
            <tr key={u.unit} onClick={() => onSelect(u.ward_id)} title={u.reason}>
              <td className="n">{u.unit}</td><td>{u.ward_name}</td><td className="n">{u.people_within_walk.toLocaleString('en-IN')}</td>
            </tr>))}</tbody>
        </table>
        <table className="list" style={{ marginTop: 10 }}>
          <caption className="meta" style={{ textAlign: 'left' }}>Ambulances: shared by expected heat-illness demand (population × HRI).</caption>
          <thead><tr><th>Ward</th><th>Ambulances</th><th>Share of demand</th></tr></thead>
          <tbody>{plan.ambulances.map((a) => (
            <tr key={a.ward_id} onClick={() => onSelect(a.ward_id)} title={a.reason}>
              <td>{a.ward_name}</td><td className="n">{a.ambulances}</td><td className="n">{(a.share_of_demand * 100).toFixed(1)}%</td>
            </tr>))}</tbody>
        </table>
      </>)}
    </div>
  )
}
