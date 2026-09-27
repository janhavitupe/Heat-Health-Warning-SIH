import { useEffect, useState } from 'react'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api.js'
import { SERIES } from '../theme.js'

const dark = window.matchMedia?.('(prefers-color-scheme: dark)').matches
const S = dark ? SERIES.dark : SERIES.light
const GRID = dark ? '#2c2c2a' : '#e1e0d9'
const INK2 = dark ? '#c3c2b7' : '#52514e'
const signed = (v, d = 1) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(d)}`
const shortDate = (d) => new Date(`${d}T00:00:00`).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })

// What-if simulator (Innovation 3): interventions re-run over the May 2024 heatwave.
export default function WhatIfTab({ wards, selected, point, armed, onArm, cooling }) {
  const all = (wards?.features ?? []).map((f) => f.properties).sort((a, b) => a.ward_name.localeCompare(b.ward_name))
  const [chosen, setChosen] = useState(selected ? [selected] : [])
  const [trees, setTrees] = useState(10)
  const [roofs, setRoofs] = useState(0)
  const [site, setSite] = useState('')           // '', 'map', or a recommended-site index
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const [saved, setSaved] = useState([])
  const [name, setName] = useState('')

  useEffect(() => { api.scenarios().then((x) => setSaved(x.scenarios)).catch(() => {}) }, [])
  const sites = cooling?.recommended_sites?.features ?? []
  const centre = site === 'map' ? point : site !== '' ? { lon: sites[+site]?.geometry.coordinates[0], lat: sites[+site]?.geometry.coordinates[1] } : null

  function changes() {
    const out = []
    if (chosen.length && trees > 0) out.push({ lever: 'tree_cover', wards: chosen, pp: trees })
    if (chosen.length && roofs > 0) out.push({ lever: 'cool_roofs', wards: chosen, share: roofs / 100 })
    if (centre?.lon) out.push({ lever: 'cooling_centre', lon: centre.lon, lat: centre.lat })
    return out
  }
  async function run() {
    const ch = changes()
    if (!ch.length) { setErr('Choose at least one intervention.'); return }
    setBusy(true); setErr(null)
    try { setResult(await api.runScenario(ch, 'may2024')) } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }
  async function save() {
    try { await api.saveScenario(name, '', changes(), 'may2024'); setName(''); setSaved((await api.scenarios()).scenarios) } catch (e) { setErr(e.message) }
  }

  const first = result?.wards?.[0]
  const series = first && result.series[first.ward_id].dates.map((d, i) => ({
    date: d, baseline: result.series[first.ward_id].baseline_mri[i], scenario: result.series[first.ward_id].scenario_mri[i] }))

  return (
    <div className="whatif">
      <p className="meta">Test interventions on the May 2024 heatwave before funding them. Results are <b>Scenario Estimates</b>.</p>

      <h4>Wards for tree planting / cool roofs</h4>
      <div className="chips">
        {chosen.map((w) => <button key={w} className="chip" aria-pressed="true" onClick={() => setChosen(chosen.filter((x) => x !== w))}>
          {all.find((a) => a.ward_id === w)?.ward_name ?? w} ✕</button>)}
        <select aria-label="Add ward" value="" onChange={(e) => e.target.value && setChosen([...new Set([...chosen, e.target.value])])}>
          <option value="">+ add ward</option>
          {all.map((w) => <option key={w.ward_id} value={w.ward_id}>{w.ward_name}</option>)}
        </select>
      </div>

      <label className="fld">Add tree cover: <b>+{trees} percentage points</b>
        <input type="range" min="0" max="20" step="1" value={trees} onChange={(e) => setTrees(+e.target.value)} /></label>
      <label className="fld">Cool roofs on <b>{roofs}%</b> of sheet-roofed homes
        <input type="range" min="0" max="100" step="10" value={roofs} onChange={(e) => setRoofs(+e.target.value)} /></label>
      {roofs > 0 && <p className="meta">Sheet-roof data is not available yet, so this lever will show no effect until it is added.</p>}

      <h4>New cooling centre</h4>
      <div className="adv-controls">
        <select aria-label="Cooling centre location" value={site} onChange={(e) => { setSite(e.target.value); onArm(e.target.value === 'map') }}>
          <option value="">None</option>
          <option value="map">Click a point on the map…</option>
          {sites.map((f, i) => <option key={i} value={i}>Recommended site {f.properties.rank}: {f.properties.ward_name}</option>)}
        </select>
        {site === 'map' && <span className="meta">{armed ? 'Click the map to place it.' : point ? `Placed at ${point.lat.toFixed(4)}, ${point.lon.toFixed(4)}` : ''}</span>}
      </div>

      <div className="rbtns"><button className="ok" disabled={busy} onClick={run}>{busy ? 'Running…' : 'Run scenario'}</button></div>
      {err && <p className="review" role="alert">{err}</p>}

      {result && (<>
        <div className="kpis">
          <div className="kpi"><div className="v">{result.city.red_ward_days_avoided}</div><div className="l">Red ward-days avoided</div></div>
          <div className="kpi"><div className="v">{result.city.orange_plus_ward_days_avoided}</div><div className="l">Orange-or-worse ward-days avoided</div></div>
          <div className="kpi"><div className="v">{result.city.wards_affected}</div><div className="l">Wards affected</div></div>
        </div>
        {result.changes.map((c, i) => (
          <p key={i} className="meta">
            {c.lever === 'tree_cover' && `Trees +${c.pp} pts: night surface ${signed(c.night_lst_change_c, 2)} °C, night air ${signed(c.night_air_change_c, 2)} °C.`}
            {c.lever === 'cooling_centre' && `New cooling centre: ${c.people_newly_within_walk.toLocaleString('en-IN')} more people within a 15-minute walk.`}
            {c.lever === 'cool_roofs' && (c.note || `Cool roofs on ${c.share * 100}% of sheet roofs.`)}
          </p>
        ))}
        <table className="list">
          <thead><tr><th>Ward</th><th>Mean MRI</th><th>Red days</th><th>Night min °C</th><th>PVI</th></tr></thead>
          <tbody>{result.wards.map((w) => (
            <tr key={w.ward_id} style={{ cursor: 'default' }}>
              <td>{w.ward_name}</td>
              <td className="n">{w.baseline.mean_mri.toFixed(1)} → {w.scenario.mean_mri.toFixed(1)}</td>
              <td className="n">{w.baseline.red_days} → {w.scenario.red_days}</td>
              <td className="n">{signed(w.change.mean_tmin, 2)}</td>
              <td className="n">{signed(w.change.pvi)}</td>
            </tr>))}</tbody>
        </table>
        {series && (<>
          <h4>Mortality risk in {first.ward_name}, May–June 2024</h4>
          <div className="chart">
            <ResponsiveContainer>
              <LineChart data={series} margin={{ top: 6, right: 8, bottom: 0, left: -18 }}>
                <CartesianGrid stroke={GRID} vertical={false} />
                <XAxis dataKey="date" tickFormatter={shortDate} stroke={GRID} tick={{ fill: INK2, fontSize: 11 }} minTickGap={24} />
                <YAxis domain={[0, 100]} stroke={GRID} tick={{ fill: INK2, fontSize: 11 }} />
                <Line dataKey="baseline" name="Now" stroke={S[1]} strokeWidth={2} dot={false} isAnimationActive={false} />
                <Line dataKey="scenario" name="With intervention" stroke={S[0]} strokeWidth={2} dot={false} isAnimationActive={false} />
                <Legend wrapperStyle={{ fontSize: 11, color: INK2 }} iconSize={10} />
                <Tooltip formatter={(v) => v.toFixed(1)} labelFormatter={shortDate} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>)}
        <details><summary className="meta">Assumptions</summary><ul className="work">{result.assumptions.map((a, i) => <li key={i}>{a}</li>)}</ul></details>
        <div className="rbtns">
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Name this scenario" />
          <button disabled={!name.trim()} onClick={save}>Save</button>
        </div>
      </>)}

      {saved.length > 0 && (<>
        <h4>Saved scenarios</h4>
        <table className="list"><thead><tr><th>Name</th><th>Red ward-days avoided</th><th>Wards</th></tr></thead>
          <tbody>{saved.map((x) => <tr key={x.scenario_id} style={{ cursor: 'default' }}><td>{x.name}</td>
            <td className="n">{x.city.red_ward_days_avoided}</td><td className="n">{x.city.wards_affected}</td></tr>)}</tbody></table>
      </>)}
    </div>
  )
}
